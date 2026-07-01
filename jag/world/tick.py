"""Tick engine: orchestrates the turn processing chain.

This is the core scheduler that processes each game turn in order:
ActionPlan → Rules → Dice → WorldUpdate → NPCTick → WorldSim →
Quest → Story → Memory → Knowledge → Persist → Narrative
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Protocol

from jag.core.dice import DiceRoller, DiceResult
from jag.core.events import EventBus, EventQueue, EventType, GameEvent
from jag.core.rules import RuleContext, RuleEngine
from jag.debug.tracer import PipelineTracer, TickTrace
from jag.knowledge.graph import KnowledgeGraph
from jag.knowledge.memory import MemoryStore
from jag.world.economy import EconomySimulator
from jag.world.faction import FactionSimulator
from jag.world.npc import NPC
from jag.world.quest import Quest, QuestGenerator
from jag.world.weather import WeatherSimulator
from jag.world.world import WorldState

logger = logging.getLogger(__name__)


# ── Hook protocols for future phases (Agent layer) ──────────────


class ActionPlanner(Protocol):
    """Protocol for player action planning (implemented in Phase 6)."""

    async def plan(
        self, action_text: str, player_id: str, world: WorldState
    ) -> dict[str, Any]:
        """Parse and plan a player action. Returns structured action dict."""
        ...


class StoryDirector(Protocol):
    """Protocol for story direction (implemented in Phase 6)."""

    async def process(
        self, events: list[GameEvent], world: WorldState
    ) -> list[dict[str, Any]]:
        """Process events and generate story developments."""
        ...


class Narrator(Protocol):
    """Protocol for narrative generation (implemented in Phase 6)."""

    async def narrate(
        self, tick_result: TickResult, world: WorldState
    ) -> str:
        """Generate narrative text for a tick result."""
        ...


class NPCAgent(Protocol):
    """Protocol for NPC decision making (implemented in Phase 6)."""

    async def decide(
        self, npc: NPC, world: WorldState, observation: dict[str, Any]
    ) -> dict[str, Any]:
        """Decide NPC action for one tick."""
        ...


# ── Tick result ──────────────────────────────────────────────────


@dataclass
class TickResult:
    """Result of processing one game tick."""

    turn: int = 0
    success: bool = True
    player_action: dict[str, Any] = field(default_factory=dict)
    dice_result: DiceResult | None = None
    rule_changes: list[dict[str, Any]] = field(default_factory=list)
    npc_actions: list[dict[str, Any]] = field(default_factory=list)
    world_events: list[GameEvent] = field(default_factory=list)
    new_quests: list[Quest] = field(default_factory=list)
    story_beats: list[dict[str, Any]] = field(default_factory=list)
    narrative: str = ""
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"Turn {self.turn}:"]
        if self.player_action:
            parts.append(f"  Action: {self.player_action.get('type', 'unknown')}")
        if self.dice_result:
            parts.append(f"  Roll: {self.dice_result.summary()}")
        if self.npc_actions:
            parts.append(f"  NPCs acted: {len(self.npc_actions)}")
        if self.world_events:
            parts.append(f"  Events: {len(self.world_events)}")
        if self.new_quests:
            parts.append(f"  New quests: {len(self.new_quests)}")
        if self.errors:
            parts.append(f"  Errors: {len(self.errors)}")
        return "\n".join(parts)


# ── Tick Engine ──────────────────────────────────────────────────


class TickEngine:
    """Core turn processing orchestrator.

    Processing chain:
    1. ActionPlan  - parse & validate player action
    2. RuleEngine  - evaluate game rules
    3. Dice        - resolve action outcomes
    4. WorldUpdate - apply changes to world state
    5. NPCTick     - concurrent NPC decision & action
    6. WorldSim    - weather, economy, faction ticks
    7. Quest       - dynamic quest generation
    8. Story       - story arc processing
    9. Memory      - memory compression
    10. Knowledge  - knowledge graph update
    11. Persist    - save state
    12. Narrative  - generate narrative text
    """

    def __init__(
        self,
        world: WorldState,
        event_bus: EventBus,
        rule_engine: RuleEngine,
        dice: DiceRoller,
        # Simulators
        weather: WeatherSimulator | None = None,
        economy: EconomySimulator | None = None,
        faction: FactionSimulator | None = None,
        quest_gen: QuestGenerator | None = None,
        knowledge: KnowledgeGraph | None = None,
        # Hooks (Phase 6)
        action_planner: ActionPlanner | None = None,
        story_director: StoryDirector | None = None,
        narrator: Narrator | None = None,
        npc_agent: NPCAgent | None = None,
        # Config
        npc_concurrency: int = 5,
        # Debug
        tracer: PipelineTracer | None = None,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self.rule_engine = rule_engine
        self.dice = dice
        # Simulators
        self.weather = weather or WeatherSimulator()
        self.economy = economy or EconomySimulator()
        self.faction = faction or FactionSimulator()
        self.quest_gen = quest_gen or QuestGenerator()
        self.knowledge = knowledge or KnowledgeGraph()
        # Hooks
        self.action_planner = action_planner
        self.story_director = story_director
        self.narrator = narrator
        self.npc_agent = npc_agent
        # State
        self._npcs: dict[str, NPC] = {}
        self._memory_stores: dict[str, MemoryStore] = {}
        self._semaphore = asyncio.Semaphore(npc_concurrency)
        self._persist_callback: Callable[..., Coroutine[Any, Any, None]] | None = None
        self._event_queue = EventQueue()
        self.tracer = tracer

    def register_npc(self, npc: NPC) -> None:
        """Register an NPC for tick processing."""
        self._npcs[npc.id] = npc
        self._memory_stores[npc.id] = npc.memory

    def clear_npcs(self) -> None:
        """Clear all registered NPCs."""
        self._npcs.clear()
        self._memory_stores.clear()

    def set_persist_callback(
        self, callback: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """Set callback for persisting state after each tick."""
        self._persist_callback = callback

    async def tick(self, player_action: dict[str, Any] | None = None) -> TickResult:
        """Process one game tick.

        Args:
            player_action: Player's action dict with keys like:
                - type: str (move, attack, interact, use, etc.)
                - target: str (target entity/location ID)
                - params: dict (action-specific parameters)
                - text: str (original natural language input)

        Returns:
            TickResult with all outcomes from this tick.
        """
        # Determine player input text for tracing
        player_input_text = ""
        if player_action:
            player_input_text = player_action.get("text", "")

        # Start tracing
        trace: TickTrace | None = None
        if self.tracer:
            trace = self.tracer.start_tick(
                turn=self.world.time.turn,
                player_input=player_input_text,
            )

        result = TickResult(turn=self.world.time.turn)

        try:
            # === PHASE 1: DANGER CHECK & NPC GENERATION (CODE-ONLY) ===
            
            # 1. Check if player is in danger or moving to danger
            danger_encountered = await self._step_danger_check(player_action, result, trace)
            
            # 2. Dynamically generate NPCs if needed
            await self._step_dynamic_npc_generation(player_action, result, trace)
            
            # === PHASE 2: STANDARD TICK PROCESSING ===
            
            # 3. Action Planning (uses LLM only if needed)
            planned_action = await self._step_action_plan(player_action, result, trace)

            # 4. Rule Evaluation (CODE-ONLY)
            await self._step_rules(planned_action, result, trace)

            # 5. Dice Resolution (CODE-ONLY)
            await self._step_dice(planned_action, result, trace)

            # 6. World Update (CODE-ONLY)
            await self._step_world_update(planned_action, result, trace)

            # 7. NPC Tick (concurrent, CODE-ONLY + LLM for decisions if available)
            await self._step_npc_tick(result, trace)

            # 8. World Simulation (CODE-ONLY)
            sim_events = self._step_world_sim(result, trace)

            # 9. Quest Generation (CODE-ONLY)
            await self._step_quest_gen(sim_events, result, trace)

            # 10. Story Processing (LLM, optional)
            await self._step_story(result, trace)

            # 11. Memory Compression (CODE-ONLY)
            await self._step_memory(result, trace)

            # 12. Knowledge Graph Update (CODE-ONLY)
            await self._step_knowledge(result, trace)

            # 13. Persist (CODE-ONLY)
            await self._step_persist(result, trace)

            # 14. Narrative Generation (LLM, with code fallback)
            await self._step_narrative(result, trace)

            # Advance time
            self.world.advance_time(1)
            result.success = True

        except Exception as e:
            logger.error("Tick error: %s", e)
            result.errors.append(str(e))
            result.success = False

        # Finalize trace
        if trace and self.tracer:
            trace.narrative = result.narrative
            trace.action_type = result.player_action.get("type", "") if result.player_action else ""
            trace.dice_summary = result.dice_result.summary() if result.dice_result else ""
            trace.npc_count = len(result.npc_actions)
            trace.event_count = len(result.world_events)
            trace.quest_count = len(result.new_quests)
            trace.story_beat_count = len(result.story_beats)
            trace.errors = list(result.errors)
            self.tracer.end_tick(trace)
            await self.tracer.notify(trace)

        # Publish tick complete event
        await self.event_bus.publish(
            GameEvent(
                event_type=EventType.SYSTEM,
                description=f"Tick {result.turn} complete",
                data={"success": result.success, "errors": len(result.errors)},
                turn=result.turn,
            )
        )

        return result

    # ── Step implementations ─────────────────────────────────────

    async def _step_danger_check(
        self, player_action: dict[str, Any] | None, result: TickResult, trace: TickTrace | None = None
    ) -> bool:
        """Check if player is in danger or entering danger. Code-only step."""
        step = self.tracer.start_step("danger_check") if self.tracer else None
        
        from jag.core.events import EventType, GameEvent
        
        player_id = "player"  # default player ID
        player = self.world.characters.get(player_id, {})
        current_loc_id = player.get("location_id", "")
        
        danger_encountered = False
        danger_description = ""
        
        # Check destination danger if moving
        if player_action and player_action.get("type") == "move":
            dest_loc_id = player_action.get("target", "")
            if dest_loc_id:
                dest_loc = self.world.locations.get(dest_loc_id)
                if dest_loc and dest_loc.danger_level >= 7:
                    # High danger! Roll to see if encounter happens
                    dc = 8 + dest_loc.danger_level - 5
                    roll = self.dice.roll(dc=dc)
                    if not roll.is_success:
                        danger_encountered = True
                        danger_description = f"你在前往{dest_loc.name}的途中遇到了危险！"
                        result.dice_result = roll
        
        # Check current location danger
        if not danger_encountered and current_loc_id:
            current_loc = self.world.locations.get(current_loc_id)
            if current_loc:
                # Check for hostile characters
                hostiles = self.world.get_hostile_characters_at(current_loc_id, exclude_id=player_id)
                if hostiles:
                    danger_encountered = True
                    hostile_name = self.world.characters.get(hostiles[0], {}).get("name", "某物")
                    danger_description = f"{hostile_name}正在对你虎视眈眈！"
        
        if danger_encountered:
            # Emit danger event
            await self.event_bus.publish(
                GameEvent(
                    event_type=EventType.DANGER,
                    description=danger_description,
                    data={"location_id": current_loc_id, "danger_level": current_loc.danger_level if current_loc else 0},
                    turn=result.turn,
                )
            )
            result.world_events.append(
                GameEvent(
                    event_type=EventType.DANGER,
                    description=danger_description,
                    data={"location_id": current_loc_id},
                    turn=result.turn,
                )
            )
        
        if step and self.tracer:
            self.tracer.end_step(step, details={"danger_encountered": danger_encountered, "description": danger_description})
            trace.steps.append(step)
        
        return danger_encountered
    
    async def _step_dynamic_npc_generation(
        self, player_action: dict[str, Any] | None, result: TickResult, trace: TickTrace | None = None
    ) -> None:
        """Dynamically generate NPCs based on location and context. Code-only step."""
        step = self.tracer.start_step("dynamic_npc") if self.tracer else None
        
        from random import randint
        from jag.world.npc import NPC
        
        player_id = "player"
        player = self.world.characters.get(player_id, {})
        current_loc_id = player.get("location_id", "")
        
        if current_loc_id:
            current_loc = self.world.locations.get(current_loc_id)
            if current_loc:
                # 1. Generate NPC based on location type and tags
                loc_type = current_loc.location_type
                loc_tags = current_loc.tags
                should_generate = False
                npc_type = "citizen"
                
                # Location-type based generation
                if loc_type in ["tavern", "inn", "market", "shop"]:
                    npc_type = "merchant"
                    should_generate = randint(1, 100) <= 70
                elif loc_type in ["gate", "wall", "tower", "fortress"]:
                    npc_type = "guard"
                    should_generate = randint(1, 100) <= 80
                elif loc_type in ["forest", "cave", "ruins", "dungeon"]:
                    npc_type = "monster"
                    should_generate = randint(1, 100) <= 40 + current_loc.danger_level
                
                # Tag-based generation
                if "tavern" in loc_tags:
                    npc_type = "merchant"
                    should_generate = True
                
                # Generate NPC if conditions met
                if should_generate and len(current_loc.entities) < 10:
                    npc_info = self.world.generate_npc_at(current_loc_id, npc_type)
                    
                    # Create NPC
                    npc = NPC(
                        id=npc_info["id"],
                        name=npc_info["data"]["name"],
                        description=f"{npc_info['data']['role']}，出现在{current_loc.name}。",
                    )
                    npc.state.current_location_id = current_loc_id
                    npc.state.mood = "neutral"
                    
                    # Register NPC
                    self.register_npc(npc)
                    self.world.add_character(npc.id, npc_info["data"])
                    
                    result.npc_actions.append({
                        "npc_id": npc.id,
                        "npc_name": npc.name,
                        "action": "spawn",
                        "description": f"{npc.name}出现了。",
                        "location_id": current_loc_id,
                    })
        
        if step and self.tracer:
            self.tracer.end_step(step, details={"npc_generated": len([a for a in result.npc_actions if a.get("action") == "spawn"])})
            trace.steps.append(step)

    async def _step_action_plan(
        self, player_action: dict[str, Any] | None, result: TickResult, trace: TickTrace | None = None
    ) -> dict[str, Any]:
        """Step 1: Parse and plan the player action."""
        step = self.tracer.start_step("action_plan") if self.tracer else None
        if not player_action:
            if step and self.tracer:
                self.tracer.end_step(step, details={"skipped": True})
                trace.steps.append(step)  # type: ignore[union-attr]
            return {}

        if self.action_planner:
            try:
                planned = await asyncio.wait_for(
                    self.action_planner.plan(
                        action_text=player_action.get("text", ""),
                        player_id=player_action.get("player_id", "player"),
                        world=self.world,
                    ),
                    timeout=8.0,
                )
                result.player_action = planned
                if step and self.tracer:
                    self.tracer.end_step(step, details={
                        "action_type": planned.get("type", ""),
                        "target": planned.get("target", ""),
                        "risk": planned.get("risk", ""),
                        "dc": planned.get("dc", 0),
                        "attribute": planned.get("attribute", ""),
                    })
                    trace.steps.append(step)  # type: ignore[union-attr]
                return planned
            except asyncio.TimeoutError:
                logger.warning("Action planner timed out, using fallback")
                result.errors.append("action_plan: timeout")
                result.player_action = player_action
                if step and self.tracer:
                    self.tracer.end_step(step, details={"fallback": "timeout", "action_type": player_action.get("type", "")})
                    trace.steps.append(step)  # type: ignore[union-attr]
                return player_action
            except Exception as e:
                logger.warning("Action planner failed: %s", e)
                result.errors.append(f"action_plan: {e}")
                if step and self.tracer:
                    self.tracer.end_step(step, success=False, error=str(e))
                    trace.steps.append(step)  # type: ignore[union-attr]

        # Fallback: use raw action
        result.player_action = player_action
        if step and self.tracer:
            self.tracer.end_step(step, details={"fallback": True, "action_type": player_action.get("type", "")})
            trace.steps.append(step)  # type: ignore[union-attr]
        return player_action

    async def _step_rules(
        self, action: dict[str, Any], result: TickResult, trace: TickTrace | None = None
    ) -> None:
        """Step 2: Evaluate game rules."""
        step = self.tracer.start_step("rules") if self.tracer else None
        if not action:
            if step and self.tracer:
                self.tracer.end_step(step, details={"skipped": True})
                trace.steps.append(step)  # type: ignore[union-attr]
            return

        context = RuleContext(
            source=action,
            actor=self.world.characters.get(action.get("player_id", ""), {}),
            world=self.world.snapshot(),
            turn=self.world.time.turn,
        )
        try:
            changes = self.rule_engine.evaluate(context)
            result.rule_changes = changes

            # Emit events from rule changes
            for change in changes:
                event = change.get("_emit_event")
                if event and isinstance(event, GameEvent):
                    await self.event_bus.publish(event)
                    result.world_events.append(event)
            if step and self.tracer:
                self.tracer.end_step(step, details={"rules_matched": len(changes)})
                trace.steps.append(step)  # type: ignore[union-attr]
        except Exception as e:
            logger.warning("Rule evaluation failed: %s", e)
            result.errors.append(f"rules: {e}")
            if step and self.tracer:
                self.tracer.end_step(step, success=False, error=str(e))
                trace.steps.append(step)  # type: ignore[union-attr]

    async def _step_dice(
        self, action: dict[str, Any], result: TickResult, trace: TickTrace | None = None
    ) -> None:
        """Step 3: Resolve actions with dice rolls."""
        step = self.tracer.start_step("dice") if self.tracer else None
        if not action:
            if step and self.tracer:
                self.tracer.end_step(step, details={"skipped": True})
                trace.steps.append(step)  # type: ignore[union-attr]
            return

        action_type = action.get("type", "")
        if action_type in ("attack", "check", "skill"):
            dc = action.get("dc", 10)
            attribute_mod = action.get("attribute_mod", 0)
            proficiency_mod = action.get("proficiency_mod", 0)
            advantage = action.get("advantage", False)
            disadvantage = action.get("disadvantage", False)

            dice_result = self.dice.roll_check(
                attribute_mod=attribute_mod,
                proficiency_mod=proficiency_mod,
                dc=dc,
                advantage=advantage,
                disadvantage=disadvantage,
            )
            result.dice_result = dice_result

            await self.event_bus.publish(
                GameEvent(
                    event_type=EventType.COMBAT if action_type == "attack" else EventType.INTERACTION,
                    source_id=action.get("player_id", "player"),
                    target_id=action.get("target", ""),
                    description=f"Dice roll: {dice_result.summary()}",
                    data={"roll": dice_result.total, "success": dice_result.is_success},
                    turn=self.world.time.turn,
                )
            )
            if step and self.tracer:
                self.tracer.end_step(step, details={
                    "roll": dice_result.base_roll,
                    "total": dice_result.total,
                    "result": dice_result.result.value,
                    "dc": dc,
                    "summary": dice_result.summary(),
                })
                trace.steps.append(step)  # type: ignore[union-attr]
        else:
            if step and self.tracer:
                self.tracer.end_step(step, details={"skipped": True, "reason": f"action_type={action_type}"})
                trace.steps.append(step)  # type: ignore[union-attr]

    async def _step_world_update(
        self, action: dict[str, Any], result: TickResult, trace: TickTrace | None = None
    ) -> None:
        """Step 4: Apply action effects to world state."""
        step = self.tracer.start_step("world_update") if self.tracer else None
        if not action:
            if step and self.tracer:
                self.tracer.end_step(step, details={"skipped": True})
                trace.steps.append(step)  # type: ignore[union-attr]
            return

        action_type = action.get("type", "")
        player_id = action.get("player_id", "player")

        if action_type == "move":
            target_loc = action.get("target", "")
            player_data = self.world.characters.get(player_id, {})
            current_loc = player_data.get("location_id", "")
            if current_loc and target_loc:
                self.world.move_character(player_id, current_loc, target_loc)
                from_loc_name = current_loc
                to_loc_name = target_loc
                from_loc = self.world.locations.get(current_loc)
                if from_loc:
                    from_loc_name = from_loc.name
                to_loc = self.world.locations.get(target_loc)
                if to_loc:
                    to_loc_name = to_loc.name
                result.world_events.append(
                    GameEvent(
                        event_type=EventType.INTERACTION,
                        source_id=player_id,
                        description=f"你从{from_loc_name}来到了{to_loc_name}。",
                        data={"from": current_loc, "to": target_loc},
                        turn=self.world.time.turn,
                    )
                )

        elif action_type == "take":
            item_id = action.get("target", "")
            player_data = self.world.characters.get(player_id, {})
            loc_id = player_data.get("location_id", "")
            if loc_id and item_id in self.world.get_location_items(loc_id):
                loc = self.world.locations[loc_id]
                loc.items.remove(item_id)
                inventory = player_data.setdefault("inventory", [])
                inventory.append(item_id)

        elif action_type == "drop":
            item_id = action.get("target", "")
            player_data = self.world.characters.get(player_id, {})
            loc_id = player_data.get("location_id", "")
            inventory = player_data.get("inventory", [])
            if loc_id and item_id in inventory:
                inventory.remove(item_id)
                loc = self.world.locations[loc_id]
                loc.items.append(item_id)

        if step and self.tracer:
            self.tracer.end_step(step, details={"action_type": action_type, "target": action.get("target", "")})
            trace.steps.append(step)  # type: ignore[union-attr]

    async def _step_npc_tick(self, result: TickResult, trace: TickTrace | None = None) -> None:
        """Step 5: Process NPC ticks.

        Optimization: only update NPCs affected by the player action:
        - If player acts (interact/speak): only target NPC + same-location NPCs
        - If player moves: NPCs at origin + destination
        - If no player action (wait): all NPCs
        """
        step = self.tracer.start_step("npc_tick") if self.tracer else None
        if not self._npcs:
            if step and self.tracer:
                self.tracer.end_step(step, details={"skipped": True, "npc_count": 0})
                trace.steps.append(step)  # type: ignore[union-attr]
            return

        player_action = result.player_action
        affected_loc_ids: set[str] = set()
        target_npc_id: str | None = None

        if player_action:
            action_type = player_action.get("type", "")
            player_data = self.world.characters.get("player", {})
            current_loc = player_data.get("location_id", "")

            if action_type == "move":
                dest = player_action.get("target", "")
                if current_loc:
                    affected_loc_ids.add(current_loc)
                if dest:
                    affected_loc_ids.add(dest)
            elif action_type in ("speak", "interact", "attack"):
                target = player_action.get("target", "")
                if target and target in self._npcs:
                    target_npc_id = target
                if current_loc:
                    affected_loc_ids.add(current_loc)
            else:
                if current_loc:
                    affected_loc_ids.add(current_loc)

        tasks = []
        processed_count = 0
        for npc_id, npc in self._npcs.items():
            should_process = False
            if not player_action:
                should_process = True
            elif target_npc_id and npc_id == target_npc_id:
                should_process = True
            elif npc.state.current_location_id in affected_loc_ids:
                should_process = True

            if should_process:
                tasks.append(self._process_single_npc(npc_id, npc, result))
                processed_count += 1

        await asyncio.gather(*tasks, return_exceptions=True)

        if step and self.tracer:
            self.tracer.end_step(step, details={
                "total_npcs": len(self._npcs),
                "processed": processed_count,
                "actions": len(result.npc_actions),
            })
            trace.steps.append(step)  # type: ignore[union-attr]

    async def _process_single_npc(
        self, npc_id: str, npc: NPC, result: TickResult
    ) -> None:
        """Process a single NPC's tick with semaphore limiting."""
        async with self._semaphore:
            try:
                # Build observation
                loc_id = npc.state.current_location_id
                world_data = {
                    "location": {
                        "id": loc_id,
                        "name": self.world.locations.get(loc_id, None),
                    },
                    "nearby_characters": self.world.get_location_entities(loc_id),
                    "nearby_items": self.world.get_location_items(loc_id),
                    "time": self.world.time.time_of_day(),
                    "hour": self.world.time.hour,
                }
                observation = npc.get_observation(world_data)

                # Check schedule
                schedule = npc.get_current_schedule(self.world.time.hour)
                if schedule:
                    observation["schedule"] = {
                        "activity": schedule.activity,
                        "location": schedule.location_id,
                    }

                # Get NPC decision
                if self.npc_agent:
                    try:
                        action = await asyncio.wait_for(
                            self.npc_agent.decide(npc, self.world, observation),
                            timeout=5.0,
                        )
                    except asyncio.TimeoutError:
                        action = self._default_npc_action(npc, observation, schedule)
                    except Exception:
                        action = self._default_npc_action(npc, observation, schedule)
                else:
                    action = self._default_npc_action(npc, observation, schedule)

                # Apply NPC action
                if action and action.get("type"):
                    await self._apply_npc_action(npc, action, result)

                # NPC state decay
                npc.state.energy = max(0.0, npc.state.energy - 0.02)
                npc.state.hunger = min(1.0, npc.state.hunger + 0.03)

                # Record memory
                if action and action.get("type") != "idle":
                    npc.record_memory(
                        f"Turn {self.world.time.turn}: {action.get('type', 'did something')}",
                        importance=3,
                        turn=self.world.time.turn,
                    )

            except Exception as e:
                logger.warning("NPC %s tick failed: %s", npc_id, e)
                result.errors.append(f"npc_{npc_id}: {e}")

    def _default_npc_action(
        self,
        npc: NPC,
        observation: dict[str, Any],
        schedule: Any,
    ) -> dict[str, Any]:
        """Default NPC action when no NPCAgent is provided."""
        if schedule and schedule.location_id:
            if npc.state.current_location_id != schedule.location_id:
                return {
                    "type": "move",
                    "target": schedule.location_id,
                    "description": f"{npc.name} heads to {schedule.location_id}",
                }
            return {
                "type": "schedule_activity",
                "activity": schedule.activity,
                "description": f"{npc.name} is {schedule.activity}",
            }
        return {"type": "idle", "description": f"{npc.name} idles"}

    async def _apply_npc_action(
        self, npc: NPC, action: dict[str, Any], result: TickResult
    ) -> None:
        """Apply an NPC's action to the world."""
        action_type = action.get("type", "")

        if action_type == "move":
            target = action.get("target", "")
            old_loc = npc.state.current_location_id
            if old_loc and target:
                self.world.move_character(npc.id, old_loc, target)
                npc.state.current_location_id = target

        npc.state.current_action = action.get("description", action_type)
        result.npc_actions.append({
            "npc_id": npc.id,
            "npc_name": npc.name,
            "action": action_type,
            "description": action.get("description", ""),
            "location_id": npc.state.current_location_id,
        })

        await self.event_bus.publish(
            GameEvent(
                event_type=EventType.NPC_ACTION,
                source_id=npc.id,
                location_id=npc.state.current_location_id,
                description=action.get("description", f"{npc.name} acts"),
                data={"action": action_type},
                turn=self.world.time.turn,
            )
        )

    def _step_world_sim(self, result: TickResult, trace: TickTrace | None = None) -> list[dict[str, Any]]:
        """Step 6: Run world simulations (weather, economy, faction)."""
        step = self.tracer.start_step("world_sim") if self.tracer else None
        all_sim_events: list[dict[str, Any]] = []

        # Weather
        try:
            weather_events = self.weather.tick(season=self.world.time.season)
            all_sim_events.extend(weather_events)
        except Exception as e:
            logger.warning("Weather tick failed: %s", e)
            result.errors.append(f"weather: {e}")

        # Economy
        try:
            econ_events = self.economy.tick(self.world)
            all_sim_events.extend(econ_events)
        except Exception as e:
            logger.warning("Economy tick failed: %s", e)
            result.errors.append(f"economy: {e}")

        # Faction
        try:
            faction_events = self.faction.tick(self.world)
            all_sim_events.extend(faction_events)
        except Exception as e:
            logger.warning("Faction tick failed: %s", e)
            result.errors.append(f"faction: {e}")

        # Convert sim events to GameEvents
        for sim_evt in all_sim_events:
            evt_type_str = sim_evt.get("type", "environment")
            evt_type_map = {
                "weather_change": EventType.ENVIRONMENT,
                "price_shift": EventType.ECONOMY,
                "faction_tension": EventType.SOCIAL,
            }
            game_event = GameEvent(
                event_type=evt_type_map.get(evt_type_str, EventType.WORLD),
                description=sim_evt.get("description", str(sim_evt)),
                data=sim_evt,
                turn=self.world.time.turn,
            )
            result.world_events.append(game_event)

        if step and self.tracer:
            self.tracer.end_step(step, details={"sim_events": len(all_sim_events)})
            trace.steps.append(step)  # type: ignore[union-attr]

        return all_sim_events

    async def _step_quest_gen(
        self, sim_events: list[dict[str, Any]], result: TickResult, trace: TickTrace | None = None
    ) -> None:
        """Step 7: Generate quests from events."""
        step = self.tracer.start_step("quest_gen") if self.tracer else None
        try:
            new_quests = self.quest_gen.check(self.world, sim_events)
            result.new_quests = new_quests
            for quest in new_quests:
                await self.event_bus.publish(
                    GameEvent(
                        event_type=EventType.QUEST,
                        description=f"New quest: {quest.title}",
                        data={"quest_id": quest.id, "title": quest.title},
                        turn=self.world.time.turn,
                    )
                )
            if step and self.tracer:
                self.tracer.end_step(step, details={"new_quests": len(new_quests)})
                trace.steps.append(step)  # type: ignore[union-attr]
        except Exception as e:
            logger.warning("Quest generation failed: %s", e)
            result.errors.append(f"quest: {e}")
            if step and self.tracer:
                self.tracer.end_step(step, success=False, error=str(e))
                trace.steps.append(step)  # type: ignore[union-attr]

    async def _step_story(self, result: TickResult, trace: TickTrace | None = None) -> None:
        """Step 8: Process story developments."""
        step = self.tracer.start_step("story") if self.tracer else None
        if not self.story_director or not result.world_events:
            if step and self.tracer:
                self.tracer.end_step(step, details={"skipped": True})
                trace.steps.append(step)  # type: ignore[union-attr]
            return
        try:
            story_beats = await asyncio.wait_for(
                self.story_director.process(result.world_events, self.world),
                timeout=8.0,
            )
            result.story_beats = story_beats
            if step and self.tracer:
                self.tracer.end_step(step, details={"story_beats": len(story_beats)})
                trace.steps.append(step)  # type: ignore[union-attr]
        except asyncio.TimeoutError:
            logger.warning("Story processing timed out")
            result.errors.append("story: timeout")
            if step and self.tracer:
                self.tracer.end_step(step, success=False, error="timeout")
                trace.steps.append(step)  # type: ignore[union-attr]
        except Exception as e:
            logger.warning("Story processing failed: %s", e)
            result.errors.append(f"story: {e}")
            if step and self.tracer:
                self.tracer.end_step(step, success=False, error=str(e))
                trace.steps.append(step)  # type: ignore[union-attr]

    async def _step_memory(self, result: TickResult, trace: TickTrace | None = None) -> None:
        """Step 9: Memory maintenance (compression handled externally)."""
        step = self.tracer.start_step("memory") if self.tracer else None
        # Memory compression is handled by MemoryCompressor
        # Here we just ensure short-term memories don't overflow
        for npc_id, store in self._memory_stores.items():
            try:
                # If short-term memory exceeds capacity, it's handled by the
                # MemoryStore.record() sliding window automatically
                pass
            except Exception as e:
                logger.warning("Memory step failed for %s: %s", npc_id, e)

        if step and self.tracer:
            self.tracer.end_step(step, details={"memory_stores": len(self._memory_stores)})
            trace.steps.append(step)  # type: ignore[union-attr]

    async def _step_knowledge(self, result: TickResult, trace: TickTrace | None = None) -> None:
        """Step 10: Update knowledge graph from events."""
        step = self.tracer.start_step("knowledge") if self.tracer else None
        updates = 0
        for event in result.world_events:
            try:
                # Convert GameEvent to dict for KnowledgeGraph.infer()
                event_dict = {
                    "type": event.event_type.value,
                    "entity_id": event.source_id,
                    "target_id": event.target_id,
                    "location_id": event.location_id,
                    **event.data,
                }
                self.knowledge.infer(event_dict)
                updates += 1
            except Exception as e:
                logger.warning("Knowledge update failed: %s", e)

        if step and self.tracer:
            self.tracer.end_step(step, details={"events_processed": updates})
            trace.steps.append(step)  # type: ignore[union-attr]

    async def _step_persist(self, result: TickResult, trace: TickTrace | None = None) -> None:
        """Step 11: Persist state."""
        step = self.tracer.start_step("persist") if self.tracer else None
        if self._persist_callback:
            try:
                await self._persist_callback(self.world, result)
            except Exception as e:
                logger.warning("Persist failed: %s", e)
                result.errors.append(f"persist: {e}")

        if step and self.tracer:
            has_cb = self._persist_callback is not None
            self.tracer.end_step(step, details={"has_callback": has_cb})
            trace.steps.append(step)  # type: ignore[union-attr]

    async def _step_narrative(self, result: TickResult, trace: TickTrace | None = None) -> None:
        """Step 14: Generate narrative text (with improved code-based fallback)."""
        step = self.tracer.start_step("narrative") if self.tracer else None
        if self.narrator:
            try:
                result.narrative = await asyncio.wait_for(
                    self.narrator.narrate(result, self.world),
                    timeout=8.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Narrative generation timed out, using fallback")
                result.errors.append("narrative: timeout")
                result.narrative = self._generate_fallback_narrative(result)
            except Exception as e:
                logger.warning("Narrative generation failed: %s, using fallback", e)
                result.errors.append(f"narrative: {e}")
                result.narrative = self._generate_fallback_narrative(result)
        else:
            result.narrative = self._generate_fallback_narrative(result)

        if step and self.tracer:
            self.tracer.end_step(step, details={"narrative_length": len(result.narrative), "llm_used": self.narrator is not None})
            trace.steps.append(step)
    
    def _generate_fallback_narrative(self, result: TickResult) -> str:
        """Generate rich narrative text using code-only logic."""
        parts = []
        player_loc_id = ""
        player_data = self.world.characters.get("player", {})
        if player_data:
            player_loc_id = player_data.get("location_id", "")

        action_type = ""
        target = ""
        if result.player_action:
            action_type = result.player_action.get("type", "act")
            action_text = result.player_action.get("text", "")
            target = result.player_action.get("target", "")

            if action_type == "move" and target:
                loc = self.world.locations.get(target)
                loc_name = loc.name if loc else target
                parts.append(f"你动身前往{loc_name}。")
            elif action_type == "speak" and target:
                npc_data = self.world.characters.get(target, {})
                npc_name = npc_data.get("name", target)
                parts.append(f"你走向{npc_name}，开始与对方交谈。")
                import random
                dialogues = [
                    f"{npc_name}抬起头，微笑着说：'你好，旅行者。有什么我可以帮你的吗？'",
                    f"{npc_name}看了你一眼：'哦，是外地人啊。这镇子最近可不太平。'",
                    f"'欢迎来到这里。'{npc_name}说道，'你是来做生意的，还是来冒险的？'",
                    f"{npc_name}放下手中的活计：'今天天气真不错，对吧？'",
                    f"'小心点，朋友。'{npc_name}压低声音，'最近夜里有奇怪的声音。'",
                ]
                parts.append(random.choice(dialogues))
            elif action_type == "interact" and target:
                npc_data = self.world.characters.get(target, {})
                if npc_data:
                    parts.append(f"你与{npc_data.get('name', target)}进行了互动。")
                else:
                    parts.append(f"你试着与{target}互动。")
            elif action_type == "attack" and target:
                parts.append(f"你向{target}发起攻击！")
            elif action_type == "rest":
                parts.append("你稍作休息，恢复体力。")
            elif action_type == "examine":
                if target:
                    parts.append(f"你仔细检查{target}。")
                else:
                    parts.append("你仔细观察周围的环境。")
            elif target:
                action_desc = {
                    "take": "拾取",
                    "drop": "丢弃",
                    "use": "使用",
                    "craft": "制作",
                }.get(action_type, action_type or "行动")
                parts.append(f"你尝试{action_desc}{target}。")
            elif action_text:
                parts.append(f"你尝试{action_text}。")

        if result.dice_result:
            roll = result.dice_result
            if roll.result.value == "critical_success":
                parts.append("你完美地完成了！这真是一次出色的表现！")
            elif roll.result.value == "success":
                parts.append("你成功了！事情进展得很顺利。")
            elif roll.result.value == "failure":
                parts.append("你失败了……事情没有按计划进行。")
            elif roll.result.value == "critical_failure":
                parts.append("糟糕！这是一次灾难性的失败！")

        for evt in result.world_events:
            if evt.event_type.value == "danger":
                parts.append(evt.description)

        nearby_npc_actions = [
            a for a in result.npc_actions
            if a.get("location_id") == player_loc_id or a.get("action") == "spawn"
        ]
        for npc_act in nearby_npc_actions[:5]:
            if action_type == "speak" and target and npc_act.get("npc_id") == target:
                continue
            if npc_act.get("action") == "spawn":
                parts.append(npc_act.get("description", ""))
            elif npc_act.get("description"):
                parts.append(npc_act["description"])

        other_events = [e for e in result.world_events if e.event_type.value != "danger"]
        for evt in other_events[:2]:
            parts.append(evt.description)

        if not parts:
            parts.append("时间流逝，周围一切如常。")

        return " ".join(p for p in parts if p)
