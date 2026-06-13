"""
实习能量站 - 新人成长导航智能看板 后端服务
FastAPI 主入口
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.dependencies import engine, SessionLocal
from app.models.database import Base, seed_milestone_configs, seed_demo_data
from app.routers import intern, mentor, hr, ai, webhook, sandbox

app = FastAPI(
    title="实习能量站 API",
    description="新人成长导航智能看板后端服务 — 基于腾讯混元大模型",
    version="2.0.0",
)

# 启动时建表 + 插入种子数据
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_milestone_configs(db)
        seed_demo_data(db)
    finally:
        db.close()
    yield

app.router.lifespan_context = lifespan

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(intern.router, prefix="/api/intern", tags=["实习生端"])
app.include_router(mentor.router, prefix="/api/mentor", tags=["导师端"])
app.include_router(hr.router, prefix="/api/hr", tags=["HR端"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI服务"])
app.include_router(webhook.router, prefix="/api/webhook", tags=["Webhook接收端"])
app.include_router(sandbox.router, prefix="/api/sandbox", tags=["上帝视角沙盒"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "intern-growth-platform", "version": "2.0.0"}


# ============================================================
# 前端静态文件 + SPA fallback
# ============================================================

_dist_path = Path(__file__).parent.parent / "frontend" / "dist"
_index_html = _dist_path / "index.html"


@app.get("/{full_path:path}")
async def serve_frontend(request: Request, full_path: str):
    """SPA fallback：API 路径返回 404，其他路径返回 index.html"""
    # API 路径不处理（已由上面路由处理，这里不会走到）
    if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi"):
        return JSONResponse(status_code=404, content={"error": "Not found"})

    # 尝试匹配静态资源（js/css/img）
    static_file = _dist_path / full_path
    if static_file.exists() and static_file.is_file():
        return FileResponse(static_file)

    # SPA fallback：所有前端路由都返回 index.html
    if _index_html.exists():
        return FileResponse(_index_html)

    return JSONResponse(status_code=404, content={"error": "Frontend not built"})
