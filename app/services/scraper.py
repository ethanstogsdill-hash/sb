import asyncio
import re
from playwright.async_api import async_playwright
from app.config import settings


async def scrape_agents() -> list[dict]:
    """Login to allagentreports.com, bypass Cloudflare, scrape agent/player table."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )

        # Stealth: remove webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            delete navigator.__proto__.webdriver;
        """)

        page = await context.new_page()

        try:
            # Navigate to login — wait for Cloudflare challenge to resolve
            await page.goto(settings.site_url, wait_until="networkidle", timeout=60000)
            # Give CF challenge extra time if needed
            await page.wait_for_timeout(3000)

            # Fill login form by input type (ASP.NET field names change)
            username_input = page.locator("input[type='text']").first
            password_input = page.locator("input[type='password']").first

            await username_input.fill(settings.site_username)
            await password_input.fill(settings.site_password)

            # Click submit button
            submit = page.locator("input[type='submit'], button[type='submit']").first
            await submit.click()

            # Wait for navigation after login
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # Navigate to the agent/player report page
            # Try common paths for agent reports
            current_url = page.url
            agents_data = []

            # Look for a link to player/agent reports
            report_link = page.locator("a:has-text('Player'), a:has-text('Agent'), a:has-text('Report')").first
            try:
                await report_link.click(timeout=5000)
                await page.wait_for_load_state("networkidle", timeout=15000)
                await page.wait_for_timeout(2000)
            except Exception:
                # If no link found, try direct URL patterns
                for path in ["/AgentPlayer.aspx", "/PlayerList.aspx", "/Reports.aspx"]:
                    try:
                        await page.goto(settings.site_url + path, wait_until="networkidle", timeout=15000)
                        break
                    except Exception:
                        continue

            # Extract table data
            agents_data = await _extract_table_data(page)

            return agents_data

        except Exception as e:
            raise RuntimeError(f"Scrape failed: {str(e)}")
        finally:
            await browser.close()


async def _extract_table_data(page) -> list[dict]:
    """Extract agent data from HTML tables on the page."""
    agents = []

    # Find all data tables
    tables = page.locator("table")
    table_count = await tables.count()

    for t in range(table_count):
        table = tables.nth(t)
        rows = table.locator("tr")
        row_count = await rows.count()

        if row_count < 2:
            continue

        # Get headers from first row
        header_row = rows.first
        headers = []
        header_cells = header_row.locator("th, td")
        header_count = await header_cells.count()
        for h in range(header_count):
            text = (await header_cells.nth(h).inner_text()).strip().lower()
            headers.append(text)

        if not headers:
            continue

        # Map headers to our fields
        col_map = _map_columns(headers)
        if not col_map.get("account_id") and not col_map.get("account_name"):
            continue  # Not the right table

        # Parse data rows
        for r in range(1, row_count):
            row = rows.nth(r)
            cells = row.locator("td")
            cell_count = await cells.count()

            if cell_count < 2:
                continue

            raw = {}
            for c in range(min(cell_count, len(headers))):
                text = (await cells.nth(c).inner_text()).strip()
                raw[headers[c]] = text

            agent = {
                "account_id": raw.get(headers[col_map["account_id"]], "") if col_map.get("account_id") is not None else "",
                "account_name": raw.get(headers[col_map["account_name"]], "") if col_map.get("account_name") is not None else "",
                "win_loss": _parse_number(raw.get(headers[col_map["win_loss"]], "0")) if col_map.get("win_loss") is not None else 0,
                "balance": _parse_number(raw.get(headers[col_map["balance"]], "0")) if col_map.get("balance") is not None else 0,
                "action": _parse_number(raw.get(headers[col_map["action"]], "0")) if col_map.get("action") is not None else 0,
                "raw_data": raw,
            }

            if agent["account_id"] or agent["account_name"]:
                # Use account_name as fallback ID
                if not agent["account_id"]:
                    agent["account_id"] = agent["account_name"]
                agents.append(agent)

        if agents:
            break  # Found the main data table

    return agents


def _map_columns(headers: list[str]) -> dict:
    """Map table headers to our field names."""
    col_map = {}
    patterns = {
        "account_id": ["id", "account id", "acct id", "player id", "userid"],
        "account_name": ["name", "account", "player", "username", "account name", "player name"],
        "win_loss": ["win/loss", "win loss", "w/l", "net", "winloss", "win_loss", "profit"],
        "balance": ["balance", "bal", "credit"],
        "action": ["action", "volume", "handle", "total action", "wager"],
    }

    for field, keywords in patterns.items():
        for i, header in enumerate(headers):
            if any(kw in header for kw in keywords):
                col_map[field] = i
                break

    return col_map


def _parse_number(text: str) -> float:
    """Parse a number string, handling currency symbols and parentheses for negatives."""
    if not text:
        return 0.0
    text = text.strip()
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = re.sub(r"[^\d.\-]", "", text)
    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return 0.0
