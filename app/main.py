"""SmartExec — AI Shaker Backend API."""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smartexec")

app = FastAPI(title="SmartExec API", version="1.0.0")

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    from app.database import init_db

    init_db()
    logger.info("Database initialized and seeded.")


# ── Routers ──────────────────────────────────────────────────────────

from app.api.dashboard_api import router as dashboard_router  # noqa: E402
from app.api.line_handler import router as line_router  # noqa: E402
from app.api.menu_factory_api import router as factory_router  # noqa: E402

app.include_router(line_router)
app.include_router(dashboard_router, prefix="/api")
app.include_router(factory_router, prefix="/api/menu-factory")

# ── Static files (dashboard HTML) ───────────────────────────────────

browser_dir = os.path.join(os.path.dirname(__file__), "browser")
if os.path.isdir(browser_dir):
    app.mount("/browser", StaticFiles(directory=browser_dir, html=True), name="browser")


# ── Root endpoint ────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "SmartExec API is running", "version": "1.0.0"}


@app.get("/tenants/{tenant_id}/status")
def tenant_status(tenant_id: str):
    from app.database import SessionLocal
    from app.models.core import Tenant, TenantMenu

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            return JSONResponse(status_code=404, content={"error": "Tenant not found"})
        menus = db.query(TenantMenu).filter_by(tenant_id=tenant_id, status="enabled").all()
        return {
            "tenant_id": tenant.id,
            "name": tenant.name,
            "enabled_menus": [m.menu_id for m in menus],
        }
    finally:
        db.close()


# ── Global exception handler ────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error: %s %s — %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
