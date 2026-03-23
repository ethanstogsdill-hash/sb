"""Standalone scrape script — launches native Chrome via CDP to bypass Cloudflare."""
import json
import re
import sys
import os
import time
import subprocess
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9222


def main():
    site_url = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    profile_dir = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.path.dirname(__file__), "data", "chrome_profile")

    os.makedirs(profile_dir, exist_ok=True)

    cdp_port = CDP_PORT

    # Use 'start' command on Windows — subprocess.Popen doesn't work for Chrome CDP
    profile_abs = os.path.abspath(profile_dir)
    cmd = f'start "" "{CHROME_PATH}" --remote-debugging-port={cdp_port} --user-data-dir="{profile_abs}" --no-first-run --no-default-browser-check --window-position=-2000,-2000 "{site_url}"'
    os.system(cmd)

    # Wait for Chrome to start and CDP to be ready
    import urllib.request
    for attempt in range(15):
        time.sleep(1)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/version", timeout=2)
            break
        except Exception:
            continue
    else:
        print(json.dumps({"error": "Chrome failed to start with CDP"}), file=sys.stderr)
        sys.exit(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            # Login if needed
            if "login" in page.url.lower():
                page.locator("#ctl00_ContentSectionMisc_txtUser").fill(username)
                page.locator("#ctl00_ContentSectionMisc_txtPassword").fill(password)
                page.locator("a.btn-login").click()
                page.wait_for_timeout(5000)

                # Check for Cloudflare
                title = page.title()
                if "moment" in title.lower():
                    # Wait for CF to resolve (may need manual intervention on first run)
                    for _ in range(12):
                        time.sleep(5)
                        if "moment" not in page.title().lower():
                            break
                    else:
                        print(json.dumps({"error": "Cloudflare challenge not resolved. Run once with --headed to solve manually."}), file=sys.stderr)
                        sys.exit(1)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

            # We should be on the dashboard now
            if "dashboard" not in page.url.lower():
                print(json.dumps({"error": f"Unexpected page after login: {page.url}"}), file=sys.stderr)
                sys.exit(1)

            # Try to click "Last Week" stat box to switch period (This Week may be empty)
            try:
                last_week = page.locator("text=Last Week").first
                if last_week.is_visible():
                    last_week.click()
                    page.wait_for_timeout(3000)
                    page.wait_for_load_state("networkidle", timeout=15000)
                    print("DEBUG: Switched to Last Week view", file=sys.stderr)
            except Exception as e:
                print(f"DEBUG: Could not switch to Last Week: {e}", file=sys.stderr)

            # Wait for dashboard widgets to fully load
            page.wait_for_timeout(3000)

            # Scrape dashboard tables (top losers + top winners = all players)
            agents = scrape_dashboard(page)

            # If no agents found on dashboard, try Weekly Balance by Player page
            if not agents:
                print("DEBUG: No dashboard agents, trying Weekly Balance page...", file=sys.stderr)
                try:
                    page.evaluate("""
                        const links = document.querySelectorAll('a[href="/Forms/BettorBalance.aspx"]');
                        if (links.length > 0) links[0].click();
                    """)
                    page.wait_for_timeout(5000)
                    page.wait_for_load_state("networkidle", timeout=15000)
                    print(f"DEBUG: Balance page URL: {page.url}", file=sys.stderr)

                    if "login" not in page.url.lower():
                        agents = scrape_balance_table_as_agents(page)
                except Exception as e:
                    print(f"DEBUG: Balance page nav failed: {e}", file=sys.stderr)
            else:
                # Try to enrich with balance data
                try:
                    page.evaluate("""
                        const links = document.querySelectorAll('a[href="/Forms/BettorBalance.aspx"]');
                        if (links.length > 0) links[0].click();
                    """)
                    page.wait_for_timeout(5000)
                    page.wait_for_load_state("networkidle", timeout=15000)

                    if "login" not in page.url.lower():
                        balance_data = scrape_balance_table(page)
                        if balance_data:
                            agents = merge_data(agents, balance_data)
                except Exception:
                    pass

            print(json.dumps(agents))
            browser.close()

    finally:
        # Kill the Chrome instance we started
        try:
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True, timeout=5)
        except Exception:
            pass


def scrape_dashboard(page) -> list[dict]:
    """Scrape the top losers + top winners tables from dashboard."""
    agents = []
    seen_ids = set()
    tables = page.locator("table").all()

    print(f"DEBUG: Found {len(tables)} tables on dashboard", file=sys.stderr)

    for idx, table in enumerate(tables):
        rows = table.locator("tr").all()
        if len(rows) < 2:
            continue

        # Check headers
        header_cells = rows[0].locator("th").all()
        headers = [c.inner_text().strip().lower() for c in header_cells]
        print(f"DEBUG: Table {idx} headers={headers} rows={len(rows)}", file=sys.stderr)

        # Look for Agent/Player/Win-Loss tables (headers: ['agent', 'player', 'win / loss'])
        has_player = any("player" in h for h in headers)
        has_winloss = any("win" in h for h in headers)
        if not (has_player and has_winloss):
            continue

        for r in range(1, len(rows)):
            cells = rows[r].locator("td").all()
            if len(cells) < 3:
                continue
            agent_name = cells[0].inner_text().strip()
            player_id = cells[1].inner_text().strip()
            win_loss_text = cells[2].inner_text().strip()

            if player_id and player_id not in seen_ids:
                seen_ids.add(player_id)
                agents.append({
                    "account_id": player_id,
                    "account_name": player_id,
                    "win_loss": parse_number(win_loss_text),
                    "balance": 0,
                    "action": 0,
                    "raw_data": {
                        "agent": agent_name,
                        "player": player_id,
                        "win_loss": win_loss_text,
                        "source": "dashboard",
                    },
                })

    print(f"DEBUG: Scraped {len(agents)} agents from dashboard", file=sys.stderr)
    return agents


def scrape_balance_table_as_agents(page) -> list[dict]:
    """Scrape Weekly Balance by Player table and return as agent records."""
    data = scrape_balance_table(page)
    agents = []
    for d in data:
        agents.append({
            "account_id": d["player"],
            "account_name": d["player"],
            "win_loss": d.get("win_loss", 0),
            "balance": d.get("balance", 0),
            "action": d.get("action", 0),
            "raw_data": d,
        })
    return agents


def scrape_balance_table(page) -> list[dict]:
    """Scrape the Weekly Balance by Player table for balance/action data."""
    data = []
    tables = page.locator("table").all()

    for table in tables:
        rows = table.locator("tr").all()
        if len(rows) < 2:
            continue

        header_cells = rows[0].locator("th, td").all()
        headers = [c.inner_text().strip().lower() for c in header_cells]

        col_map = {}
        for i, h in enumerate(headers):
            if "player" in h or "name" in h or "account" in h:
                col_map["player"] = i
            elif "balance" in h or "bal" in h:
                col_map["balance"] = i
            elif "action" in h or "handle" in h or "volume" in h:
                col_map["action"] = i
            elif "win" in h and "loss" in h or "w/l" in h or "net" in h:
                col_map["win_loss"] = i

        if "player" not in col_map:
            continue

        for r in range(1, len(rows)):
            cells = rows[r].locator("td").all()
            if len(cells) < 2:
                continue
            entry = {"player": cells[col_map["player"]].inner_text().strip()}
            if "balance" in col_map and col_map["balance"] < len(cells):
                entry["balance"] = parse_number(cells[col_map["balance"]].inner_text().strip())
            if "action" in col_map and col_map["action"] < len(cells):
                entry["action"] = parse_number(cells[col_map["action"]].inner_text().strip())
            if "win_loss" in col_map and col_map["win_loss"] < len(cells):
                entry["win_loss"] = parse_number(cells[col_map["win_loss"]].inner_text().strip())
            data.append(entry)

        if data:
            break

    return data


def merge_data(agents: list[dict], balance_data: list[dict]) -> list[dict]:
    """Merge balance/action data into agent records."""
    balance_map = {d["player"]: d for d in balance_data}
    for agent in agents:
        extra = balance_map.get(agent["account_id"], {})
        if "balance" in extra:
            agent["balance"] = extra["balance"]
        if "action" in extra:
            agent["action"] = extra["action"]
        if "win_loss" in extra and agent["win_loss"] == 0:
            agent["win_loss"] = extra["win_loss"]
    return agents


def parse_number(text):
    if not text:
        return 0.0
    text = text.strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = re.sub(r"[^\d.\-]", "", text)
    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return 0.0


if __name__ == "__main__":
    main()
