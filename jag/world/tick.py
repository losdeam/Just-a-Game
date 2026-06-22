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
            # 1. Action Planning
            planned_action = await self._step_action_plan(player_action, result, trace)

            # 2. Rule Evaluation
            await self._step_rules(planned_action, result, trace)

            # 3. Dice Resolution
            await self._step_dice(planned_action, result, trace)

            # 4. World Update
            await self._step_world_update(planned_action, result, trace)

            # 5. NPC Tick (concurrent)
            await self._step_npc_tick(result, trace)

            # 6. World Simulation
            sim_events = self._step_world_sim(result, trace)

            # 7. Quest Generation
            await self._step_quest_gen(sim_events, result, trace)

            # 8. Story Processing
            await self._step_story(result, trace)

            # 9. Memory Compression
            await self._step_memory(result, trace)

            # 10. Knowledge Graph Update
            await self._step_knowledge(result, trace)

            # 11. Persist
            await self._step_persist(result, trace)

            # 12. Narrative
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
                planned = await self.action_planner.plan(
                    action_text=player_action.get("text", ""),
                    player_id=player_action.get("player_id", "player"),
                    world=self.world,
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
                result.world_events.append(
                    GameEvent(
                        event_type=EventType.INTERACTION,
                        source_id=player_id,
                        description=f"Moved from {current_loc} to {target_loc}",
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
        """Step 5: Process all NPC ticks concurrently."""
        step = self.tracer.start_step("npc_tick") if self.tracer else None
        if not self._npcs:
            if step and self.tracer:
                self.tracer.end_step(step, details={"skipped": True, "npc_count": 0})
                trace.steps.append(step)  # type: ignore[union-attr]
            return

        tasks = []
        for npc_id, npc in self._npcs.items():
            tasks.append(self._process_single_npc(npc_id, npc, result))

        await asyncio.gather(*tasks, return_exceptions=True)

        if step and self.tracer:
            self.tracer.end_step(step, details={"npc_count": len(self._npcs), "actions": len(result.npc_actions)})
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
                    action = await self.npc_agent.decide(npc, self.world, observation)
                else:
                    # Default: follow schedule or idle
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
            story_beats = await self.story_director.process(
                result.world_events, self.world
            )
            result.story_beats = story_beats
            if step and self.tracer:
                self.tracer.end_step(step, details={"story_beats": len(story_beats)})
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
        """Step 12: Generate narrative text."""
        step = self.tracer.start_step("narrative") if self.tracer else None
        if self.narrator:
            try:
                result.narrative = await self.narrator.narrate(result, self.world)
            except Exception as e:
                logger.warning("Narrative generation failed: %s", e)
                result.errors.append(f"narrative: {e}")
        else:
            # Default: build simple narrative from events
            parts = []
            if result.player_action:
                parts.append(f"You {result.player_action.get('type', 'act')}.")
            if result.dice_result:
                parts.append(f"Roll: {result.dice_result.summary()}")
            for npc_act in result.npc_actions:
                parts.append(npc_act.get("description", ""))
            for evt in result.world_events[:5]:
                parts.append(evt.description)
            result.narrative = " ".join(p for p in parts if p)

        if step and self.tracer:
            self.tracer.end_step(step, details={"narrative_length": len(result.narrative)})
            trace.steps.append(step)  # type: ignore[union-attr]
