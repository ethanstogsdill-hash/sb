from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from app.services import gmail_service

router = APIRouter()


@router.get("/auth-url")
async def get_auth_url():
    try:
        url = gmail_service.get_auth_url()
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
async def oauth_callback(code: str):
    try:
        gmail_service.exchange_code(code)
        return HTMLResponse("""
            <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#1a202c;color:#e2e8f0">
                <h2>Gmail Connected!</h2>
                <p>You can close this window and return to the dashboard.</p>
                <script>setTimeout(()=>window.close(), 3000)</script>
            </body></html>
        """)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def gmail_status():
    return {"connected": gmail_service.is_connected()}
