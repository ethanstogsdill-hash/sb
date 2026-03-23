import asyncio
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from app.config import settings

WORKER_SCRIPT = str(Path(__file__).parent.parent.parent / "scrape_worker.py")
PYTHON_EXE = sys.executable
PROFILE_DIR = str(Path(__file__).parent.parent.parent / "data" / "chrome_profile")
_executor = ThreadPoolExecutor(max_workers=1)


async def scrape_all() -> dict:
    """Run scrape_worker.py and return {"agents": [...], "wagers": [...]}."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_worker_v2)


async def scrape_agents() -> list[dict]:
    """Backward-compatible wrapper — returns only agents."""
    data = await scrape_all()
    return data["agents"]


def _run_worker_v2() -> dict:
    result = subprocess.run(
        [PYTHON_EXE, WORKER_SCRIPT,
         settings.site_url, settings.site_username, settings.site_password, PROFILE_DIR],
        capture_output=True, text=True, timeout=300,
    )

    if result.returncode != 0:
        err = result.stderr.strip()
        try:
            err_data = json.loads(err)
            raise RuntimeError(err_data.get("error", err))
        except json.JSONDecodeError:
            raise RuntimeError(f"Scrape failed: {err}")

    parsed = json.loads(result.stdout)

    # Backward compat: if output is a plain list, wrap it
    if isinstance(parsed, list):
        return {"agents": parsed, "wagers": []}
    return parsed
