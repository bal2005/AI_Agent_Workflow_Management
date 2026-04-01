import React from "react";
import { useNavigate, useLocation } from "react-router-dom";

const s = {
  navbar: {
    display: "flex", alignItems: "center", gap: 0, padding: "0 24px",
    background: "#0d0f18", borderBottom: "1px solid #1e2130", flexShrink: 0, height: 52,
  },
  logo: {
    display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 800,
    color: "#f1f5f9", cursor: "pointer", padding: "0 16px 0 0",
    borderRight: "1px solid #1e2130", marginRight: 12, height: "100%",
    textDecoration: "none", userSelect: "none",
  },
  navLinks: { display: "flex", gap: 2, flex: 1, overflowX: "auto", scrollbarWidth: "none" },
  navLink: (isActive) => ({
    padding: "6px 13px", borderRadius: 7, fontSize: 12, fontWeight: 600,
    cursor: "pointer", whiteSpace: "nowrap",
    background: isActive ? "#4f46e5" : "transparent",
    color: isActive ? "#fff" : "#64748b",
    border: isActive ? "1px solid #6366f1" : "1px solid transparent",
    transition: "all .12s",
  }),
};

const PAGES = [
  { path: "/",            label: "📊 Dashboard" },
  { path: "/agents",      label: "🤖 Agents" },
  { path: "/tools",       label: "🔧 Tools" },
  { path: "/task-create", label: "📋 Tasks" },
  { path: "/task",        label: "⚡ Playground" },
  { path: "/scheduler",   label: "🗓 Scheduler" },
  { path: "/run-history", label: "📋 Run History" },
  { path: "/sandbox",     label: "🐳 Sandbox" },
  { path: "/llm",         label: "🧠 LLM Config" },
  { path: "/admin",       label: "🛠 Admin" },
];

export default function Navbar() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  // Match active: /task-details/:id should highlight /task-create
  const isActive = (path) => {
    if (path === "/") return pathname === "/";
    if (path === "/task-create") return pathname.startsWith("/task-create") || pathname.startsWith("/task-details");
    return pathname === path || pathname.startsWith(path + "/");
  };

  return (
    <div style={s.navbar}>
      <div style={s.logo} onClick={() => navigate("/")}>
        <span style={{ fontSize: 18 }}>🤖</span>
        <span>Agent Studio</span>
      </div>
      <div style={s.navLinks}>
        {PAGES.map((page) => (
          <button
            key={page.path}
            onClick={() => navigate(page.path)}
            style={s.navLink(isActive(page.path))}
            onMouseEnter={(e) => {
              if (!isActive(page.path)) { e.currentTarget.style.background = "#1a1d2e"; e.currentTarget.style.color = "#cbd5e1"; }
            }}
            onMouseLeave={(e) => {
              if (!isActive(page.path)) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#64748b"; }
            }}
          >
            {page.label}
          </button>
        ))}
      </div>
    </div>
  );
}
