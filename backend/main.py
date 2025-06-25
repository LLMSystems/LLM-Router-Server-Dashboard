from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import config, status, system, embedding, llm
import yaml
from contextlib import asynccontextmanager

CONFIG_PATH = "config.yaml"

@asynccontextmanager
async def lifespan(app: FastAPI):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        app.state.config = yaml.safe_load(f)
    app.state.config_path = CONFIG_PATH
    app.state.starting_models = set()
    print("config.yaml 載入完成")    
    yield  
    
    print("FastAPI app 正在關閉")

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
#  uvicorn main:app --reload --host 0.0.0.0 --port 5000