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
        renderWeeklyTable(snapshots);
        renderWeeklySummary(summary);
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
