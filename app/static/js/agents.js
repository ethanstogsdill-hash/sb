// Load agents from API
async function loadAgents() {
    try {
        allAgents = await api("/api/agents");
        renderAgents();
    } catch (e) {
        console.error("Failed to load agents:", e);
    }
}

function renderAgents() {
    const tbody = document.getElementById("agents-tbody");
    if (!allAgents.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-gray-500">No agents loaded. Click "Refresh Now" to scrape.</td></tr>';
        return;
    }

    tbody.innerHTML = allAgents.map(a => `
        <tr class="border-b border-gray-700 hover:bg-gray-750 transition">
            <td class="px-4 py-2 font-mono text-xs">${esc(a.account_id)}</td>
            <td class="px-4 py-2">${esc(a.account_name)}</td>
            <td class="px-4 py-2">
                <input type="text" class="inline-edit" value="${esc(a.real_name || "")}"
                    placeholder="Enter name..."
                    onchange="updateRealName(${a.id}, this.value)"
                    onkeydown="if(event.key==='Enter') this.blur()">
            </td>
            <td class="px-4 py-2 text-right ${numClass(a.win_loss)}">${fmt(a.win_loss)}</td>
            <td class="px-4 py-2 text-right">${fmt(a.balance)}</td>
            <td class="px-4 py-2 text-right">${fmt(a.action)}</td>
            <td class="px-4 py-2 text-xs text-gray-500">${a.last_scraped_at || "—"}</td>
        </tr>
    `).join("");
}

// Escape HTML
function esc(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// Update real name via API
async function updateRealName(id, name) {
    try {
        await api(`/api/agents/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ real_name: name }),
        });
        toast("Name updated", "success");
    } catch (e) {
        toast("Failed to update name: " + e.message, "error");
    }
}

// Trigger manual scrape
async function triggerScrape() {
    const btn = document.getElementById("scrape-btn");
    btn.classList.add("btn-loading");
    btn.textContent = "Scraping...";
    try {
        const data = await api("/api/agents/scrape", { method: "POST" });
        toast(`Scraped ${data.count} agents`, "success");
        await loadAgents();
        await loadDashboard();
        await loadWeeks();
    } catch (e) {
        toast("Scrape failed: " + e.message, "error");
    } finally {
        btn.classList.remove("btn-loading");
        btn.textContent = "Refresh Now";
        loadScrapeStatus();
    }
}

// Load scrape status
async function loadScrapeStatus() {
    try {
        const data = await api("/api/agents/scrape-status");
        const el = document.getElementById("scrape-status");
        if (data.last_run) {
            el.textContent = `Last: ${data.last_run} (${data.status})`;
        } else {
            el.textContent = "Never scraped";
        }
    } catch {
        // ignore
    }
}
