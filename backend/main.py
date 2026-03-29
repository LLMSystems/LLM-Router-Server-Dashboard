import logging
import os
import httpx
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import config, embedding, llm, status, system

CONFIG_PATH = os.environ.get("LLM_ROUTER_SERVER_CONFIG_PATH", "config.yaml")

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        app.state.config = yaml.safe_load(f)
    app.state.config_path = CONFIG_PATH
    app.state.starting_models = set()
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=2.0),
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
        ),
    )
    logger.info(f"{CONFIG_PATH} 載入完成")    
    try:
        yield  
    finally:
        await app.state.http_client.aclose()
    logger.info("FastAPI app 正在關閉")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(config.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(embedding.router, prefix="/api")
app.include_router(llm.router, prefix="/api")