// Bets tab state
let allBets = [];
let betSports = [];

async function loadBets() {
    try {
        const [bets, stats, sports] = await Promise.all([
            api("/api/bets"),
            api("/api/bets/stats"),
            api("/api/bets/sports"),
        ]);
        allBets = bets;
        betSports = sports;

        // Update stats bar
        document.getElementById("bet-stat-total").textContent = stats.total_bets;
        document.getElementById("bet-stat-risked").textContent = fmt(stats.total_risked);
        document.getElementById("bet-stat-record").textContent = `${stats.wins} - ${stats.losses}`;
        document.getElementById("bet-stat-pending").textContent = stats.pending;

        // Populate sport filter dropdown
        const sportSelect = document.getElementById("bet-sport-filter");
        const currentSport = sportSelect.value;
        sportSelect.innerHTML = '<option value="">All Sports</option>';
        sports.forEach(s => {
            sportSelect.innerHTML += `<option value="${esc(s)}">${esc(s)}</option>`;
        });
        sportSelect.value = currentSport;

        // Populate player filter dropdown
        const playerSelect = document.getElementById("bet-player-filter");
        const currentPlayer = playerSelect.value;
        const players = [...new Set(bets.map(b => b.player_id))].sort();
        playerSelect.innerHTML = '<option value="">All Players</option>';
        players.forEach(p => {
            const name = bets.find(b => b.player_id === p);
            const label = name && name.real_name ? `${name.real_name} (${p})` : p;
            playerSelect.innerHTML += `<option value="${esc(p)}">${esc(label)}</option>`;
        });
        playerSelect.value = currentPlayer;

        filterBets();
    } catch (e) {
        console.error("Failed to load bets:", e);
    }
}

function filterBets() {
    const search = (document.getElementById("bet-search").value || "").toLowerCase();
    const sport = document.getElementById("bet-sport-filter").value;
    const result = document.getElementById("bet-result-filter").value;
    const player = document.getElementById("bet-player-filter").value;

    let filtered = allBets;
    if (sport) filtered = filtered.filter(b => b.sport === sport);
    if (result) filtered = filtered.filter(b => b.result === result);
    if (player) filtered = filtered.filter(b => b.player_id === player);
    if (search) {
        filtered = filtered.filter(b =>
            (b.description || "").toLowerCase().includes(search) ||
            (b.player_id || "").toLowerCase().includes(search) ||
            (b.account_name || "").toLowerCase().includes(search) ||
            (b.real_name || "").toLowerCase().includes(search) ||
            (b.sport || "").toLowerCase().includes(search) ||
            (b.bet_type || "").toLowerCase().includes(search)
        );
    }

    renderBets(filtered);
}

function renderBets(bets) {
    const tbody = document.getElementById("bets-tbody");
    if (!bets || !bets.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-500">No bets found.</td></tr>';
        return;
    }

    tbody.innerHTML = bets.map(b => {
        const playerLabel = b.real_name || b.account_name || b.player_id;
        return `
        <tr class="border-b border-gray-700 hover:bg-gray-750 transition">
            <td class="px-4 py-2 text-xs text-gray-400 whitespace-nowrap">${esc(b.placed_at || "—")}</td>
            <td class="px-4 py-2">${esc(playerLabel)}</td>
            <td class="px-4 py-2">${esc(b.sport || "—")}</td>
            <td class="px-4 py-2 max-w-xs truncate" title="${esc(b.description)}">${esc(b.description || "—")}</td>
            <td class="px-4 py-2 text-xs">${esc(b.bet_type || "—")}</td>
            <td class="px-4 py-2 text-right font-mono">${fmt(b.risk)}</td>
            <td class="px-4 py-2 text-right font-mono">${fmt(b.win_amount)}</td>
            <td class="px-4 py-2 text-center">${resultBadge(b.result)}</td>
        </tr>`;
    }).join("");
}

function resultBadge(result) {
    const colors = {
        win: "bg-green-600 text-green-100",
        loss: "bg-red-600 text-red-100",
        pending: "bg-yellow-600 text-yellow-100",
        push: "bg-gray-600 text-gray-200",
        cancel: "bg-gray-600 text-gray-200",
    };
    const cls = colors[result] || "bg-gray-600 text-gray-200";
    const label = result ? result.charAt(0).toUpperCase() + result.slice(1) : "Unknown";
    return `<span class="px-2 py-0.5 rounded text-xs font-medium ${cls}">${label}</span>`;
}
