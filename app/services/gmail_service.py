import os
import re
import json
import base64
from pathlib import Path
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = Path(settings.credentials_dir) / "gmail_token.json"


def _get_flow() -> Flow:
    """Create OAuth2 flow from .env credentials."""
    client_config = {
        "web": {
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.gmail_redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = settings.gmail_redirect_uri
    return flow


def get_auth_url() -> str:
    """Generate OAuth consent URL."""
    flow = _get_flow()
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url


def exchange_code(code: str):
    """Exchange authorization code for tokens and save."""
    flow = _get_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    _save_token(creds)
    return creds


def _save_token(creds: Credentials):
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }))


def _load_creds() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None
    data = json.loads(TOKEN_PATH.read_text())
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
    return creds


def is_connected() -> bool:
    creds = _load_creds()
    return creds is not None and creds.valid


def scan_emails(max_results: int = 50) -> list[dict]:
    """Scan Gmail for payment-related emails."""
    creds = _load_creds()
    if not creds or not creds.valid:
        raise RuntimeError("Gmail not connected")

    service = build("gmail", "v1", credentials=creds)

    # Search for payment-related emails
    query = "subject:(payment OR sent you OR paid you OR deposit OR transfer OR venmo OR zelle OR cash app)"
    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    payments = []

    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="full"
        ).execute()

        parsed = _parse_payment_email(msg)
        if parsed:
            payments.append(parsed)

    return payments


def _parse_payment_email(msg: dict) -> dict | None:
    """Parse a Gmail message into a payment record."""
    msg_id = msg["id"]
    headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}

    sender = headers.get("from", "")
    subject = headers.get("subject", "")
    date = headers.get("date", "")

    # Try to parse date
    try:
        dt = parsedate_to_datetime(date)
        date = dt.isoformat()
    except Exception:
        pass

    # Get body text
    body = _get_body(msg["payload"])

    # Detect payment method
    method = _detect_method(sender, subject, body)
    if not method:
        return None

    # Extract amount
    amount = _extract_amount(subject + " " + body)
    if amount is None:
        return None

    return {
        "gmail_message_id": msg_id,
        "sender": sender[:200],
        "subject": subject[:300],
        "amount": amount,
        "payment_method": method,
        "date": date,
    }


def _get_body(payload: dict) -> str:
    """Extract plain text body from email payload."""
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        # Recurse into multipart
        if part.get("parts"):
            result = _get_body(part)
            if result:
                return result
    return ""


def _detect_method(sender: str, subject: str, body: str) -> str | None:
    """Detect payment method from email content."""
    combined = (sender + " " + subject + " " + body).lower()
    methods = [
        ("venmo", "Venmo"),
        ("zelle", "Zelle"),
        ("cash app", "Cash App"),
        ("cashapp", "Cash App"),
        ("square cash", "Cash App"),
        ("paypal", "PayPal"),
        ("apple pay", "Apple Pay"),
    ]
    for keyword, name in methods:
        if keyword in combined:
            return name
    return None


def _extract_amount(text: str) -> float | None:
    """Extract dollar amount from text using regex."""
    patterns = [
        r"\$\s*([\d,]+\.?\d*)",           # $50.00 or $1,000
        r"([\d,]+\.?\d*)\s*(?:dollars?|USD)",  # 50 dollars
        r"sent you\s*\$?([\d,]+\.?\d*)",   # sent you $50
        r"paid you\s*\$?([\d,]+\.?\d*)",   # paid you $50
        r"amount[:\s]*\$?([\d,]+\.?\d*)",  # amount: $50
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return None
