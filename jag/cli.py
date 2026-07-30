"""CLI interface for JAG: command-line RPG gameplay with rich output.

Driven by the new module-based engine: the Director conceives plot and solidifies
changes through tools, while the five modules hold all state.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from jag.config import GameConfig, load_config
from jag.engine import Game, load_demo_world

console = Console()


def print_banner() -> None:
    banner = Text()
    banner.append("  JAG  ", style="bold white on dark_red")
    banner.append(" — 导演驱动的开放世界RPG框架 ", style="dim")
    console.print(banner)
    console.print()


def print_status(status: dict[str, Any], game: Game) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("属性", style="cyan")
    table.add_column("数值", style="white")

    table.add_row("回合", str(status["turn"]))
    table.add_row("时间", status["time"])
    table.add_row("天数", str(status["day"]))
    table.add_row("季节", status["season"])
    table.add_row("位置", status["location"])
    table.add_row("生命", f"{status['health']}/{status['max_health']}")
    table.add_row("附近", "、".join(status.get("nearby_entities", [])) or "无")

    console.print(Panel(table, title="[bold]世界状态[/bold]", border_style="blue"))


def print_inventory(game: Game) -> None:
    inv = game.inventory
    if not inv.items and inv.gold == 0:
        console.print("[dim]你的背包是空的。[/dim]")
        return
    table = Table(title=f"背包（金币: {inv.gold}）", show_header=True)
    table.add_column("#", style="dim")
    table.add_column("物品", style="green")
    table.add_column("数量", style="white")
    table.add_column("类型", style="cyan")
    for i, it in enumerate(inv.items, 1):
        flag = " [已装备]" if it.equipped else ""
        table.add_row(str(i), f"{it.name}{flag}", str(it.quantity), it.item_type)
    console.print(table)


def print_narrative(text: str) -> None:
    console.print(Panel(text, title="[bold green]叙事[/bold green]", border_style="green"))


def print_help() -> None:
    help_text = """
[bold]指令:[/bold]
  [cyan]status[/cyan]       — 查看世界状态
  [cyan]inventory[/cyan]    — 查看背包
  [cyan]look[/cyan]         — 环顾四周
  [cyan]modules[/cyan]      — 查看五大模块提示词（导演所见）
  [cyan]wait[/cyan]         — 等待（推进时间）
  [cyan]wait N[/cyan]       — 等待N回合
  [cyan]save[/cyan]         — 保存游戏
  [cyan]load[/cyan]         — 加载游戏
  [cyan]help[/cyan]         — 显示帮助
  [cyan]quit/exit[/cyan]    — 退出游戏

[bold]行动:[/bold]
  直接用自然语言描述你想做的事！导演会构思情节，并通过工具固化影响。
  例如:
    "我想探索森林"
    "和商人对话"
    "用剑攻击哥布林"
"""
    console.print(Panel(help_text, title="[bold]帮助[/bold]", border_style="yellow"))


def print_modules(game: Game) -> None:
    """Show the prompt fragments each module would hand to the Director."""
    ss = game.self_state
    loc = game.location
    npc = game.npc
    console.print(Panel(game.worldview.to_prompt(), title="[bold]世界观模块[/bold]", border_style="purple"))
    console.print(Panel(loc.prompt_for_location(ss.current_location_id), title="[bold]地点模块(当前)[/bold]", border_style="blue"))
    console.print(Panel(npc.prompt_for_location(ss.current_location_id), title="[bold]NPC模块(当前)[/bold]", border_style="cyan"))
    console.print(Panel(ss.to_prompt(), title="[bold]自身状态模块[/bold]", border_style="yellow"))
    console.print(Panel(game.inventory.to_prompt(), title="[bold]背包模块[/bold]", border_style="green"))


async def game_loop(game: Game) -> None:
    print_banner()

    opening = await game.generate_opening()
    print_narrative(opening)
    console.print()
    console.print("[dim]输入 [cyan]help[/cyan] 查看指令，或直接描述你想做的事。[/dim]")
    console.print("[dim]输入 [cyan]modules[/cyan] 可查看各模块当前传给导演的提示词。[/dim]")
    console.print()

    while True:
        try:
            player_input = console.input("[bold green]> [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]再见，冒险者！[/yellow]")
            break

        if not player_input:
            continue

        cmd = player_input.lower().split()[0] if player_input else ""

        if cmd in ("quit", "exit", "q"):
            console.print("[yellow]再见，冒险者！[/yellow]")
            break
        elif cmd == "status":
            print_status(game.get_status(), game)
            continue
        elif cmd == "inventory":
            print_inventory(game)
            continue
        elif cmd == "modules":
            print_modules(game)
            continue
        elif cmd == "help":
            print_help()
            continue
        elif cmd == "save":
            path = player_input.split(maxsplit=1)[1] if len(player_input.split()) > 1 else "savegame.json"
            game.save_game(path)
            console.print(f"[green]游戏已保存至 {path}[/green]")
            continue
        elif cmd == "load":
            path = player_input.split(maxsplit=1)[1] if len(player_input.split()) > 1 else "savegame.json"
            if game.load_game(path):
                console.print(f"[green]游戏已从 {path} 加载[/green]")
                print_status(game.get_status(), game)
            else:
                console.print(f"[red]从 {path} 加载失败[/red]")
            continue
        elif cmd == "look":
            status = game.get_status()
            ss = game.self_state
            loc = game.location.get(ss.current_location_id)
            text = f"你环顾四周。你身处{status['location']}。{status.get('location_description', '')}"
            present = game.npc.at_location(ss.current_location_id)
            if present:
                text += "\n\n你看到:\n" + "\n".join(
                    f"  • {n.name}（{n.description}）" for n in present
                )
            else:
                text += "\n\n附近没有其他人。"
            if loc and loc.connected:
                names = [game.location.get(c).name if game.location.get(c) else c for c in loc.connected]
                text += "\n\n可前往: " + "、".join(names)
            print_narrative(text)
            continue
        elif cmd == "wait":
            parts = player_input.split()
            turns = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            result = await game.advance_world(turns)
            for n in result["narratives"]:
                print_narrative(n)
            continue

        # Process action via Director
        try:
            result = await game.process_action(player_input)
            print_narrative(result["narrative"])
            # surface tool solidification
            for tr in result.get("tool_results", []):
                mark = "[green]✓[/green]" if tr["ok"] else "[red]✗[/red]"
                console.print(f"[dim]{mark} {tr['tool']}: {tr['message']}[/dim]")
            opts = result.get("suggested_options", [])
            if opts:
                labels = "  ".join(f"[cyan]{o['label']}[/cyan]" for o in opts)
                console.print(f"[dim]建议: {labels}[/dim]")
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]错误: {e}[/red]")


@click.group(invoke_without_command=True)
@click.option("--config", "-c", default=None, help="配置文件路径（YAML）")
@click.pass_context
def main(ctx: click.Context, config: str | None) -> None:
    """JAG — 导演驱动的开放世界RPG框架。"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(play, config=config)


@main.command()
@click.option("--config", "-c", default=None, help="配置文件路径（YAML）")
def play(config: str | None) -> None:
    """开始新游戏（加载演示世界）。"""
    cfg = load_config(config)
    game = Game(config=cfg)
    load_demo_world(game.worldview, game.location, game.npc, game.self_state, game.inventory)
    console.print("[dim]已加载演示世界: 阿尔多利亚王国[/dim]")
    asyncio.run(game_loop(game))


@main.command()
def version() -> None:
    """显示版本信息。"""
    console.print("[bold]JAG[/bold] v0.2.0 — 导演驱动的开放世界RPG框架（模块化重构）")


@main.command()
@click.option("--host", "-h", default=None, help="服务监听地址")
@click.option("--port", "-p", default=None, type=int, help="服务监听端口")
@click.option("--config", "-c", default=None, help="配置文件路径（YAML）")
def web(host: str | None, port: int | None, config: str | None) -> None:
    """启动调试 Web 界面。"""
    from jag.web.server import run_server

    cfg = load_config(config)
    host = host or cfg.web_host
    port = port or cfg.web_port
    console.print(f"[bold]JAG[/bold] 启动调试界面: http://{host}:{port}")
    run_server(host=host, port=port, config=config)


if __name__ == "__main__":
    main()
