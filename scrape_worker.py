"""Standalone scrape script — launches native Chrome via CDP to bypass Cloudflare."""
import hashlib
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
    cmd = f'start "" "{CHROME_PATH}" --remote-debugging-port={cdp_port} --user-data-dir="{profile_abs}" --no-first-run --no-default-browser-check "{site_url}"'
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

            # Wait for Cloudflare challenge to resolve BEFORE trying login
            for attempt in range(20):
                title = page.title().lower()
                url = page.url.lower()
                print(f"DEBUG: attempt={attempt} title='{page.title()}' url='{page.url}'", file=sys.stderr)
                if "moment" in title or "checking" in title or "challenge" in url or "cloudflare" in title:
                    print("DEBUG: Cloudflare challenge detected, waiting...", file=sys.stderr)
                    time.sleep(5)
                    continue
                break
            else:
                print(json.dumps({"error": "Cloudflare challenge not resolved after 100s. Run once with visible Chrome to solve manually."}), file=sys.stderr)
                sys.exit(1)

            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # Login if needed
            if "login" in page.url.lower():
                # Wait for the login form to actually appear in DOM
                try:
                    page.locator("#ctl00_ContentSectionMisc_txtUser").wait_for(state="visible", timeout=30000)
                except Exception:
                    # Dump page info for debugging
                    print(f"DEBUG: Login form not found. URL={page.url} Title={page.title()}", file=sys.stderr)
                    print(f"DEBUG: Page HTML (first 2000 chars): {page.content()[:2000]}", file=sys.stderr)
                    print(json.dumps({"error": f"Login form not found on page: {page.url}"}), file=sys.stderr)
                    sys.exit(1)

                page.locator("#ctl00_ContentSectionMisc_txtUser").fill(username)
                page.locator("#ctl00_ContentSectionMisc_txtPassword").fill(password)
                page.locator("a.btn-login").click()
                page.wait_for_timeout(5000)

                # Check if Cloudflare appeared after login click
                title = page.title()
                if "moment" in title.lower():
                    for _ in range(12):
                        time.sleep(5)
                        if "moment" not in page.title().lower():
                            break
                    else:
                        print(json.dumps({"error": "Cloudflare challenge after login not resolved."}), file=sys.stderr)
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

            # Scrape individual wagers
            wagers = []
            try:
                wagers = scrape_wagers(page)
                print(f"DEBUG: Scraped {len(wagers)} wagers", file=sys.stderr)
            except Exception as e:
                print(f"DEBUG: Wager scrape failed: {e}", file=sys.stderr)

            print(json.dumps({"agents": agents, "wagers": wagers}))
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


def scrape_wagers(page) -> list[dict]:
    """Navigate to Wagers Live page and scrape individual bet records."""
    # Click Reports → Wagers → Wagers Live
    try:
        wager_link = page.locator("a[href*='Wager']").first
        wager_link.click()
        page.wait_for_timeout(3000)
        page.wait_for_load_state("networkidle", timeout=15000)

        # Look for Wagers Live sub-link
        live_link = page.locator("a[href*='WagersLive'], a[href*='wagerlive'], a[href*='WagerLive']").first
        if live_link.is_visible():
            live_link.click()
            page.wait_for_timeout(3000)
            page.wait_for_load_state("networkidle", timeout=15000)
    except Exception as e:
        print(f"DEBUG: Wager navigation error: {e}", file=sys.stderr)
        # Try direct navigation via evaluate
        try:
            page.evaluate("""
                const links = [...document.querySelectorAll('a')];
                const wl = links.find(a => /wager.*live/i.test(a.textContent) || /WagersLive/i.test(a.href));
                if (wl) wl.click();
            """)
            page.wait_for_timeout(5000)
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e2:
            print(f"DEBUG: Wager fallback navigation error: {e2}", file=sys.stderr)
            return []

    print(f"DEBUG: Wager page URL: {page.url}", file=sys.stderr)

    wagers = []
    tables = page.locator("table").all()

    for table in tables:
        rows = table.locator("tr").all()
        if len(rows) < 2:
            continue

        header_cells = rows[0].locator("th, td").all()
        headers = [c.inner_text().strip().lower() for c in header_cells]

        # Fuzzy column matching
        col_map = {}
        for i, h in enumerate(headers):
            if "ticket" in h or h == "#" or h == "no":
                col_map["ticket_id"] = i
            elif "date" in h or "time" in h:
                col_map.setdefault("placed_at", i)
            elif "player" in h or "account" in h:
                col_map["player_id"] = i
            elif "sport" in h:
                col_map["sport"] = i
            elif "desc" in h or "event" in h or "selection" in h:
                col_map["description"] = i
            elif "type" in h or "wager" in h:
                col_map["bet_type"] = i
            elif "risk" in h or "stake" in h:
                col_map["risk"] = i
            elif "win" in h and "loss" not in h:
                col_map["win_amount"] = i
            elif "result" in h or "status" in h:
                col_map["result"] = i

        # Need at least player + one value column to consider this a wagers table
        if "player_id" not in col_map:
            continue

        print(f"DEBUG: Wager table headers={headers} col_map={col_map}", file=sys.stderr)

        for r in range(1, len(rows)):
            cells = rows[r].locator("td").all()
            if len(cells) < 3:
                continue

            def get_cell(key):
                idx = col_map.get(key)
                if idx is not None and idx < len(cells):
                    return cells[idx].inner_text().strip()
                return ""

            player_id = get_cell("player_id")
            if not player_id:
                continue

            ticket_id = get_cell("ticket_id")
            placed_at = get_cell("placed_at")
            sport = get_cell("sport")
            description = get_cell("description")
            bet_type = get_cell("bet_type")
            risk = parse_number(get_cell("risk"))
            win_amount = parse_number(get_cell("win_amount"))
            result = normalize_result(get_cell("result"))

            # Generate synthetic ticket_id if missing
            if not ticket_id:
                hash_input = f"{player_id}|{placed_at}|{description}|{risk}"
                ticket_id = hashlib.md5(hash_input.encode()).hexdigest()[:12]

            wagers.append({
                "ticket_id": ticket_id,
                "player_id": player_id,
                "placed_at": placed_at,
                "sport": sport,
                "description": description,
                "bet_type": bet_type,
                "risk": risk,
                "win_amount": win_amount,
                "result": result,
            })

        if wagers:
            break

    return wagers


def normalize_result(text: str) -> str:
    """Normalize bet result status to standard lowercase values."""
    t = text.lower().strip()
    if t.startswith("win") or t == "w":
        return "win"
    if t.startswith("los") or t == "l":
        return "loss"
    if t.startswith("push") or t == "p" or t == "tie":
        return "push"
    if t.startswith("cancel") or t == "void" or t == "c":
        return "cancel"
    if t == "" or t.startswith("pend") or t == "open" or t == "active":
        return "pending"
    return t


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
