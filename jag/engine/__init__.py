"""Engine package: the central orchestration layer.

Replaces the old GameMaster + tick-engine with a single `Game` coordinator that
drives the five modules through the Director. See `game.py` for the flow.
"""

from __future__ import annotations

from .game import Game, create_game
from .world_setup import TAG_CATALOG, create_world_from_tags, load_demo_world

__all__ = [
    "Game",
    "create_game",
    "load_demo_world",
    "create_world_from_tags",
    "TAG_CATALOG",
]
