// Load payments from API
async function loadPayments() {
    try {
        const payments = await api("/api/payments");
        renderPayments(payments);
    } catch (e) {
        console.error("Failed to load payments:", e);
    }
}

function renderPayments(payments) {
    const tbody = document.getElementById("payments-tbody");
    if (!payments.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-gray-500">No payments loaded. Connect Gmail and click "Scan Now".</td></tr>';
        return;
    }

    tbody.innerHTML = payments.map(p => {
        const statusColor = p.match_status === "matched" ? "text-green-400" : "text-yellow-400";
        const methodBadge = _methodBadge(p.payment_method);

        // Build agent dropdown
        const agentOptions = allAgents.map(a =>
            `<option value="${a.id}" ${p.linked_agent_id === a.id ? "selected" : ""}>${esc(a.real_name || a.account_name)}</option>`
        ).join("");

        return `
        <tr class="border-b border-gray-700 hover:bg-gray-750 transition">
            <td class="px-4 py-2 text-xs">${_formatDate(p.date)}</td>
            <td class="px-4 py-2 text-xs truncate max-w-[150px]" title="${esc(p.sender)}">${esc(p.sender)}</td>
            <td class="px-4 py-2 text-xs truncate max-w-[200px]" title="${esc(p.subject)}">${esc(p.subject)}</td>
            <td class="px-4 py-2 text-right text-profit font-medium">${fmt(p.amount)}</td>
            <td class="px-4 py-2">${methodBadge}</td>
            <td class="px-4 py-2">
                <select class="bg-gray-700 border border-gray-600 rounded text-xs px-2 py-1 text-gray-200"
                    onchange="linkPayment(${p.id}, this.value)">
                    <option value="">— Unlinked —</option>
                    ${agentOptions}
                </select>
            </td>
            <td class="px-4 py-2 ${statusColor} text-xs font-medium cursor-pointer"
                onclick="toggleMatchStatus(${p.id}, '${p.match_status}')">
                ${p.match_status}
            </td>
        </tr>`;
    }).join("");
}

function _methodBadge(method) {
    const colors = {
        "Venmo": "bg-blue-900 text-blue-300",
        "Zelle": "bg-purple-900 text-purple-300",
        "Cash App": "bg-green-900 text-green-300",
        "PayPal": "bg-indigo-900 text-indigo-300",
        "Apple Pay": "bg-gray-700 text-gray-300",
    };
    const cls = colors[method] || "bg-gray-700 text-gray-300";
    return `<span class="px-2 py-0.5 rounded text-xs ${cls}">${esc(method || "Unknown")}</span>`;
}

function _formatDate(iso) {
    if (!iso) return "—";
    try {
        const d = new Date(iso);
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
        return iso;
    }
}

// Link payment to agent
async function linkPayment(paymentId, agentIdStr) {
    const agentId = agentIdStr ? parseInt(agentIdStr) : null;
    const status = agentId ? "matched" : "unmatched";
    try {
        await api(`/api/payments/${paymentId}`, {
            method: "PATCH",
            body: JSON.stringify({ linked_agent_id: agentId, match_status: status }),
        });
        toast(agentId ? "Payment linked" : "Payment unlinked", "success");
        await loadPayments();
        await loadDashboard();
    } catch (e) {
        toast("Failed to link: " + e.message, "error");
    }
}

// Toggle match status
async function toggleMatchStatus(paymentId, current) {
    const next = current === "matched" ? "unmatched" : "matched";
    try {
        await api(`/api/payments/${paymentId}`, {
            method: "PATCH",
            body: JSON.stringify({ match_status: next }),
        });
        await loadPayments();
        await loadDashboard();
    } catch (e) {
        toast("Failed to update status: " + e.message, "error");
    }
}

// Trigger Gmail scan
async function triggerScan() {
    const btn = document.getElementById("scan-btn");
    btn.classList.add("btn-loading");
    btn.textContent = "Scanning...";
    try {
        const data = await api("/api/payments/scan", { method: "POST" });
        toast(`Found ${data.total} emails, ${data.new} new`, "success");
        await loadPayments();
        await loadDashboard();
    } catch (e) {
        toast("Scan failed: " + e.message, "error");
    } finally {
        btn.classList.remove("btn-loading");
        btn.textContent = "Scan Now";
    }
}
