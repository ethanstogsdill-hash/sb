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
    // no-op: profiles tab handles display now
}

function renderProfiles() {
    const tbody = document.getElementById("profiles-tbody");
    if (!allAgents.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-gray-500">No players loaded.</td></tr>';
        return;
    }

    tbody.innerHTML = allAgents.map(a => `
        <tr class="border-b border-gray-700 hover:bg-gray-750 transition">
            <td class="px-4 py-2 text-center">
                <input type="checkbox" ${a.excluded ? "checked" : ""}
                    class="w-4 h-4 accent-indigo-500 cursor-pointer"
                    onchange="updateAgentProfile(${a.id}, 'excluded', this.checked)"
                    title="Exclude from peer-to-peer settlement (house account)">
            </td>
            <td class="px-4 py-2 font-mono text-xs">${esc(a.account_id)}</td>
            <td class="px-4 py-2">${esc(a.account_name)}</td>
            <td class="px-4 py-2">
                <input type="text" class="inline-edit" value="${esc(a.real_name || "")}"
                    placeholder="Enter name..."
                    onchange="updateAgentProfile(${a.id}, 'real_name', this.value)"
                    onkeydown="if(event.key==='Enter') this.blur()">
            </td>
            <td class="px-4 py-2">
                <input type="text" class="inline-edit" value="${esc(a.telegram || "")}"
                    placeholder="@username"
                    onchange="updateAgentProfile(${a.id}, 'telegram', this.value)"
                    onkeydown="if(event.key==='Enter') this.blur()">
            </td>
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

// Update agent profile field via API
async function updateAgentProfile(id, field, value) {
    try {
        await api(`/api/agents/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ [field]: value }),
        });
        // Update local state so weekly view stays in sync
        const agent = allAgents.find(a => a.id === id);
        if (agent) agent[field] = value;
        const labels = { telegram: "Telegram updated", real_name: "Name updated", excluded: value ? "Marked as house account" : "Unmarked as house account" };
        toast(labels[field] || "Updated", "success");
    } catch (e) {
        toast("Failed to update: " + e.message, "error");
    }
}

// Trigger manual scrape
async function triggerScrape() {
    const btn = document.getElementById("scrape-btn");
    btn.classList.add("btn-loading");
    btn.textContent = "Scraping...";
    try {
        const data = await api("/api/agents/scrape", { method: "POST" });
        const betMsg = data.bet_count ? `, ${data.bet_count} bets` : "";
        toast(`Scraped ${data.count} agents${betMsg}`, "success");
        await loadAgents();
        await loadDashboard();
        await loadWeeks();
        await loadBets();
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
