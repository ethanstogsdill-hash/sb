// Global state
let allAgents = [];
let availableWeeks = [];
let selectedWeek = null;

// API helper
async function api(path, options = {}) {
    const res = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Request failed");
    }
    return res.json();
}

// Toast notifications
function toast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const colors = {
        success: "bg-green-600",
        error: "bg-red-600",
        info: "bg-blue-600",
        warning: "bg-yellow-600",
    };
    const el = document.createElement("div");
    el.className = `toast ${colors[type] || colors.info} text-white px-4 py-2 rounded shadow-lg text-sm`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
        el.classList.add("fade-out");
        setTimeout(() => el.remove(), 300);
    }, 3000);
}

// Format currency
function fmt(n) {
    if (n == null) return "$0.00";
    const val = Number(n);
    const formatted = Math.abs(val).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return val < 0 ? `-$${formatted}` : `$${formatted}`;
}

// Color class for numbers
function numClass(n) {
    const val = Number(n);
    if (val > 0) return "text-profit";
    if (val < 0) return "text-loss";
    return "";
}

// Gmail connect
async function connectGmail() {
    try {
        const data = await api("/api/gmail/auth-url");
        window.open(data.url, "_blank", "width=600,height=700");
    } catch (e) {
        toast("Gmail auth not configured: " + e.message, "error");
    }
}

// Check Gmail status
async function checkGmailStatus() {
    try {
        const data = await api("/api/gmail/status");
        const indicator = document.getElementById("gmail-indicator");
        const text = document.getElementById("gmail-text");
        const btn = document.getElementById("gmail-connect-btn");
        if (data.connected) {
            indicator.className = "w-3 h-3 rounded-full bg-green-500";
            text.textContent = "Gmail: Connected";
            btn.style.display = "none";
        }
    } catch {
        // Silently fail — not configured yet
    }
}

// Format week label for dropdown
function formatWeekLabel(weekStart) {
    try {
        const start = new Date(weekStart + "T00:00:00");
        const end = new Date(start);
        end.setDate(end.getDate() + 6);
        const opts = { month: "short", day: "numeric" };
        return `${start.toLocaleDateString("en-US", opts)} – ${end.toLocaleDateString("en-US", opts)}, ${start.getFullYear()}`;
    } catch {
        return weekStart;
    }
}

// Polling loop
let pollInterval;
function startPolling() {
    loadDashboard();
    loadAgents();
    loadPayments();
    checkGmailStatus();
    loadScrapeStatus();
    loadWeeks();

    pollInterval = setInterval(() => {
        loadDashboard();
        loadAgents();
        loadPayments();
        loadScrapeStatus();
        loadWeeks();
    }, 30000);
}

// Init
document.addEventListener("DOMContentLoaded", startPolling);
