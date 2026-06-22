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
    banner.append(" — 智能体驱动开放世界RPG框架 ", style="dim")
    console.print(banner)
    console.print()


def print_status(status: dict[str, Any]) -> None:
    """Print game status in a nice panel."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("属性", style="cyan")
    table.add_column("数值", style="white")

    table.add_row("回合", str(status["turn"]))
    table.add_row("时间", status["time"])
    table.add_row("天数", str(status["day"]))
    table.add_row("季节", status["season"])
    table.add_row("位置", status["location"])
    table.add_row("NPC数量", str(status["npc_count"]))
    table.add_row("任务", str(status["active_quests"]))
    table.add_row("故事线", str(status["active_threads"]))

    console.print(Panel(table, title="[bold]世界状态[/bold]", border_style="blue"))


def print_inventory(inventory: list[str]) -> None:
    """Print player inventory."""
    if not inventory:
        console.print("[dim]你的背包是空的。[/dim]")
        return
    table = Table(title="背包", show_header=True)
    table.add_column("#", style="dim")
    table.add_column("物品", style="green")
    for i, item in enumerate(inventory, 1):
        table.add_row(str(i), item)
    console.print(table)


def print_narrative(text: str) -> None:
    """Print narrative text."""
    console.print(Panel(text, title="[bold green]叙事[/bold green]", border_style="green"))


def print_help() -> None:
    """Print help text."""
    help_text = """
[bold]指令:[/bold]
  [cyan]status[/cyan]       — 查看世界状态
  [cyan]inventory[/cyan]    — 查看背包
  [cyan]look[/cyan]         — 环顾四周
  [cyan]wait[/cyan]         — 等待（推进时间）
  [cyan]wait N[/cyan]       — 等待N回合
  [cyan]save[/cyan]         — 保存游戏
  [cyan]load[/cyan]         — 加载游戏
  [cyan]help[/cyan]         — 显示帮助
  [cyan]quit/exit[/cyan]    — 退出游戏

[bold]行动:[/bold]
  直接用自然语言描述你想做的事！
  例如:
    "我想探索森林"
    "和商人对话"
    "用剑攻击哥布林"
    "搜索房间寻找隐藏物品"
"""
    console.print(Panel(help_text, title="[bold]帮助[/bold]", border_style="yellow"))


async def game_loop(gm: GameMaster) -> None:
    """Main game loop."""
    print_banner()

    status = gm.get_status()
    loc_desc = status.get("location_description", "")
    console.print(f"[dim]你发现自己身处 [bold]{status['location']}[/bold]。[/dim]")
    if loc_desc:
        console.print(f"[dim]{loc_desc}[/dim]")
    console.print(f"[dim]现在是 {status['time']}，第{status['day']}天，{status['season']}。[/dim]")
    console.print()
    console.print("[dim]输入 [cyan]help[/cyan] 查看指令，或直接描述你想做的事。[/dim]")
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

        # Handle commands
        if cmd in ("quit", "exit", "q"):
            console.print("[yellow]再见，冒险者！[/yellow]")
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
            console.print(f"[green]游戏已保存至 {path}[/green]")
            continue
        elif cmd == "load":
            path = player_input.split(maxsplit=1)[1] if len(player_input.split()) > 1 else "savegame.json"
            if gm.load_game(path):
                console.print(f"[green]游戏已从 {path} 加载[/green]")
                print_status(gm.get_status())
            else:
                console.print(f"[red]从 {path} 加载失败[/red]")
            continue
        elif cmd == "look":
            player_input = "仔细环顾四周"
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
            console.print(f"[red]错误: {e}[/red]")


def setup_demo_world(gm: GameMaster) -> None:
    """Set up a basic demo world."""
    from jag.world.npc import NPC, ScheduleEntry
    from jag.world.world import WorldLocation, WorldRegion

    # Regions
    gm.setup_world(
        regions=[
            WorldRegion(id="kingdom", name="阿尔多利亚王国", description="一个位于荒野边缘的和平王国。", region_type="kingdom"),
        ],
        locations=[
            WorldLocation(id="town_square", name="城镇广场", description="阿尔多利亚繁华的中心。商贩们吆喝着叫卖，市民们忙碌地穿梭往来。", region_id="kingdom", location_type="outdoor", light_level=8),
            WorldLocation(id="tavern", name="金色酒壶", description="一家温暖的酒馆，弥漫着麦芽酒和烤肉的气味。冒险者们围坐在炉火旁分享故事。", region_id="kingdom", location_type="indoor", light_level=6),
            WorldLocation(id="market", name="集市街", description="一条长长的街道，两旁摆满了摊位，从新鲜农产品到异域工艺品应有尽有。", region_id="kingdom", location_type="outdoor", light_level=8),
            WorldLocation(id="forest_edge", name="森林边缘", description="文明世界与黑暗森林的交界处。扭曲的树木在前方投下阴影。", region_id="kingdom", location_type="outdoor", light_level=4, danger_level=3),
            WorldLocation(id="darkwood", name="暗木小径", description="一条穿过古老森林的狭窄小径。诡异的声响在林间回荡。", region_id="kingdom", location_type="outdoor", light_level=2, danger_level=5),
            WorldLocation(id="ruins", name="远古遗迹", description="布满青苔和藤蔓的石制建筑。阴影中有东西在闪烁。", region_id="kingdom", location_type="outdoor", light_level=3, danger_level=7),
        ],
        npcs=[
            NPC(
                id="innkeeper",
                name="贝尔塔",
                description="一位眼神和善的健壮妇女，经营着这家酒馆。",
                location_id="tavern",
                personality="friendly",
                goal="让酒馆生意兴隆，顾客满意",
                desires=["好故事", "美酒"],
                schedule=[
                    ScheduleEntry(hour_start=6, hour_end=22, activity="照看吧台", location_id="tavern"),
                    ScheduleEntry(hour_start=22, hour_end=6, activity="睡觉", location_id="tavern"),
                ],
            ),
            NPC(
                id="guard_captain",
                name="阿尔德里克爵士",
                description="一位身披旧铠的沧桑骑士，城镇卫队的队长。",
                location_id="town_square",
                personality="stern",
                goal="保护城镇免受威胁",
                fears=["辜负职责"],
                schedule=[
                    ScheduleEntry(hour_start=6, hour_end=12, activity="巡逻", location_id="town_square"),
                    ScheduleEntry(hour_start=12, hour_end=18, activity="训练新兵", location_id="market"),
                    ScheduleEntry(hour_start=18, hour_end=6, activity="休息", location_id="tavern"),
                ],
            ),
            NPC(
                id="merchant",
                name="泽菲尔",
                description="一位走南闯北的商人，眼光毒辣，口才了得。",
                location_id="market",
                personality="charming",
                goal="通过贸易积累财富",
                desires=["稀有文物", "金币"],
                schedule=[
                    ScheduleEntry(hour_start=8, hour_end=18, activity="贩卖货物", location_id="market"),
                    ScheduleEntry(hour_start=18, hour_end=8, activity="休息", location_id="tavern"),
                ],
            ),
        ],
        player_data={
            "location_id": "town_square",
            "inventory": ["生锈的铁剑", "皮甲", "面包", "10枚金币"],
            "name": "冒险者",
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
@click.option("--config", "-c", default=None, help="配置文件路径（YAML）")
@click.pass_context
def main(ctx: click.Context, config: str | None) -> None:
    """JAG — 智能体驱动开放世界RPG框架。"""
    if ctx.invoked_subcommand is None:
        # Default: start playing
        ctx.invoke(play, config=config)


@main.command()
@click.option("--config", "-c", default=None, help="配置文件路径（YAML）")
def play(config: str | None) -> None:
    """开始新游戏。"""
    cfg = load_config(config)

    gm = GameMaster(config=cfg)
    setup_demo_world(gm)

    console.print("[dim]正在设置演示世界...[/dim]")
    asyncio.run(game_loop(gm))


@main.command()
def version() -> None:
    """显示版本信息。"""
    console.print("[bold]JAG[/bold] v0.1.0 — 智能体驱动开放世界RPG框架")


@main.command()
@click.option("--host", "-h", default="127.0.0.1", help="服务监听地址")
@click.option("--port", "-p", default=8000, help="服务监听端口")
@click.option("--config", "-c", default=None, help="配置文件路径（YAML）")
def web(host: str, port: int, config: str | None) -> None:
    """启动调试 Web 界面。"""
    from jag.web.server import run_server

    console.print(f"[bold]JAG[/bold] 启动调试界面: http://{host}:{port}")
    run_server(host=host, port=port, config=config)


if __name__ == "__main__":
    main()
