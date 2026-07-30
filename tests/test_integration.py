"""Integration tests for the new module-based engine.

Covers: module prompts, tool solidification, the Director flow (mock LLM +
fallback), demo world loading, and persistence round-trip.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from jag.config import GameConfig, LLMConfig, LLMModuleConfig
from jag.director import Director
from jag.engine import Game, load_demo_world
from jag.llm import MockLLMProvider
from jag.modules import InventoryModule, ItemData, SelfStateModule
from jag.tools import build_default_registry


@pytest.fixture
def game_config() -> GameConfig:
    return GameConfig(
        world_name="Test World",
        llm=LLMConfig(default=LLMModuleConfig(provider="mock", model="mock")),
    )


@pytest.fixture
def game(game_config: GameConfig) -> Game:
    g = Game(config=game_config)
    load_demo_world(g.worldview, g.location, g.npc, g.self_state, g.inventory)
    return g


# ── Modules ──────────────────────────────────────────────────────────────


def test_worldview_prompt_has_name(game: Game) -> None:
    prompt = game.worldview.to_prompt()
    assert "阿尔多利亚王国" in prompt
    assert "【世界观】" in prompt


def test_location_prompt_for_current(game: Game) -> None:
    prompt = game.location.prompt_for_location(game.self_state.current_location_id)
    assert "城镇广场" in prompt
    assert "可前往" in prompt


def test_npc_at_location(game: Game) -> None:
    present = game.npc.at_location("town_square")
    assert any(n.name == "阿尔德里克爵士" for n in present)


def test_self_state_advances_time() -> None:
    ss = SelfStateModule()
    ss.advance_time(3)
    assert ss.turn == 3
    assert ss.hour == 11


def test_inventory_add_remove() -> None:
    inv = InventoryModule()
    inv.add(ItemData("bread", "面包", quantity=2, item_type="consumable"))
    assert inv.has("bread")
    assert inv.remove("bread", 1)
    assert inv.has("bread")
    assert inv.remove("bread", 1)
    assert not inv.has("bread")


# ── Tools ────────────────────────────────────────────────────────────────


def test_move_player_tool(game: Game) -> None:
    reg = build_default_registry()
    result = reg.execute("move_player", {"location_id": "tavern"}, game)
    assert result.ok
    assert game.self_state.current_location_id == "tavern"


def test_update_health_tool_clamps(game: Game) -> None:
    reg = build_default_registry()
    reg.execute("update_health", {"delta": -1000}, game)
    assert game.self_state.health == 0
    reg.execute("update_health", {"delta": 1000}, game)
    assert game.self_state.health == game.self_state.max_health


def test_add_npc_tool(game: Game) -> None:
    reg = build_default_registry()
    result = reg.execute("add_npc", {
        "id": "goblin", "name": "哥布林", "description": "丑陋的小怪物",
        "location_id": "forest_edge", "personality": "aggressive",
    }, game)
    assert result.ok
    assert game.npc.get("goblin") is not None


def test_registry_describes_all_tools() -> None:
    reg = build_default_registry()
    text = reg.describe_all()
    assert "update_worldview" in text
    assert "move_player" in text
    assert "add_npc" in text
    assert "add_item" in text


# ── Director + Game flow ─────────────────────────────────────────────────


def test_opening_generated(game: Game) -> None:
    opening = asyncio.run(game.generate_opening())
    assert isinstance(opening, str)
    assert len(opening) > 0


def test_process_action_returns_narrative_and_advances_time(game: Game) -> None:
    before = game.self_state.turn
    result = asyncio.run(game.process_action("我环顾四周"))
    assert "narrative" in result
    assert result["narrative"]
    assert game.self_state.turn == before + 1
    assert "status" in result
    assert "suggested_options" in result


def test_director_fallback_on_empty_decision(game: Game) -> None:
    # Mock LLM returns a default (empty) DirectorDecision -> fallback kicks in.
    director = Director(MockLLMProvider(), build_default_registry())
    decision = asyncio.run(director.process_action("做点什么", game))
    assert decision.narrative  # fallback narrative is non-empty


def test_director_executes_tool_calls(game: Game) -> None:
    """A scripted mock provider returns a decision with a tool call; the Director
    must execute it against the modules."""
    from jag.director.models import DirectorDecision, ToolCall

    class ScriptedMock(MockLLMProvider):
        async def structured(self, prompt, response_model, system="", **kwargs):  # type: ignore[override]
            return DirectorDecision(
                thoughts="移动到酒馆",
                narrative="你走进了金色酒壶。",
                tool_calls=[ToolCall(tool="move_player", args={"location_id": "tavern"})],
                suggested_options=["和贝尔塔交谈"],
            )

    director = Director(ScriptedMock(), build_default_registry())
    decision = asyncio.run(director.process_action("去酒馆", game))
    assert game.self_state.current_location_id == "tavern"
    assert decision.narrative == "你走进了金色酒壶。"


# ── Persistence ──────────────────────────────────────────────────────────


def test_save_load_roundtrip(game: Game) -> None:
    # play a couple of actions so history is non-empty
    asyncio.run(game.process_action("四处看看"))
    asyncio.run(game.process_action("走向集市"))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
    try:
        game.save_game(path)
        # mutate state
        game.self_state.health = 1
        game.self_state.current_location_id = "ruins"
        # reload
        assert game.load_game(path)
        assert game.self_state.health == 100
        assert game.self_state.current_location_id == "town_square"
        assert len(game.history) == 2
    finally:
        os.unlink(path)


# ── Status / views ───────────────────────────────────────────────────────


def test_status_shape(game: Game) -> None:
    status = game.get_status()
    for key in ("turn", "time", "day", "season", "location", "inventory",
                "health", "max_health", "nearby_entities"):
        assert key in status


def test_lore_view(game: Game) -> None:
    lore = game.get_lore_view()
    assert lore["world_name"] == "阿尔多利亚王国"
    assert len(lore["locations"]) == 6
    assert len(lore["npcs"]) == 3
