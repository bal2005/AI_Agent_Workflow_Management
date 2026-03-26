import React from "react";

const s = {
  navbar: {
    display: "flex",
    alignItems: "center",
    gap: 0,
    padding: "0 24px",
    background: "#0d0f18",
    borderBottom: "1px solid #1e2130",
    flexShrink: 0,
    height: 52,
  },
  logo: {
    display: "flex", alignItems: "center", gap: 8,
    fontSize: 14, fontWeight: 800, color: "#f1f5f9",
    cursor: "pointer", padding: "0 16px 0 0",
    borderRight: "1px solid #1e2130", marginRight: 12, height: "100%",
    textDecoration: "none", userSelect: "none",
  },
  navLinks: {
    display: "flex", gap: 2, flex: 1, overflowX: "auto",
    scrollbarWidth: "none",
  },
  navLink: (isActive) => ({
    padding: "6px 13px",
    borderRadius: 7,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap",
    background: isActive ? "#4f46e5" : "transparent",
    color: isActive ? "#fff" : "#64748b",
    border: isActive ? "1px solid #6366f1" : "1px solid transparent",
    transition: "all .12s",
  }),
};

const PAGES = [
  { id: "agents",       label: "🤖 Agents" },
  { id: "tools",        label: "🔧 Tools" },
  { id: "task-create",  label: "📋 Tasks" },
  { id: "task-details", label: "📊 Task Details" },
  { id: "task",         label: "⚡ Playground" },
  { id: "scheduler",    label: "🗓 Scheduler" },
  { id: "run-history",  label: "📋 Run History" },
  { id: "llm",          label: "🧠 LLM Config" },
  { id: "admin",        label: "🛠 Admin" },
];

export default function Navbar({ currentPage, onNavigate }) {
  return (
    <div style={s.navbar}>
      {/* Logo → home */}
      <div style={s.logo} onClick={() => onNavigate("landing")}>
        <span style={{ fontSize: 18 }}>🤖</span>
        <span>Agent Studio</span>
      </div>

      <div style={s.navLinks}>
        {PAGES.map((page) => (
          <button
            key={page.id}
            onClick={() => onNavigate(page.id)}
            style={s.navLink(currentPage === page.id)}
            onMouseEnter={(e) => {
              if (currentPage !== page.id) {
                e.currentTarget.style.background = "#1a1d2e";
                e.currentTarget.style.color = "#cbd5e1";
              }
            }}
            onMouseLeave={(e) => {
              if (currentPage !== page.id) {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = "#64748b";
              }
            }}
          >
            {page.label}
          </button>
        ))}
      </div>
    </div>
  );
}
