// Weekly view logic

async function loadWeeks() {
    try {
        availableWeeks = await api("/api/weeks");
        renderWeekDropdown();
        if (availableWeeks.length && !selectedWeek) {
            selectedWeek = availableWeeks[0];
        }
        if (selectedWeek) {
            await loadWeekData(selectedWeek);
        }
    } catch (e) {
        console.error("Failed to load weeks:", e);
    }
}

function renderWeekDropdown() {
    const select = document.getElementById("week-select");
    if (!select) return;

    const current = select.value || selectedWeek;
    select.innerHTML = availableWeeks.length
        ? availableWeeks.map(w =>
            `<option value="${w}" ${w === current ? "selected" : ""}>${formatWeekLabel(w)}</option>`
        ).join("")
        : '<option value="">No weeks available</option>';
}

async function onWeekChange(value) {
    if (!value) return;
    selectedWeek = value;
    await loadWeekData(value);
}

async function loadWeekData(weekStart) {
    try {
        const [snapshots, summary] = await Promise.all([
            api(`/api/weeks/${weekStart}`),
            api(`/api/weeks/${weekStart}/summary`),
        ]);
        currentSnapshots = snapshots;
        renderWeeklyTable(snapshots);
        renderWeeklySummary(summary);
        // Hide settlement panel when week changes
        document.getElementById("settlement-panel").style.display = "none";
    } catch (e) {
        console.error("Failed to load week data:", e);
    }
}

function renderWeeklySummary(summary) {
    document.getElementById("week-stat-players").textContent = summary.players;

    const wlEl = document.getElementById("week-stat-wl");
    wlEl.textContent = fmt(summary.net_wl);
    wlEl.className = `text-2xl font-bold ${numClass(summary.net_wl)}`;

    const totalOwed = summary.total_owed_to_us;
    const totalPaid = summary.total_paid;
    const pctEl = document.getElementById("week-stat-collection");
    if (totalOwed > 0) {
        const pct = Math.min(100, (totalPaid / totalOwed) * 100).toFixed(0);
        pctEl.textContent = `${fmt(totalPaid)} / ${fmt(totalOwed)} (${pct}%)`;
    } else {
        pctEl.textContent = totalPaid > 0 ? fmt(totalPaid) : "$0.00";
    }
}

function renderWeeklyTable(snapshots) {
    const tbody = document.getElementById("weekly-tbody");
    if (!snapshots.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-gray-500">No data for this week.</td></tr>';
        return;
    }

    tbody.innerHTML = snapshots.map(s => {
        const owed = Math.abs(s.win_loss);
        const paid = s.amount_paid || 0;
        const remaining = Math.max(0, owed - paid);
        const direction = s.win_loss < 0 ? "Player owes" : s.win_loss > 0 ? "We owe" : "";

        let remainClass = "text-red-400";
        if (remaining === 0 && owed > 0) remainClass = "text-green-400";
        else if (paid > 0) remainClass = "text-yellow-400";

        return `
        <tr class="border-b border-gray-700 hover:bg-gray-750 transition">
            <td class="px-4 py-2 font-mono text-xs">${esc(s.account_name)}</td>
            <td class="px-4 py-2">
                <input type="text" class="inline-edit" value="${esc(s.real_name || "")}"
                    placeholder="Enter name..."
                    onchange="updateRealName(${s.agent_id}, this.value)"
                    onkeydown="if(event.key==='Enter') this.blur()">
            </td>
            <td class="px-4 py-2 text-right ${numClass(s.win_loss)}">
                ${fmt(s.win_loss)}
                <span class="text-xs text-gray-500 ml-1">${direction}</span>
            </td>
            <td class="px-4 py-2 text-right">${fmt(owed)}</td>
            <td class="px-4 py-2 text-right">
                <input type="number" step="0.01" min="0"
                    class="inline-edit w-24 text-right"
                    value="${paid.toFixed(2)}"
                    onchange="updatePayment(${s.id}, this.value)"
                    onkeydown="if(event.key==='Enter') this.blur()">
            </td>
            <td class="px-4 py-2 text-right ${remainClass} font-medium">${fmt(remaining)}</td>
        </tr>`;
    }).join("");
}

// Store current snapshots for settlement calculation
let currentSnapshots = [];

function toggleSettlement() {
    const panel = document.getElementById("settlement-panel");
    if (panel.style.display === "none") {
        calculateSettlement();
        panel.style.display = "";
    } else {
        panel.style.display = "none";
    }
}

function calculateSettlement() {
    const tbody = document.getElementById("settlement-tbody");
    const summaryEl = document.getElementById("settlement-summary");

    if (!currentSnapshots.length || !allAgents.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="px-4 py-8 text-center text-gray-500">No data available.</td></tr>';
        summaryEl.textContent = "";
        return;
    }

    // Build agent lookup
    const agentMap = {};
    allAgents.forEach(a => { agentMap[a.id] = a; });

    // Filter out excluded (house) accounts and zero balances
    const eligible = currentSnapshots.filter(s => {
        const agent = agentMap[s.agent_id];
        return agent && !agent.excluded && s.win_loss !== 0;
    });

    // Split into debtors (lost, win_loss < 0) and creditors (won, win_loss > 0)
    const debtors = eligible
        .filter(s => s.win_loss < 0)
        .map(s => ({ agent_id: s.agent_id, amount: Math.abs(s.win_loss) }))
        .sort((a, b) => b.amount - a.amount);

    const creditors = eligible
        .filter(s => s.win_loss > 0)
        .map(s => ({ agent_id: s.agent_id, amount: s.win_loss }))
        .sort((a, b) => b.amount - a.amount);

    const transfers = [];
    let di = 0, ci = 0;

    // Greedy two-pointer matching
    while (di < debtors.length && ci < creditors.length) {
        const d = debtors[di];
        const c = creditors[ci];
        const transfer = Math.min(d.amount, c.amount);

        transfers.push({
            from_id: d.agent_id,
            to_id: c.agent_id,
            amount: transfer,
            type: "peer"
        });

        d.amount -= transfer;
        c.amount -= transfer;

        if (d.amount < 0.01) di++;
        if (c.amount < 0.01) ci++;
    }

    // Leftover debtors pay the bookie
    while (di < debtors.length) {
        if (debtors[di].amount >= 0.01) {
            transfers.push({
                from_id: debtors[di].agent_id,
                to_id: null,
                amount: debtors[di].amount,
                type: "to_bookie"
            });
        }
        di++;
    }

    // Leftover creditors get paid by bookie
    while (ci < creditors.length) {
        if (creditors[ci].amount >= 0.01) {
            transfers.push({
                from_id: null,
                to_id: creditors[ci].agent_id,
                amount: creditors[ci].amount,
                type: "from_bookie"
            });
        }
        ci++;
    }

    // Calculate stats
    const bookieFlow = transfers
        .filter(t => t.type !== "peer")
        .reduce((sum, t) => sum + t.amount, 0);
    const peerFlow = transfers
        .filter(t => t.type === "peer")
        .reduce((sum, t) => sum + t.amount, 0);
    const totalFlow = bookieFlow + peerFlow;

    summaryEl.innerHTML = `
        Peer-to-peer: <span class="text-green-400 font-medium">${fmt(peerFlow)}</span> &nbsp;|&nbsp;
        Through bookie: <span class="text-yellow-400 font-medium">${fmt(bookieFlow)}</span> &nbsp;|&nbsp;
        Total: <span class="text-white font-medium">${fmt(totalFlow)}</span>
    `;

    if (!transfers.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="px-4 py-8 text-center text-gray-500">No settlements needed.</td></tr>';
        return;
    }

    tbody.innerHTML = transfers.map(t => {
        const fromAgent = t.from_id ? agentMap[t.from_id] : null;
        const toAgent = t.to_id ? agentMap[t.to_id] : null;

        const fromName = fromAgent ? (fromAgent.real_name || fromAgent.account_name) : "Bookie (You)";
        const toName = toAgent ? (toAgent.real_name || toAgent.account_name) : "Bookie (You)";

        const fromTg = fromAgent?.telegram || "";
        const toTg = toAgent?.telegram || "";
        const tgDisplay = [fromTg, toTg].filter(Boolean).join(" → ") || "—";

        let rowClass = "";
        if (t.type === "to_bookie") rowClass = "bg-yellow-900/20";
        else if (t.type === "from_bookie") rowClass = "bg-yellow-900/20";

        return `
        <tr class="border-b border-gray-700 ${rowClass}">
            <td class="px-4 py-2">${esc(fromName)}</td>
            <td class="px-4 py-2">${esc(toName)}</td>
            <td class="px-4 py-2 text-right font-medium text-green-400">${fmt(t.amount)}</td>
            <td class="px-4 py-2 text-gray-400 text-xs">${esc(tgDisplay)}</td>
        </tr>`;
    }).join("");
}

async function updatePayment(snapshotId, value) {
    const amount = parseFloat(value) || 0;
    try {
        await api(`/api/weeks/snapshots/${snapshotId}/payment`, {
            method: "PATCH",
            body: JSON.stringify({ amount_paid: amount }),
        });
        toast("Payment updated", "success");
        if (selectedWeek) {
            await loadWeekData(selectedWeek);
        }
    } catch (e) {
        toast("Failed to update payment: " + e.message, "error");
    }
}
