import argparse
import asyncio
import os
from contextlib import asynccontextmanager

import httpx
import uvicorn
import uvloop
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config_loader import load_config
from app.router import router

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=None)
    yield
    await app.state.http_client.aclose()


def create_app(config: dict) -> FastAPI:
    app = FastAPI(title="LLM Router API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.config = config
    app.include_router(router)
    
    return app

# --- support gunicorn ---
config_path = os.environ.get("CONFIG_PATH", "configs/config.yaml")
config = load_config(config_path)
app = create_app(config)

# --- CLI support ---
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, help="Path to config.yaml")
    args = parser.parse_args()

    if args.config:
        config_override = load_config(args.config)
        uvicorn.run(
            create_app(config_override),
            host=config_override.get("server", {}).get("host", "0.0.0.0"),
            port=config_override.get("server", {}).get("port", 8947),
            reload=False,
            loop=config_override.get("server", {}).get("loop", "uvloop"),
            log_level=config_override.get("server", {}).get("uvicorn_log_level", "info")
        )
    else:
        uvicorn.run(
            "main:app",
            host=config.get("server", {}).get("host", "0.0.0.0"),
            port=config.get("server", {}).get("port", 8947),
            reload=False,
            loop=config.get("server", {}).get("loop", "uvloop"),
            log_level=config.get("server", {}).get("uvicorn_log_level", "info")
        )

if __name__ == "__main__":
    main()