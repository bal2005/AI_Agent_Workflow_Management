import React from "react";

const s = {
  navbar: {
    display: "flex",
    alignItems: "center",
    gap: 24,
    padding: "16px 40px",
    background: "#0f1117",
    borderBottom: "1px solid #1e2130",
    marginBottom: 32,
  },
  backBtn: {
    background: "none",
    border: "1px solid #2d3748",
    borderRadius: 8,
    color: "#94a3b8",
    padding: "8px 16px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    transition: "all .15s",
  },
  navLinks: {
    display: "flex",
    gap: 4,
    flex: 1,
  },
  navLink: (isActive) => ({
    padding: "8px 16px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    background: isActive ? "#4f46e5" : "transparent",
    color: isActive ? "#fff" : "#94a3b8",
    border: isActive ? "1px solid #6366f1" : "1px solid transparent",
    transition: "all .15s",
  }),
};

export default function Navbar({ onBack, currentPage, onNavigate }) {
  const pages = [
    { id: "agents", label: "🤖 Agent Creation" },
    { id: "tools", label: "🔧 Tools Management" },
    { id: "task", label: "⚡ Task Playground" },
    { id: "llm", label: "🧠 LLM Config" },
  ];

  return (
    <div style={s.navbar}>
      <button
        onClick={onBack}
        style={s.backBtn}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "#1e2130";
          e.currentTarget.style.color = "#cbd5e1";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "none";
          e.currentTarget.style.color = "#94a3b8";
        }}
      >
        ← Back
      </button>

      <div style={s.navLinks}>
        {pages.map((page) => (
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
                e.currentTarget.style.color = "#94a3b8";
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
