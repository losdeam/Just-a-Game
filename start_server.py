"""Simple server startup script."""

from __future__ import annotations

import os

from jag.config import load_config
from jag.web.server import create_app
import uvicorn


def main() -> None:
    config = load_config()

    app = create_app(config)

    host = os.environ.get("WEB_HOST", config.web_host)
    port = int(os.environ.get("WEB_PORT", str(config.web_port)))

    provider = config.llm.default.provider
    model = config.llm.default.model
    has_key = bool(config.llm.default.api_key and config.llm.default.api_key != "your-api-key-here")

    print(f"JAG Debug Server starting at http://{host}:{port}")
    if provider == "mock":
        print("Using Mock LLM (no API key required)")
    elif has_key:
        print(f"Using LLM: {provider}/{model}")
    else:
        print(f"LLM provider: {provider}/{model} (no API key configured)")
    print("Press Ctrl+C to stop")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
