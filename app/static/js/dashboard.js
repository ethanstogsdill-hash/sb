// Load dashboard summary stats
async function loadDashboard() {
    try {
        const data = await api("/api/dashboard/summary");
        document.getElementById("stat-agents").textContent = data.total_agents;
        document.getElementById("stat-action").textContent = fmt(data.total_action);

        const wlEl = document.getElementById("stat-wl");
        wlEl.textContent = fmt(data.net_win_loss);
        wlEl.className = `text-2xl font-bold ${numClass(data.net_win_loss)}`;

        document.getElementById("stat-unmatched").textContent = data.unmatched_payments;
    } catch (e) {
        console.error("Failed to load dashboard:", e);
    }
}
