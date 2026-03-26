import React from "react";

const features = [
  { icon: "🤖", label: "Agent Creation",   desc: "Build AI agents with domain context and custom skills",       page: "agents" },
  { icon: "🔧", label: "Tools Management", desc: "Grant agents filesystem, shell, and web tool permissions",    page: "tools" },
  { icon: "📋", label: "Task Creation",    desc: "Define tasks with prompts, workflows, and LLM overrides",     page: "task-create" },
  { icon: "⚡", label: "Task Playground",  desc: "Run tasks interactively against a live filesystem",           page: "task" },
  { icon: "📊", label: "Task Details",     desc: "View run history, logs, and reproducibility snapshots",       page: "task-details" },
  { icon: "🗓", label: "Scheduler",        desc: "Schedule tasks with interval, cron, or manual triggers",      page: "scheduler" },
  { icon: "📋", label: "Run History",      desc: "Browse all execution runs with detailed trace logs",          page: "run-history" },
  { icon: "🧠", label: "LLM Config",       desc: "Configure BYOK providers — OpenAI, Groq, Claude, Ollama",    page: "llm" },
  { icon: "🛠", label: "Admin",            desc: "Manage agents and domains, update prompts in bulk",           page: "admin" },
];

export default function LandingPage({ onNavigate }) {
  return (
    <div style={{
      flex: 1, overflowY: "auto", background: "#0f1117", color: "#e2e8f0",
      fontFamily: "Inter, sans-serif", display: "flex", flexDirection: "column",
      alignItems: "center", padding: "60px 40px 80px",
    }}>
      {/* Hero */}
      <div style={{ textAlign: "center", marginBottom: 56, maxWidth: 640 }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
        <h1 style={{ fontSize: 38, fontWeight: 800, color: "#f8fafc", margin: "0 0 14px", letterSpacing: -0.5 }}>
          Agent Studio
        </h1>
        <p style={{ fontSize: 16, color: "#64748b", lineHeight: 1.7, margin: 0 }}>
          Build, configure, and orchestrate AI agents with full control over
          prompts, tools, tasks, and scheduling — all in one place.
        </p>
        <button
          onClick={() => onNavigate("agents")}
          style={{
            marginTop: 28, padding: "12px 32px", borderRadius: 10,
            background: "#6366f1", border: "none", color: "#fff",
            fontSize: 15, fontWeight: 700, cursor: "pointer",
            boxShadow: "0 0 24px rgba(99,102,241,0.35)",
          }}
          onMouseEnter={e => e.currentTarget.style.background = "#4f46e5"}
          onMouseLeave={e => e.currentTarget.style.background = "#6366f1"}
        >
          Get Started →
        </button>
      </div>

      {/* Feature grid */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
        gap: 16, width: "100%", maxWidth: 900,
      }}>
        {features.map(f => (
          <div
            key={f.page}
            onClick={() => onNavigate(f.page)}
            style={{
              background: "#1e2130", border: "1px solid #2d3148", borderRadius: 12,
              padding: "22px 24px", cursor: "pointer", transition: "border-color .15s, transform .15s",
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = "#6366f1";
              e.currentTarget.style.transform = "translateY(-2px)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = "#2d3148";
              e.currentTarget.style.transform = "translateY(0)";
            }}
          >
            <div style={{ fontSize: 26, marginBottom: 10 }}>{f.icon}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#f1f5f9", marginBottom: 6 }}>{f.label}</div>
            <div style={{ fontSize: 12, color: "#475569", lineHeight: 1.6 }}>{f.desc}</div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div style={{ marginTop: 60, fontSize: 12, color: "#334155" }}>
        Agent Studio · AI Workflow Management
      </div>
    </div>
  );
}
