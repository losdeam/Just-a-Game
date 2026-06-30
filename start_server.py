"""Simple server startup script that bypasses .env loading issues."""

from __future__ import annotations

import os
import sys

os.environ.pop("DOTENV", None)

from jag.config import GameConfig
from jag.web.server import create_app
import uvicorn


def main() -> None:
    config = GameConfig()
    config.llm.default.provider = "mock"
    config.llm.default.model = "mock"

    app = create_app(config)

    host = os.environ.get("WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB_PORT", "8080"))

    print(f"JAG Debug Server starting at http://{host}:{port}")
    print("Using Mock LLM (no API key required)")
    print("Press Ctrl+C to stop")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
