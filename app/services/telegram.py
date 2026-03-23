import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"


async def send_message(text: str) -> bool:
    """Send a message via Telegram Bot API. Returns True on success."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.debug("Telegram not configured, skipping message")
        return False

    url = f"{API_BASE.format(token=settings.telegram_bot_token)}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


async def send_bet_alerts(new_bets: list[dict]):
    """Send Telegram notifications for newly detected bets."""
    if not new_bets:
        return

    if len(new_bets) > 5:
        # Summary message to avoid spam
        total_risk = sum(b.get("risk", 0) for b in new_bets)
        text = (
            f"<b>🎰 {len(new_bets)} New Bets Detected</b>\n"
            f"Total risked: ${total_risk:,.2f}\n\n"
        )
        # List first 5 briefly
        for b in new_bets[:5]:
            player = b.get("player_id", "Unknown")
            desc = b.get("description", "")[:40]
            text += f"• {player}: {desc}\n"
        text += f"...and {len(new_bets) - 5} more"
        await send_message(text)
    else:
        for b in new_bets:
            player = b.get("player_id", "Unknown")
            sport = b.get("sport", "N/A")
            desc = b.get("description", "N/A")
            risk = b.get("risk", 0)
            win = b.get("win_amount", 0)
            text = (
                f"<b>New Bet 🎰</b>\n"
                f"Player: {player}\n"
                f"Sport: {sport}\n"
                f"Pick: {desc}\n"
                f"Risk: ${risk:,.2f} → Win: ${win:,.2f}"
            )
            await send_message(text)
