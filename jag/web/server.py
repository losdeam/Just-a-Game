"""FastAPI + WebSocket backend for JAG debug interface.

Wired to the new module-based engine: a single `Game` coordinator drives the
five modules through the Director. All endpoints mirror the previous API
surface so the static frontend keeps working unchanged.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from jag.config import GameConfig, LLMModuleConfig, load_config
from jag.engine import Game, create_world_from_tags, load_demo_world
from jag.engine.world_setup import TAG_CATALOG
from jag.llm import LiteLLMProvider

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: GameConfig | None = None) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="JAG Debug Server")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    cfg = config or load_config()
    game = Game(config=cfg)
    _world_initialized = False

    connections: list[WebSocket] = []

    async def _send(ws: WebSocket, payload: dict[str, Any]) -> None:
        await ws.send_text(json.dumps(payload, ensure_ascii=False))

    def _llm_configured() -> bool:
        c = game.config.llm.default
        return bool(c.api_key and c.api_key != "your-api-key-here" and c.provider != "mock")

    # ── HTTP routes ─────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/api/status")
    async def get_status() -> JSONResponse:
        return JSONResponse(game.get_status())

    @app.get("/api/history")
    async def get_history(limit: int = 50) -> JSONResponse:
        # Surface the narrative history (new engine has no tick tracer).
        items = game.history[-limit:]
        history = [
            {
                "turn": h["turn"],
                "player_input": h["input"],
                "narrative": h["narrative"],
                "tool_results": h.get("tool_results", []),
            }
            for h in items
        ]
        return JSONResponse(history)

    @app.get("/api/locations")
    async def get_locations() -> JSONResponse:
        return JSONResponse(game.get_locations_view())

    @app.get("/api/npcs")
    async def get_npcs() -> JSONResponse:
        return JSONResponse(game.get_npcs_view())

    @app.get("/api/config")
    async def get_config() -> JSONResponse:
        return JSONResponse(_masked_config(game.config))

    @app.post("/api/config")
    async def update_config(body: dict) -> JSONResponse:  # type: ignore[type-arg]
        try:
            _apply_config_updates(game.config, body)
            game.reinit_llm()
            return JSONResponse({"ok": True, "message": "配置已更新，LLM 已重新初始化"})
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "message": str(e)}, status_code=400)

    @app.get("/api/world/tags")
    async def get_world_tags() -> JSONResponse:
        return JSONResponse(TAG_CATALOG)

    @app.get("/api/llm/status")
    async def llm_status() -> JSONResponse:
        c = game.config.llm.default
        return JSONResponse({
            "configured": _llm_configured(),
            "provider": c.provider,
            "model": c.model,
        })

    @app.post("/api/llm/test")
    async def test_llm(body: dict) -> JSONResponse:  # type: ignore[type-arg]
        c = game.config.llm.default
        provider = body.get("provider") or c.provider
        model = body.get("model") or c.model
        api_key = body.get("api_key") or c.api_key
        api_base = body.get("api_base") or c.api_base

        if not api_key or api_key == "your-api-key-here" or "*" in api_key:
            return JSONResponse({"ok": False, "message": "未配置有效的 API Key"}, status_code=400)

        try:
            tester = LiteLLMProvider(model=model, provider=provider, api_key=api_key, api_base=api_base)
            result = await tester.complete("Say OK", system="Reply with exactly: OK")
            # Auto-apply tested config so runtime switches from Mock to real LLM
            game.config.llm.default.provider = provider
            game.config.llm.default.model = model
            game.config.llm.default.api_key = api_key
            game.config.llm.default.api_base = api_base
            game.reinit_llm()
            return JSONResponse({"ok": True, "message": f"连接成功！模型响应: {result.strip()[:100]}。配置已自动应用"})
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "message": f"连接失败: {e}"}, status_code=400)

    @app.post("/api/world/create")
    async def create_world(body: dict) -> JSONResponse:  # type: ignore[type-arg]
        nonlocal _world_initialized
        world_name = body.get("world_name", "")
        tags = body.get("tags", {})
        description = body.get("description", "")
        use_llm = body.get("use_llm", False)

        if not use_llm and description:
            use_llm = _llm_configured()
        if use_llm and not _llm_configured():
            return JSONResponse({
                "ok": False,
                "message": "使用 AI 生成需要配置 LLM API Key。请在配置设置中填写并测试连接。",
                "need_key": True,
            }, status_code=400)

        try:
            game.clear_world()
            result = create_world_from_tags(
                tags, description, game.worldview, game.location,
                game.npc, game.self_state, game.inventory,
            )
            result["ok"] = True
            if description and not _llm_configured():
                result["warning"] = "未配置 LLM API Key，已使用词条模板生成。配置后可获得 AI 驱动的自定义世界。"
            _world_initialized = True
            opening = await game.generate_opening()
            result["opening"] = opening
            result["suggested_options"] = game.get_suggested_options()
            return JSONResponse(result)
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "message": str(e)}, status_code=500)

    @app.post("/api/world/load_demo")
    async def load_demo() -> JSONResponse:
        nonlocal _world_initialized
        if not _world_initialized or not game.has_world():
            load_demo_world(game.worldview, game.location, game.npc, game.self_state, game.inventory)
            _world_initialized = True
        opening = await game.generate_opening()
        return JSONResponse({
            "ok": True, "message": "演示世界已加载",
            "opening": opening, "suggested_options": game.get_suggested_options(),
        })

    @app.get("/api/inventory")
    async def get_inventory() -> JSONResponse:
        return JSONResponse(game.get_inventory_view())

    @app.get("/api/suggested-options")
    async def get_suggested_options() -> JSONResponse:
        return JSONResponse({"ok": True, "options": game.get_suggested_options()})

    @app.get("/api/lore")
    async def get_lore() -> JSONResponse:
        return JSONResponse(game.get_lore_view())

    # ── WebSocket ───────────────────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        nonlocal _world_initialized
        await websocket.accept()
        connections.append(websocket)
        logger.info("WebSocket client connected")

        try:
            status = game.get_status()
            opening = ""
            if _world_initialized and game.has_world():
                opening = await game.generate_opening()
            await _send(websocket, {"type": "init", "status": status, "opening": opening})
        except Exception as e:  # noqa: BLE001
            logger.exception("WS init failed: %s", e)
            # Still send an init so the client isn't left hanging.
            try:
                await _send(websocket, {"type": "init", "status": game.get_status(), "opening": ""})
            except Exception:  # noqa: BLE001
                pass

        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "action":
                    player_input = msg.get("input", "")
                    if not player_input:
                        continue
                    try:
                        result = await game.process_action(player_input)
                        await _send(websocket, {
                            "type": "action_result",
                            "narrative": result["narrative"],
                            "status": result["status"],
                            "suggested_options": result["suggested_options"],
                        })
                    except Exception as e:  # noqa: BLE001
                        await _send(websocket, {"type": "error", "message": str(e)})

                elif msg_type == "wait":
                    turns = int(msg.get("turns", 1))
                    try:
                        result = await game.advance_world(turns)
                        await _send(websocket, {
                            "type": "wait_result",
                            "narratives": result["narratives"],
                            "status": result["status"],
                            "suggested_options": result["suggested_options"],
                        })
                    except Exception as e:  # noqa: BLE001
                        await _send(websocket, {"type": "error", "message": str(e)})

                elif msg_type == "status":
                    await _send(websocket, {"type": "status", "status": game.get_status()})

                elif msg_type == "history":
                    items = game.history[-50:]
                    history = [
                        {"turn": h["turn"], "player_input": h["input"],
                         "narrative": h["narrative"], "tool_results": h.get("tool_results", [])}
                        for h in items
                    ]
                    await _send(websocket, {"type": "history", "history": history})

                elif msg_type == "get_config":
                    await _send(websocket, {"type": "config", "config": _masked_config(game.config)})

                elif msg_type == "create_world":
                    world_name = msg.get("world_name", "")
                    tags = msg.get("tags", {})
                    description = msg.get("description", "")
                    use_llm = msg.get("use_llm", False)
                    if not use_llm and description:
                        use_llm = _llm_configured()
                    if use_llm and not _llm_configured():
                        await _send(websocket, {
                            "type": "error",
                            "message": "使用 AI 生成需要配置 LLM API Key。请在配置设置中填写并测试。",
                        })
                        continue
                    try:
                        await _send(websocket, {"type": "progress", "message": "正在构建世界观..."})
                        game.clear_world()
                        result = create_world_from_tags(
                            tags, description, game.worldview, game.location,
                            game.npc, game.self_state, game.inventory,
                        )
                        if description and not _llm_configured():
                            result["warning"] = "未配置 LLM API Key，已使用词条模板生成。"
                        _world_initialized = True
                        await _send(websocket, {"type": "progress", "message": "正在生成开场白..."})
                        opening = await game.generate_opening()
                        await _send(websocket, {
                            "type": "world_created",
                            "result": result,
                            "status": game.get_status(),
                            "opening": opening,
                            "suggested_options": game.get_suggested_options(),
                        })
                    except Exception as e:  # noqa: BLE001
                        await _send(websocket, {"type": "error", "message": f"世界创建失败: {e}"})

                elif msg_type == "load_demo":
                    if not _world_initialized or not game.has_world():
                        await _send(websocket, {"type": "progress", "message": "正在加载演示世界..."})
                        load_demo_world(game.worldview, game.location, game.npc, game.self_state, game.inventory)
                        _world_initialized = True
                    await _send(websocket, {"type": "progress", "message": "正在生成开场白..."})
                    opening = await game.generate_opening()
                    await _send(websocket, {
                        "type": "world_created",
                        "result": {"ok": True, "method": "demo",
                                   "world_name": game.worldview.world_name,
                                   "locations": len(game.location.locations),
                                   "npcs": len(game.npc.npcs)},
                        "status": game.get_status(),
                        "opening": opening,
                        "suggested_options": game.get_suggested_options(),
                    })

                elif msg_type == "update_config":
                    try:
                        _apply_config_updates(game.config, msg.get("config", {}))
                        game.reinit_llm()
                        await _send(websocket, {"type": "config_updated", "message": "配置已更新，LLM 已重新初始化"})
                    except Exception as e:  # noqa: BLE001
                        await _send(websocket, {"type": "error", "message": f"配置更新失败: {e}"})

        except WebSocketDisconnect:
            if websocket in connections:
                connections.remove(websocket)
            logger.info("WebSocket client disconnected")
        except Exception as e:  # noqa: BLE001
            if websocket in connections:
                connections.remove(websocket)
            logger.warning("WebSocket error: %s", e)

    return app


def _mask_key(key: str) -> str:
    if not key or len(key) <= 8:
        return "****"
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _masked_config(cfg: GameConfig) -> dict[str, Any]:
    data = cfg.model_dump()
    default = data.get("llm", {}).get("default", {})
    if default.get("api_key"):
        default["api_key"] = _mask_key(default["api_key"])
    for mod in data.get("llm", {}).get("modules", {}).values():
        if mod.get("api_key"):
            mod["api_key"] = _mask_key(mod["api_key"])
    return data


def _apply_config_updates(cfg: GameConfig, updates: dict) -> None:  # type: ignore[type-arg]
    llm = updates.get("llm", {})
    if llm:
        default = llm.get("default", {})
        for field in ("provider", "model", "api_key", "api_base", "temperature", "max_tokens"):
            if field in default:
                val = default[field]
                if val == "" or val is None:
                    continue
                if field == "api_key" and "*" in str(val):
                    continue
                setattr(cfg.llm.default, field, val)
        modules = llm.get("modules", {})
        for mod_name, mod_data in modules.items():
            if mod_name not in cfg.llm.modules:
                cfg.llm.modules[mod_name] = LLMModuleConfig()
            mod_cfg = cfg.llm.modules[mod_name]
            for field in ("provider", "model", "api_key", "api_base", "temperature", "max_tokens"):
                if field in mod_data:
                    val = mod_data[field]
                    if val == "" or val is None:
                        continue
                    if field == "api_key" and "*" in str(val):
                        continue
                    setattr(mod_cfg, field, val)

    db = updates.get("database", {})
    if db:
        for field in ("backend", "path", "url"):
            if field in db:
                setattr(cfg.database, field, db[field])

    for field in ("world_name", "world_data_dir", "max_chain_depth", "npc_concurrency",
                  "short_term_memory_size", "memory_compression_threshold"):
        if field in updates:
            setattr(cfg, field, updates[field])


def run_server(host: str | None = None, port: int | None = None, config: str | None = None) -> None:
    """Run the debug web server."""
    import uvicorn

    cfg = load_config(config)
    app = create_app(cfg)
    host = host or cfg.web_host
    port = port or cfg.web_port
    logger.info("Starting JAG debug server at http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
