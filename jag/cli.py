"""CLI interface for JAG: command-line RPG gameplay with rich output."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from jag.agents.game_master import GameMaster
from jag.config import GameConfig, load_config

console = Console()


def print_banner() -> None:
    """Print game banner."""
    banner = Text()
    banner.append("  JAG  ", style="bold white on dark_red")
    banner.append(" — Agentic Open World RPG Framework ", style="dim")
    console.print(banner)
    console.print()


def print_status(status: dict[str, Any]) -> None:
    """Print game status in a nice panel."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Turn", str(status["turn"]))
    table.add_row("Time", status["time"])
    table.add_row("Day", str(status["day"]))
    table.add_row("Season", status["season"])
    table.add_row("Location", status["location"])
    table.add_row("NPCs", str(status["npc_count"]))
    table.add_row("Quests", str(status["active_quests"]))
    table.add_row("Story Threads", str(status["active_threads"]))

    console.print(Panel(table, title="[bold]World Status[/bold]", border_style="blue"))


def print_inventory(inventory: list[str]) -> None:
    """Print player inventory."""
    if not inventory:
        console.print("[dim]Your inventory is empty.[/dim]")
        return
    table = Table(title="Inventory", show_header=True)
    table.add_column("#", style="dim")
    table.add_column("Item", style="green")
    for i, item in enumerate(inventory, 1):
        table.add_row(str(i), item)
    console.print(table)


def print_narrative(text: str) -> None:
    """Print narrative text."""
    console.print(Panel(text, title="[bold green]Narrative[/bold green]", border_style="green"))


def print_help() -> None:
    """Print help text."""
    help_text = """
[bold]Commands:[/bold]
  [cyan]status[/cyan]       — Show world status
  [cyan]inventory[/cyan]    — Show your inventory
  [cyan]look[/cyan]         — Look around
  [cyan]wait[/cyan]         — Wait (advance time)
  [cyan]wait N[/cyan]       — Wait N turns
  [cyan]save[/cyan]         — Save game
  [cyan]load[/cyan]         — Load game
  [cyan]help[/cyan]         — Show this help
  [cyan]quit/exit[/cyan]    — Quit the game

[bold]Actions:[/bold]
  Just type what you want to do in natural language!
  Examples:
    "I want to explore the forest"
    "Talk to the merchant"
    "Attack the goblin with my sword"
    "Search the room for hidden items"
"""
    console.print(Panel(help_text, title="[bold]Help[/bold]", border_style="yellow"))


async def game_loop(gm: GameMaster) -> None:
    """Main game loop."""
    print_banner()

    status = gm.get_status()
    loc_desc = status.get("location_description", "")
    console.print(f"[dim]You find yourself at [bold]{status['location']}[/bold].[/dim]")
    if loc_desc:
        console.print(f"[dim]{loc_desc}[/dim]")
    console.print(f"[dim]It is {status['time']}, day {status['day']} of {status['season']}.[/dim]")
    console.print()
    console.print("[dim]Type [cyan]help[/cyan] for commands, or just describe what you want to do.[/dim]")
    console.print()

    while True:
        try:
            player_input = console.input("[bold green]> [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Farewell, adventurer![/yellow]")
            break

        if not player_input:
            continue

        cmd = player_input.lower().split()[0] if player_input else ""

        # Handle commands
        if cmd in ("quit", "exit", "q"):
            console.print("[yellow]Farewell, adventurer![/yellow]")
            break
        elif cmd == "status":
            print_status(gm.get_status())
            continue
        elif cmd == "inventory":
            player = gm.world.characters.get(gm.player_id, {})
            print_inventory(player.get("inventory", []))
            continue
        elif cmd == "help":
            print_help()
            continue
        elif cmd == "save":
            path = player_input.split(maxsplit=1)[1] if len(player_input.split()) > 1 else "savegame.json"
            gm.save_game(path)
            console.print(f"[green]Game saved to {path}[/green]")
            continue
        elif cmd == "load":
            path = player_input.split(maxsplit=1)[1] if len(player_input.split()) > 1 else "savegame.json"
            if gm.load_game(path):
                console.print(f"[green]Game loaded from {path}[/green]")
                print_status(gm.get_status())
            else:
                console.print(f"[red]Failed to load from {path}[/red]")
            continue
        elif cmd == "look":
            player_input = "look around carefully"
        elif cmd == "wait":
            parts = player_input.split()
            turns = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            narratives = await gm.advance_world(turns)
            for n in narratives:
                print_narrative(n)
            continue

        # Process action
        try:
            narrative = await gm.process_action(player_input)
            print_narrative(narrative)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def setup_demo_world(gm: GameMaster) -> None:
    """Set up a basic demo world."""
    from jag.world.npc import NPC, ScheduleEntry
    from jag.world.world import WorldLocation, WorldRegion

    # Regions
    gm.setup_world(
        regions=[
            WorldRegion(id="kingdom", name="Kingdom of Aldoria", description="A peaceful kingdom on the edge of wildlands.", region_type="kingdom"),
        ],
        locations=[
            WorldLocation(id="town_square", name="Town Square", description="The bustling center of Aldoria. Merchants hawk their wares and townsfolk go about their day.", region_id="kingdom", location_type="outdoor", light_level=8),
            WorldLocation(id="tavern", name="The Golden Flagon", description="A warm tavern filled with the smell of ale and roasted meat. Adventurers share tales by the fire.", region_id="kingdom", location_type="indoor", light_level=6),
            WorldLocation(id="market", name="Market Street", description="A long street lined with stalls selling everything from fresh produce to exotic artifacts.", region_id="kingdom", location_type="outdoor", light_level=8),
            WorldLocation(id="forest_edge", name="Forest Edge", description="The border between civilization and the wild Darkwood. Twisted trees loom overhead.", region_id="kingdom", location_type="outdoor", light_level=4, danger_level=3),
            WorldLocation(id="darkwood", name="Darkwood Path", description="A narrow path through the ancient forest. Strange sounds echo between the trees.", region_id="kingdom", location_type="outdoor", light_level=2, danger_level=5),
            WorldLocation(id="ruins", name="Ancient Ruins", description="Crumbling stone structures covered in moss and vines. Something glimmers in the shadows.", region_id="kingdom", location_type="outdoor", light_level=3, danger_level=7),
        ],
        npcs=[
            NPC(
                id="innkeeper",
                name="Berta",
                description="A stout woman with kind eyes who runs the tavern.",
                location_id="tavern",
                personality="friendly",
                goal="Keep her tavern running and customers happy",
                desires=["good stories", "fine wine"],
                schedule=[
                    ScheduleEntry(hour_start=6, hour_end=22, activity="tending the bar", location_id="tavern"),
                    ScheduleEntry(hour_start=22, hour_end=6, activity="sleeping", location_id="tavern"),
                ],
            ),
            NPC(
                id="guard_captain",
                name="Sir Aldric",
                description="A grizzled knight in worn armor, captain of the town guard.",
                location_id="town_square",
                personality="stern",
                goal="Protect the town from threats",
                fears=["failing his duty"],
                schedule=[
                    ScheduleEntry(hour_start=6, hour_end=12, activity="patrolling", location_id="town_square"),
                    ScheduleEntry(hour_start=12, hour_end=18, activity="training recruits", location_id="market"),
                    ScheduleEntry(hour_start=18, hour_end=6, activity="resting", location_id="tavern"),
                ],
            ),
            NPC(
                id="merchant",
                name="Zephyr",
                description="A traveling merchant with an eye for rare goods and a silver tongue.",
                location_id="market",
                personality="charming",
                goal="Amass wealth through trade",
                desires=["rare artifacts", "gold"],
                schedule=[
                    ScheduleEntry(hour_start=8, hour_end=18, activity="selling wares", location_id="market"),
                    ScheduleEntry(hour_start=18, hour_end=8, activity="resting", location_id="tavern"),
                ],
            ),
        ],
        player_data={
            "location_id": "town_square",
            "inventory": ["rusty_sword", "leather_armor", "bread", "10 gold coins"],
            "name": "Adventurer",
            "type": "player",
        },
    )

    # Set up connections
    locs = gm.world.locations
    if "town_square" in locs:
        locs["town_square"].connected = ["tavern", "market", "forest_edge"]
    if "tavern" in locs:
        locs["tavern"].connected = ["town_square"]
    if "market" in locs:
        locs["market"].connected = ["town_square"]
    if "forest_edge" in locs:
        locs["forest_edge"].connected = ["town_square", "darkwood"]
    if "darkwood" in locs:
        locs["darkwood"].connected = ["forest_edge", "ruins"]
    if "ruins" in locs:
        locs["ruins"].connected = ["darkwood"]


@click.group(invoke_without_command=True)
@click.option("--config", "-c", default=None, help="Path to config YAML file")
@click.pass_context
def main(ctx: click.Context, config: str | None) -> None:
    """JAG — Agentic Open World RPG Framework."""
    if ctx.invoked_subcommand is None:
        # Default: start playing
        ctx.invoke(play, config=config)


@main.command()
@click.option("--config", "-c", default=None, help="Path to config YAML file")
def play(config: str | None) -> None:
    """Start a new game session."""
    cfg = load_config(config)

    # Force mock LLM for demo (no API key needed)
    from jag.config import LLMConfig as CfgLLM
    from jag.config import LLMModuleConfig
    cfg.llm = CfgLLM(
        default=LLMModuleConfig(provider="mock", model="mock"),
    )

    gm = GameMaster(config=cfg)
    setup_demo_world(gm)

    console.print("[dim]Setting up demo world...[/dim]")
    asyncio.run(game_loop(gm))


@main.command()
def version() -> None:
    """Show version information."""
    console.print("[bold]JAG[/bold] v0.1.0 — Agentic Open World RPG Framework")


if __name__ == "__main__":
    main()
