"""FastAPI + WebSocket backend for JAG debug interface."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


from jag.agents.game_master import GameMaster
from jag.cli import setup_demo_world
from jag.config import GameConfig, LLMModuleConfig, load_config
from jag.debug.tracer import TickTrace
from jag.skills import SkillContext, SkillRegistry
from jag.world.world_builder import WorldBuilder, get_all_tags

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: GameConfig | None = None) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="JAG Debug Server")

    # Static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Game state
    cfg = config or load_config()
    gm = GameMaster(config=cfg)
    world_builder = WorldBuilder(gm)
    _world_initialized = False  # Track if world has been set up

    # Initialize Skill Registry
    skill_registry = SkillRegistry.instance()
    skill_registry.register_defaults()

    def _ensure_world() -> None:
        """Ensure a world is loaded; does nothing if none was created."""
        pass  # World must be explicitly created via create_world or load_demo

    # WebSocket connections
    connections: list[WebSocket] = []

    async def broadcast_trace(trace: TickTrace) -> None:
        """Send trace data to all connected WebSocket clients."""
        data = json.dumps(trace.to_dict(), ensure_ascii=False)
        disconnected = []
        for ws in connections:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            connections.remove(ws)

    # Subscribe tracer to broadcast
    gm.tracer.subscribe(broadcast_trace)

    # ── Routes ────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        index_file = STATIC_DIR / "index.html"
        return index_file.read_text(encoding="utf-8")

    @app.get("/api/status")
    async def get_status() -> JSONResponse:
        _ensure_world()
        status = gm.get_status()
        return JSONResponse(status)

    @app.get("/api/history")
    async def get_history(limit: int = 50) -> JSONResponse:
        history = gm.tracer.get_history(limit)
        return JSONResponse(history)

    @app.get("/api/locations")
    async def get_locations() -> JSONResponse:
        _ensure_world()
        locs = []
        for loc_id, loc in gm.world.locations.items():
            locs.append({
                "id": loc_id,
                "name": loc.name,
                "description": loc.description,
                "type": loc.location_type,
                "light_level": loc.light_level,
                "danger_level": loc.danger_level,
                "connected": loc.connected,
                "entities": loc.entities,
                "items": loc.items,
            })
        return JSONResponse(locs)

    @app.get("/api/npcs")
    async def get_npcs() -> JSONResponse:
        _ensure_world()
        npcs = []
        for npc_id, npc in gm.tick_engine._npcs.items():
            npcs.append({
                "id": npc_id,
                "name": npc.name,
                "description": npc.description,
                "location_id": npc.state.current_location_id,
                "mood": npc.state.mood,
                "energy": round(npc.state.energy, 2),
                "hunger": round(npc.state.hunger, 2),
                "current_action": npc.state.current_action,
                "personality": npc.personality,
                "goal": npc.goal,
            })
        return JSONResponse(npcs)

    @app.get("/api/config")
    async def get_config() -> JSONResponse:
        """Return current configuration (API keys masked)."""
        cfg = gm.config
        data = cfg.model_dump()
        # Mask API keys for display
        if data.get("llm", {}).get("default", {}).get("api_key"):
            key = data["llm"]["default"]["api_key"]
            data["llm"]["default"]["api_key"] = _mask_key(key)
        for mod in data.get("llm", {}).get("modules", {}).values():
            if mod.get("api_key"):
                mod["api_key"] = _mask_key(mod["api_key"])
        return JSONResponse(data)

    @app.post("/api/config")
    async def update_config(body: dict) -> JSONResponse:  # type: ignore[type-arg]
        """Update runtime configuration and re-initialize LLM providers if needed."""
        try:
            _apply_config_updates(gm.config, body)
            gm.reinit_llm()
            return JSONResponse({"ok": True, "message": "配置已更新，LLM 已重新初始化"})
        except Exception as e:
            return JSONResponse({"ok": False, "message": str(e)}, status_code=400)

    @app.get("/api/world/tags")
    async def get_world_tags() -> JSONResponse:
        """Return available world-building tag categories."""
        return JSONResponse(get_all_tags())

    @app.get("/api/llm/status")
    async def llm_status() -> JSONResponse:
        """Check if LLM is configured and usable."""
        llm_cfg = gm.config.llm.default
        has_key = bool(llm_cfg.api_key and llm_cfg.api_key != "your-api-key-here")
        return JSONResponse({
            "configured": has_key,
            "provider": llm_cfg.provider,
            "model": llm_cfg.model,
        })

    @app.post("/api/llm/test")
    async def test_llm(body: dict) -> JSONResponse:  # type: ignore[type-arg]
        """Test if the LLM API key works by sending a simple prompt."""
        provider = body.get("provider", "")
        model = body.get("model", "")
        api_key = body.get("api_key", "")
        api_base = body.get("api_base", "") or None

        # Use current config if not provided
        llm_cfg = gm.config.llm.default
        provider = provider or llm_cfg.provider
        model = model or llm_cfg.model
        api_key = api_key or llm_cfg.api_key
        api_base = api_base or llm_cfg.api_base

        if not api_key or api_key == "your-api-key-here" or "*" in api_key:
            return JSONResponse({"ok": False, "message": "未配置有效的 API Key"}, status_code=400)

        try:
            from jag.agents.llm import LiteLLMProvider
            test_llm_provider = LiteLLMProvider(
                model=model, provider=provider, api_key=api_key, api_base=api_base,
            )
            result = await test_llm_provider.complete("Say OK", system="Reply with exactly: OK")
            
            # Auto-apply the tested config so runtime switches from Mock to real LLM
            gm.config.llm.default.provider = provider
            gm.config.llm.default.model = model
            gm.config.llm.default.api_key = api_key
            gm.config.llm.default.api_base = api_base
            gm.reinit_llm()
            
            return JSONResponse({"ok": True, "message": f"连接成功！模型响应: {result.strip()[:100]}。配置已自动应用"})
        except Exception as e:
            return JSONResponse({"ok": False, "message": f"连接失败: {e}"}, status_code=400)

    @app.post("/api/world/create")
    async def create_world(body: dict) -> JSONResponse:  # type: ignore[type-arg]
        """Create a custom world from tags and description via SkillRegistry."""
        nonlocal _world_initialized
        world_name = body.get("world_name", "")
        tags = body.get("tags", {})
        description = body.get("description", "")
        use_llm = body.get("use_llm", False)

        # Auto-enable LLM when description is provided
        llm_cfg = gm.config.llm.default
        has_key = bool(llm_cfg.api_key and llm_cfg.api_key != "your-api-key-here")

        if not use_llm and description:
            use_llm = has_key  # auto-use LLM if key available and description provided

        if use_llm and not has_key:
            return JSONResponse({
                "ok": False,
                "message": "使用 AI 生成需要配置 LLM API Key。请在配置设置中填写 API Key 并测试连接。",
                "need_key": True,
            }, status_code=400)

        try:
            # Use SkillRegistry to execute world generation
            skill_result = await skill_registry.execute(
                "world_generation",
                SkillContext(gm=gm, params={
                    "world_name": world_name,
                    "tags": tags,
                    "description": description,
                    "use_llm": use_llm,
                })
            )
            
            if not skill_result.success:
                return JSONResponse({"ok": False, "message": skill_result.error}, status_code=500)

            result = skill_result.data
            # Add warning if LLM not used
            if description and not has_key:
                result["warning"] = "未配置 LLM API Key，您的自定义描述无法用于 AI 生成，已使用词条模板生成。配置 API Key 后可获得 AI 驱动的自定义世界。"

            _world_initialized = True
            opening = await gm.generate_opening()
            options = await gm.get_suggested_options()
            result["opening"] = opening
            result["suggested_options"] = options
            # Include success flag for frontend
            result["ok"] = True
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({"ok": False, "message": str(e)}, status_code=500)

    @app.post("/api/world/load_demo")
    async def load_demo_world() -> JSONResponse:
        """Load the default demo world."""
        nonlocal _world_initialized
        if not _world_initialized:
            setup_demo_world(gm)
            _world_initialized = True
        opening = await gm.generate_opening()
        options = await gm.get_suggested_options()
        return JSONResponse({"ok": True, "message": "演示世界已加载", "opening": opening, "suggested_options": options})

    @app.get("/api/inventory")
    async def get_inventory() -> JSONResponse:
        _ensure_world()
        player = gm.world.characters.get(gm.player_id, {})
        return JSONResponse(player.get("inventory", []))
    
    @app.get("/api/suggested-options")
    async def get_suggested_options() -> JSONResponse:
        _ensure_world()
        try:
            options = await gm.get_suggested_options()
            return JSONResponse({"ok": True, "options": options})
        except Exception as e:
            return JSONResponse({"ok": False, "message": str(e)}, status_code=500)

    @app.get("/api/lore")
    async def get_lore() -> JSONResponse:
        _ensure_world()
        lore = gm.world_lore or {}
        
        # Format lore to match frontend expectations
        formatted = {
            "world_name": lore.get("world_name", gm.world_lore.get("name", "")),
            "description": lore.get("description", ""),
            "genre": lore.get("genre", ""),
            "era": lore.get("era", ""),
            "history": lore.get("history", ""),
            "main_quest": lore.get("main_quest", ""),
            "tags_applied": lore.get("tags", {}),
        }
        
        # Format NPCs
        formatted["npcs"] = []
        for npc in gm.tick_engine._npcs.values():
            formatted["npcs"].append({
                "name": npc.name,
                "role": getattr(npc, 'personality', 'NPC'),
                "location": npc.state.current_location_id,
            })
            
        # Format Locations
        formatted["locations"] = []
        for loc in gm.world.locations.values():
            formatted["locations"].append({
                "name": loc.name,
                "danger": loc.danger_level,
                "description": loc.description,
            })
            
        # Extract terrain/magic/danger from tags if available
        tags = lore.get("tags", {})
        if tags:
            formatted["terrain"] = ", ".join(tags.get("terrain", []))
            formatted["magic_level"] = ", ".join(tags.get("magic", []))
            formatted["danger_level"] = ", ".join(tags.get("danger", []))
            
        return JSONResponse(formatted)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        connections.append(websocket)
        logger.info("WebSocket client connected")

        # Send initial state
        try:
            status = gm.get_status()
            opening = await gm.generate_opening() if _world_initialized else ""
            await websocket.send_text(json.dumps({
                "type": "init",
                "status": status,
                "opening": opening,
            }, ensure_ascii=False))
        except Exception:
            pass

        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)

                msg_type = msg.get("type", "")

                if msg_type == "action":
                    _ensure_world()
                    player_input = msg.get("input", "")
                    if player_input:
                        try:
                            narrative, options = await gm.process_action(player_input)
                            status = gm.get_status()
                            await websocket.send_text(json.dumps({
                                "type": "action_result",
                                "narrative": narrative,
                                "status": status,
                                "suggested_options": options,
                            }, ensure_ascii=False))
                        except Exception as e:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": str(e),
                            }, ensure_ascii=False))

                elif msg_type == "wait":
                    _ensure_world()
                    turns = msg.get("turns", 1)
                    try:
                        narratives, options = await gm.advance_world(turns)
                        status = gm.get_status()
                        await websocket.send_text(json.dumps({
                            "type": "wait_result",
                            "narratives": narratives,
                            "status": status,
                            "suggested_options": options,
                        }, ensure_ascii=False))
                    except Exception as e:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": str(e),
                        }, ensure_ascii=False))

                elif msg_type == "status":
                    _ensure_world()
                    status = gm.get_status()
                    await websocket.send_text(json.dumps({
                        "type": "status",
                        "status": status,
                    }, ensure_ascii=False))

                elif msg_type == "history":
                    history = gm.tracer.get_history(50)
                    await websocket.send_text(json.dumps({
                        "type": "history",
                        "history": history,
                    }, ensure_ascii=False))

                elif msg_type == "get_config":
                    cfg_data = gm.config.model_dump()
                    if cfg_data.get("llm", {}).get("default", {}).get("api_key"):
                        key = cfg_data["llm"]["default"]["api_key"]
                        cfg_data["llm"]["default"]["api_key"] = _mask_key(key)
                    for mod in cfg_data.get("llm", {}).get("modules", {}).values():
                        if mod.get("api_key"):
                            mod["api_key"] = _mask_key(mod["api_key"])
                    await websocket.send_text(json.dumps({
                        "type": "config",
                        "config": cfg_data,
                    }, ensure_ascii=False))

                elif msg_type == "create_world":
                    world_name = msg.get("world_name", "")
                    tags = msg.get("tags", {})
                    description = msg.get("description", "")
                    use_llm = msg.get("use_llm", False)

                    llm_cfg = gm.config.llm.default
                    has_key = bool(llm_cfg.api_key and llm_cfg.api_key != "your-api-key-here")
                    if not use_llm and description:
                        use_llm = has_key

                    if use_llm and not has_key:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "使用 AI 生成需要配置 LLM API Key。请在配置设置中填写并测试。",
                        }, ensure_ascii=False))
                        continue

                    try:
                        await websocket.send_text(json.dumps({
                            "type": "progress",
                            "message": "正在通过 Skill 生成世界观...",
                        }, ensure_ascii=False))

                        # Use SkillRegistry to execute world generation
                        skill_result = await skill_registry.execute(
                            "world_generation",
                            SkillContext(gm=gm, params={
                                "world_name": world_name,
                                "tags": tags,
                                "description": description,
                                "use_llm": use_llm,
                            })
                        )

                        if not skill_result.success:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"世界观生成失败: {skill_result.error}",
                            }, ensure_ascii=False))
                            continue

                        result = skill_result.data
                        if description and not has_key:
                            result["warning"] = "未配置 LLM API Key，您的描述未用于 AI 生成。配置后可获得 AI 驱动的自定义世界。"
                            
                        _world_initialized = True
                        status = gm.get_status()
                        await websocket.send_text(json.dumps({
                            "type": "progress",
                            "message": "正在生成开场白...",
                        }, ensure_ascii=False))
                        opening = await gm.generate_opening()
                        options = await gm.get_suggested_options()
                        await websocket.send_text(json.dumps({
                            "type": "world_created",
                            "result": result,
                            "status": status,
                            "opening": opening,
                            "suggested_options": options,
                        }, ensure_ascii=False))
                    except Exception as e:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"世界创建失败: {e}",
                        }, ensure_ascii=False))

                elif msg_type == "load_demo":
                    if not _world_initialized:
                        await websocket.send_text(json.dumps({
                            "type": "progress",
                            "message": "正在加载演示世界...",
                        }, ensure_ascii=False))
                        setup_demo_world(gm)
                        _world_initialized = True
                    status = gm.get_status()
                    await websocket.send_text(json.dumps({
                        "type": "progress",
                        "message": "正在生成开场白...",
                    }, ensure_ascii=False))
                    opening = await gm.generate_opening()
                    options = await gm.get_suggested_options()
                    await websocket.send_text(json.dumps({
                        "type": "world_created",
                        "result": {"ok": True, "method": "demo"},
                        "status": status,
                        "opening": opening,
                        "suggested_options": options,
                    }, ensure_ascii=False))

                elif msg_type == "update_config":
                    try:
                        _apply_config_updates(gm.config, msg.get("config", {}))
                        gm.reinit_llm()
                        await websocket.send_text(json.dumps({
                            "type": "config_updated",
                            "message": "配置已更新，LLM 已重新初始化",
                        }, ensure_ascii=False))
                    except Exception as e:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"配置更新失败: {e}",
                        }, ensure_ascii=False))

        except WebSocketDisconnect:
            connections.remove(websocket)
            logger.info("WebSocket client disconnected")
        except Exception as e:
            if websocket in connections:
                connections.remove(websocket)
            logger.warning("WebSocket error: %s", e)

    return app


def _mask_key(key: str) -> str:
    """Mask an API key for display."""
    if not key or len(key) <= 8:
        return "****"
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _apply_config_updates(cfg: GameConfig, updates: dict) -> None:  # type: ignore[type-arg]
    """Apply partial config updates from a dict."""
    # LLM default
    llm = updates.get("llm", {})
    if llm:
        default = llm.get("default", {})
        for field in ("provider", "model", "api_key", "api_base", "temperature", "max_tokens"):
            if field in default:
                val = default[field]
                if val == "" or val is None:
                    continue
                # Don't overwrite with masked value
                if field == "api_key" and "*" in str(val):
                    continue
                setattr(cfg.llm.default, field, val)
        # Per-module overrides
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

    # Database
    db = updates.get("database", {})
    if db:
        for field in ("backend", "path", "url"):
            if field in db:
                setattr(cfg.database, field, db[field])

    # Game params
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
