from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Import and start scheduler after DB is ready
    from app.services.scheduler import start_scheduler, stop_scheduler
    await start_scheduler()
    yield
    await stop_scheduler()


app = FastAPI(title="Sportsbook Dashboard", lifespan=lifespan)

# Routers
from app.routers import agents, payments, dashboard, gmail  # noqa: E402
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(gmail.router, prefix="/api/gmail", tags=["gmail"])

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(static_dir / "index.html"))
