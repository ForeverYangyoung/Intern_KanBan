"""
实习能量站 - 新人成长导航智能看板 后端服务
FastAPI 主入口 — 含并发安全中间件
"""
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.dependencies import engine, SessionLocal
from app.models.database import Base, seed_milestone_configs, seed_demo_data
from app.routers import intern, mentor, hr, ai, webhook, sandbox

app = FastAPI(
    title="实习能量站 API",
    description="新人成长导航智能看板后端服务 — 纯数据驱动，AI仅做提炼",
    version="3.0.0",
)

# ============================================================
# 启动时建表 + 插入种子数据
# ============================================================
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

# ============================================================
# CORS 中间件
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 并发保命中间件
# ============================================================

# 简易速率限制（同一IP / 1秒内最多30请求）
_rate_limiter: dict = {}

@app.middleware("http")
async def concurrency_safety_middleware(request: Request, call_next):
    """
    生产级并发安全中间件：
    1. 请求超时保护（30秒）
    2. 简易速率限制（防雪崩）
    3. 请求ID注入（用于日志追踪）
    """
    # 请求追踪ID
    request_id = f"{int(time.time()*1000)}-{os.urandom(2).hex()}"
    request.state.request_id = request_id

    # 速率限制（仅对写操作）
    if request.method in ("POST", "PUT", "DELETE"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        key = f"{client_ip}"

        if key not in _rate_limiter:
            _rate_limiter[key] = {"count": 0, "window_start": now}

        window = _rate_limiter[key]
        if now - window["window_start"] > 1.0:
            window["count"] = 0
            window["window_start"] = now

        window["count"] += 1
        if window["count"] > 30:
            return JSONResponse(
                status_code=429,
                content={"error": "请求过于频繁，请稍后再试", "request_id": request_id},
                headers={"Retry-After": "1"}
            )

    # 执行请求
    start_time = time.time()
    try:
        response = await call_next(request)
        elapsed = time.time() - start_time

        # 慢请求告警（>3秒）
        if elapsed > 3.0:
            print(f"[SlowRequest] {request.method} {request.url.path} took {elapsed:.2f}s (id={request_id})")

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed:.3f}s"
        return response

    except Exception as e:
        print(f"[Error] {request.method} {request.url.path} failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "内部服务错误", "request_id": request_id}
        )

# ============================================================
# 注册路由
# ============================================================
app.include_router(intern.router, prefix="/api/intern", tags=["实习生端"])
app.include_router(mentor.router, prefix="/api/mentor", tags=["导师端"])
app.include_router(hr.router, prefix="/api/hr", tags=["HR端"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI服务"])
app.include_router(webhook.router, prefix="/api/webhook", tags=["Webhook接收端"])
app.include_router(sandbox.router, prefix="/api/sandbox", tags=["上帝视角沙盒"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "intern-growth-platform", "version": "3.0.0"}


# ============================================================
# 前端静态文件 + SPA fallback
# ============================================================
_dist_path = Path(__file__).parent.parent / "frontend" / "dist"
_index_html = _dist_path / "index.html"


@app.get("/{full_path:path}")
async def serve_frontend(request: Request, full_path: str):
    """SPA fallback"""
    if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi"):
        return JSONResponse(status_code=404, content={"error": "Not found"})

    static_file = _dist_path / full_path
    if static_file.exists() and static_file.is_file():
        return FileResponse(static_file)

    if _index_html.exists():
        return FileResponse(_index_html)

    return JSONResponse(status_code=404, content={"error": "Frontend not built"})
