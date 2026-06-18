"""Integration tests for the full JAG game loop."""

from __future__ import annotations

import asyncio

import pytest

from jag.agents.game_master import GameMaster
from jag.config import GameConfig, LLMConfig, LLMModuleConfig
from jag.demo import WorldLoader, load_factions, load_items, load_locations, load_npcs, load_regions, setup_economy


@pytest.fixture
def game_config() -> GameConfig:
    """Create a test game config with mock LLM."""
    return GameConfig(
        world_name="Test World",
        llm=LLMConfig(
            default=LLMModuleConfig(provider="mock", model="mock"),
        ),
    )


@pytest.fixture
def game_master(game_config: GameConfig) -> GameMaster:
    """Create a GameMaster with demo world loaded."""
    gm = GameMaster(config=game_config)

    regions = load_regions()
    locations = load_locations()
    npcs = load_npcs()

    gm.setup_world(
        regions=regions,
        locations=locations,
        npcs=npcs,
        player_data={
            "location_id": "village_square",
            "inventory": ["rusty_sword", "10 gold coins"],
            "name": "Test Adventurer",
            "type": "player",
        },
    )

    # Set up economy
    setup_economy(gm.economy, locations)

    # Set up factions
    factions, relations = load_factions()
    for f in factions:
        gm.faction.add_faction(f)
    for r in relations:
        gm.faction.set_relation(r["faction_a"], r["faction_b"], r["relation"])

    return gm


class TestWorldLoader:
    """Test the demo world loader."""

    def test_load_regions(self):
        regions = load_regions()
        assert len(regions) >= 2
        ids = {r.id for r in regions}
        assert "greystone" in ids
        assert "darkwood" in ids

    def test_load_locations(self):
        locations = load_locations()
        assert len(locations) >= 6
        ids = {loc.id for loc in locations}
        assert "village_square" in ids
        assert "tavern" in ids
        assert "forest_path" in ids

    def test_load_npcs(self):
        npcs = load_npcs()
        assert len(npcs) >= 4
        names = {n.name for n in npcs}
        assert "玛拉" in names
        assert "杜兰" in names

    def test_load_items(self):
        items = load_items()
        assert len(items) >= 5
        ids = {i.id for i in items}
        assert "iron_sword" in ids
        assert "healing_potion" in ids

    def test_load_factions(self):
        factions, relations = load_factions()
        assert len(factions) >= 2
        assert len(relations) >= 1

    def test_world_loader_validate(self):
        loader = WorldLoader()
        data = loader.load_all()
        errors = loader.validate(data)
        assert len(errors) == 0, f"Validation errors: {errors}"


class TestGameLoop:
    """Test the full game loop."""

    @pytest.mark.asyncio
    async def test_basic_action(self, game_master: GameMaster):
        """Test processing a basic action."""
        result = await game_master.process_action("look around")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_move_action(self, game_master: GameMaster):
        """Test moving to a new location."""
        result = await game_master.process_action("go to the tavern")
        assert isinstance(result, str)
        # Player should have attempted to move
        status = game_master.get_status()
        assert status["turn"] >= 1

    @pytest.mark.asyncio
    async def test_multiple_turns(self, game_master: GameMaster):
        """Test running multiple turns."""
        actions = [
            "look at the fountain",
            "talk to the innkeeper",
            "go to the market",
            "examine the goods",
            "head to the village gate",
        ]
        for action in actions:
            result = await game_master.process_action(action)
            assert isinstance(result, str)

        status = game_master.get_status()
        assert status["turn"] >= 5

    @pytest.mark.asyncio
    async def test_advance_world(self, game_master: GameMaster):
        """Test advancing world without player action."""
        narratives = await game_master.advance_world(3)
        assert len(narratives) == 3
        assert all(isinstance(n, str) for n in narratives)

    @pytest.mark.asyncio
    async def test_game_status(self, game_master: GameMaster):
        """Test getting game status."""
        status = game_master.get_status()
        assert "turn" in status
        assert "location" in status
        assert "npc_count" in status
        assert status["npc_count"] >= 4

    @pytest.mark.asyncio
    async def test_save_load(self, game_master: GameMaster, tmp_path):
        """Test saving and loading game."""
        save_path = str(tmp_path / "test_save.json")

        # Play a few turns first
        await game_master.process_action("look around")
        await game_master.process_action("wait")

        # Save
        game_master.save_game(save_path)

        # Load
        success = game_master.load_game(save_path)
        assert success

    @pytest.mark.asyncio
    async def test_20_turn_integration(self, game_master: GameMaster):
        """Integration test: run 20+ turns and verify consistency."""
        actions = [
            "explore the village square",
            "talk to the villagers",
            "go to the tavern",
            "order a drink",
            "listen to stories",
            "go to the blacksmith",
            "examine the weapons",
            "go to the market",
            "buy some supplies",
            "head to the village gate",
            "look into the forest",
            "venture into the forest",
            "search for tracks",
            "find the hidden camp",
            "investigate the camp",
            "head to the ruins",
            "examine the ancient runes",
            "return to the forest path",
            "go back to the village",
            "rest at the tavern",
        ]

        errors = []
        for i, action in enumerate(actions):
            try:
                result = await game_master.process_action(action)
                assert isinstance(result, str), f"Turn {i+1}: narrative is not a string"
            except Exception as e:
                errors.append(f"Turn {i+1} ({action}): {e}")

        assert not errors, f"Errors during integration: {errors}"

        status = game_master.get_status()
        assert status["turn"] >= 20, f"Expected 20+ turns, got {status['turn']}"

        # Verify world state consistency
        assert len(game_master.world.characters) > 0
        assert len(game_master.world.locations) >= 6
        assert game_master.world.time.turn >= 20
