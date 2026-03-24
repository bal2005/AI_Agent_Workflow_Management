import React, { useState } from "react";

// ─── Mock Data ────────────────────────────────────────────────────────────────

const MOCK_DOMAINS = [
  { id: 1, name: "Finance" },
  { id: 2, name: "Engineering" },
  { id: 3, name: "Operations" },
];

const MOCK_AGENTS = [
  { id: 1, domain_id: 1, name: "Risk Agent" },
  { id: 2, domain_id: 1, name: "Portfolio Analyst" },
  { id: 3, domain_id: 2, name: "Code Review Agent" },
  { id: 4, domain_id: 2, name: "Deploy Agent" },
  { id: 5, domain_id: 3, name: "Ops Monitor" },
];

// Initial mock permissions: agentId → toolId → Set of permission keys
const INITIAL_PERMS = {
  1: { filesystem: new Set(["read_files", "browse_folders"]), web_search: new Set(["perform_search"]) },
  3: { shell: new Set(["execute_commands", "allow_readonly"]), github: new Set(["read_repo", "read_issues"]) },
};

// ─── Tool Definitions ─────────────────────────────────────────────────────────

const TOOLS = [
  {
    id: "filesystem",
    name: "File System",
    icon: "📁",
    description: "Grants agents access to read, write, and monitor files and folders on the host system.",
    risk: null,
    permissions: [
      { key: "read_files", label: "Read files" },
      { key: "write_files", label: "Write files" },
      { key: "browse_folders", label: "Browse folders" },
      { key: "detect_file_changes", label: "Detect file changes" },
      { key: "detect_folder_changes", label: "Detect folder changes" },
    ],
    shells: null,
    config: [
      { key: "root_path", label: "Allowed root path", type: "text", placeholder: "/home/user/workspace" },
      { key: "extensions", label: "Allowed extensions", type: "text", placeholder: ".py, .md, .json" },
      { key: "readonly_mode", label: "Read-only mode", type: "toggle" },
    ],
  },
  {
    id: "shell",
    name: "Shell Access",
    icon: "⚡",
    description: "Allows agents to execute shell commands on the host machine. Use with caution — this grants significant system access.",
    risk: "High Risk — Shell access can modify system state, install packages, or delete files. Only assign to trusted agents.",
    permissions: [
      { key: "execute_commands", label: "Execute commands" },
      { key: "allow_readonly", label: "Allow read-only commands" },
      { key: "allow_write_impact", label: "Allow write-impacting commands" },
    ],
    shells: ["PowerShell", "CMD"],
    config: [
      { key: "allowed_commands", label: "Allowed commands", type: "text", placeholder: "ls, cat, git status" },
      { key: "blocked_commands", label: "Blocked commands", type: "text", placeholder: "rm, format, shutdown" },
      { key: "working_dir", label: "Working directory", type: "text", placeholder: "C:\\Projects" },
      { key: "timeout", label: "Timeout (seconds)", type: "number", placeholder: "30" },
    ],
  },
  {
    id: "web_search",
    name: "Web Search",
    icon: "🔍",
    description: "Enables agents to search the web and optionally open result links for deeper research.",
    risk: null,
    permissions: [
      { key: "perform_search", label: "Perform search" },
      { key: "open_links", label: "Open result links" },
    ],
    shells: null,
    config: [
      { key: "max_results", label: "Max results", type: "number", placeholder: "10" },
      { key: "safe_search", label: "Safe search", type: "toggle" },
      { key: "allowed_domains", label: "Allowed domains", type: "text", placeholder: "github.com, docs.python.org" },
    ],
  },
  {
    id: "github",
    name: "GitHub",
    icon: "🐙",
    description: "Connects agents to GitHub repositories for reading code, issues, PRs, and optionally making changes.",
    risk: null,
    permissions: [
      { key: "read_repo", label: "Read repo" },
      { key: "read_issues", label: "Read issues" },
      { key: "read_prs", label: "Read pull requests" },
      { key: "create_branch", label: "Create branch" },
      { key: "commit_changes", label: "Commit changes" },
      { key: "create_pr", label: "Create PR" },
    ],
    shells: null,
    config: [
      { key: "repo_url", label: "Repository URL", type: "text", placeholder: "https://github.com/org/repo" },
      { key: "auth_token", label: "Auth token", type: "password", placeholder: "ghp_••••••••••••" },
      { key: "repo_scope", label: "Allowed repo scope", type: "text", placeholder: "org/repo or *" },
    ],
  },
  {
    id: "email",
    name: "Email",
    icon: "✉️",
    description: "Integrates with email providers to send, read, and monitor messages. Supports Gmail API, Outlook API, or SMTP+IMAP.",
    risk: null,
    permissions: [
      { key: "send_email", label: "Send email" },
      { key: "read_inbox", label: "Read inbox" },
      { key: "read_attachments", label: "Read attachments" },
      { key: "create_draft", label: "Create draft" },
      { key: "monitor_incoming", label: "Monitor incoming mail" },
    ],
    shells: null,
    config: [
      { key: "provider", label: "Provider", type: "select", options: ["Gmail API", "Outlook API", "SMTP+IMAP"] },
      { key: "auth_placeholder", label: "Auth / credentials", type: "password", placeholder: "OAuth token or app password" },
      { key: "polling_interval", label: "Polling interval (seconds)", type: "number", placeholder: "60" },
      { key: "allowed_folders", label: "Allowed folders / labels", type: "text", placeholder: "INBOX, Work, Notifications" },
    ],
  },
];

// ─── Styles ───────────────────────────────────────────────────────────────────

const c = {
  page: { minHeight: "100vh", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif", padding: "32px 40px" },
  header: { marginBottom: 36 },
  title: { fontSize: 26, fontWeight: 700, color: "#f1f5f9", margin: 0 },
  subtitle: { fontSize: 14, color: "#64748b", marginTop: 6 },

  sectionTitle: { fontSize: 16, fontWeight: 700, color: "#94a3b8", marginBottom: 20, textTransform: "uppercase", letterSpacing: 1 },

  toolGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 20, marginBottom: 48 },

  card: { background: "#13151f", border: "1px solid #1e2130", borderRadius: 12, overflow: "hidden" },
  cardHeader: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "16px 20px", cursor: "pointer", userSelect: "none",
    borderBottom: "1px solid #1e2130",
  },
  cardHeaderLeft: { display: "flex", alignItems: "center", gap: 12 },
  cardIcon: { fontSize: 22 },
  cardName: { fontSize: 15, fontWeight: 600, color: "#e2e8f0" },
  cardChevron: { fontSize: 11, color: "#475569", transition: "transform .2s" },

  cardBody: { padding: "18px 20px" },
  desc: { fontSize: 13, color: "#64748b", marginBottom: 16, lineHeight: 1.6 },

  riskBadge: {
    display: "flex", alignItems: "flex-start", gap: 8,
    background: "#2d1515", border: "1px solid #7f1d1d", borderRadius: 8,
    padding: "10px 14px", marginBottom: 16, fontSize: 12, color: "#fca5a5", lineHeight: 1.5,
  },

  shellRow: { display: "flex", gap: 8, marginBottom: 16 },
  shellBadge: { background: "#1e2130", border: "1px solid #2d3748", borderRadius: 6, padding: "3px 10px", fontSize: 11, color: "#94a3b8" },

  subLabel: { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#475569", marginBottom: 10 },
  permGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 18 },
  permItem: { display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#94a3b8" },
  permDot: { width: 6, height: 6, borderRadius: "50%", background: "#334155", flexShrink: 0 },

  configGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 },
  configItem: {},
  configLabel: { fontSize: 11, color: "#475569", marginBottom: 4 },
  configInput: {
    width: "100%", background: "#0f1117", border: "1px solid #1e2130", borderRadius: 6,
    padding: "6px 10px", fontSize: 12, color: "#94a3b8", outline: "none", boxSizing: "border-box",
  },
  configSelect: {
    width: "100%", background: "#0f1117", border: "1px solid #1e2130", borderRadius: 6,
    padding: "6px 10px", fontSize: 12, color: "#94a3b8", outline: "none", boxSizing: "border-box",
  },
  toggleRow: { display: "flex", alignItems: "center", gap: 10, marginTop: 4 },
  toggleLabel: { fontSize: 12, color: "#64748b" },

  // Assignment section
  assignSection: { background: "#13151f", border: "1px solid #1e2130", borderRadius: 12, padding: "28px 28px" },
  assignTitle: { fontSize: 16, fontWeight: 700, color: "#94a3b8", marginBottom: 24, textTransform: "uppercase", letterSpacing: 1 },

  row: { display: "flex", gap: 20, marginBottom: 20, flexWrap: "wrap" },
  field: { display: "flex", flexDirection: "column", gap: 6, minWidth: 220 },
  label: { fontSize: 12, color: "#64748b", fontWeight: 600 },
  select: {
    background: "#0f1117", border: "1px solid #2d3748", borderRadius: 8,
    padding: "9px 14px", fontSize: 13, color: "#e2e8f0", outline: "none", minWidth: 220,
  },

  breadcrumb: {
    display: "inline-flex", alignItems: "center", gap: 8,
    background: "#1e2130", border: "1px solid #2d3748", borderRadius: 8,
    padding: "8px 16px", fontSize: 13, marginBottom: 24,
  },
  breadcrumbDomain: { color: "#818cf8", fontWeight: 600 },
  breadcrumbSep: { color: "#475569" },
  breadcrumbAgent: { color: "#34d399", fontWeight: 600 },

  toolAssignGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 16 },
  assignCard: { background: "#0f1117", border: "1px solid #1e2130", borderRadius: 10, padding: "16px 18px" },
  assignCardHeader: { display: "flex", alignItems: "center", gap: 10, marginBottom: 14 },
  assignCardIcon: { fontSize: 18 },
  assignCardName: { fontSize: 14, fontWeight: 600, color: "#e2e8f0" },
  assignPermList: { display: "flex", flexDirection: "column", gap: 8 },
  assignPermRow: { display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "#94a3b8", cursor: "pointer" },

  saveBtn: {
    marginTop: 24, padding: "10px 28px", background: "#4f46e5", border: "none",
    borderRadius: 8, color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer",
  },
  savedMsg: { marginTop: 12, fontSize: 13, color: "#34d399" },
};

// ─── Toggle component ─────────────────────────────────────────────────────────

function Toggle({ value, onChange }) {
  return (
    <div
      onClick={() => onChange(!value)}
      style={{
        width: 36, height: 20, borderRadius: 10, cursor: "pointer", position: "relative",
        background: value ? "#4f46e5" : "#1e2130", border: "1px solid #2d3748", transition: "background .2s",
      }}
    >
      <div style={{
        position: "absolute", top: 2, left: value ? 17 : 2,
        width: 14, height: 14, borderRadius: "50%", background: "#e2e8f0", transition: "left .2s",
      }} />
    </div>
  );
}

// ─── Tool Spec Card ───────────────────────────────────────────────────────────

function ToolCard({ tool }) {
  const [open, setOpen] = useState(false);
  const [configVals, setConfigVals] = useState({});

  const setVal = (key, val) => setConfigVals(p => ({ ...p, [key]: val }));

  return (
    <div style={c.card}>
      <div style={c.cardHeader} onClick={() => setOpen(o => !o)}
        onMouseEnter={e => e.currentTarget.style.background = "#1a1d2e"}
        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
      >
        <div style={c.cardHeaderLeft}>
          <span style={c.cardIcon}>{tool.icon}</span>
          <span style={c.cardName}>{tool.name}</span>
        </div>
        <span style={{ ...c.cardChevron, transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>▶</span>
      </div>

      {open && (
        <div style={c.cardBody}>
          <p style={c.desc}>{tool.description}</p>

          {tool.risk && (
            <div style={c.riskBadge}>
              <span>⚠️</span>
              <span>{tool.risk}</span>
            </div>
          )}

          {tool.shells && (
            <>
              <div style={c.subLabel}>Supported Shells</div>
              <div style={c.shellRow}>
                {tool.shells.map(s => <span key={s} style={c.shellBadge}>{s}</span>)}
              </div>
            </>
          )}

          <div style={c.subLabel}>Permissions</div>
          <div style={c.permGrid}>
            {tool.permissions.map(p => (
              <div key={p.key} style={c.permItem}>
                <div style={c.permDot} />
                {p.label}
              </div>
            ))}
          </div>

          <div style={c.subLabel}>Configuration</div>
          <div style={c.configGrid}>
            {tool.config.map(f => (
              <div key={f.key} style={c.configItem}>
                <div style={c.configLabel}>{f.label}</div>
                {f.type === "toggle" ? (
                  <div style={c.toggleRow}>
                    <Toggle value={!!configVals[f.key]} onChange={v => setVal(f.key, v)} />
                    <span style={c.toggleLabel}>{configVals[f.key] ? "Enabled" : "Disabled"}</span>
                  </div>
                ) : f.type === "select" ? (
                  <select style={c.configSelect} value={configVals[f.key] || ""} onChange={e => setVal(f.key, e.target.value)}>
                    <option value="">Select...</option>
                    {f.options.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                ) : (
                  <input
                    style={c.configInput}
                    type={f.type === "password" ? "password" : f.type === "number" ? "number" : "text"}
                    placeholder={f.placeholder}
                    value={configVals[f.key] || ""}
                    onChange={e => setVal(f.key, e.target.value)}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Checkbox ─────────────────────────────────────────────────────────────────

function Checkbox({ checked, onChange, label }) {
  return (
    <label style={c.assignPermRow} onClick={onChange}>
      <div style={{
        width: 16, height: 16, borderRadius: 4, border: `2px solid ${checked ? "#4f46e5" : "#2d3748"}`,
        background: checked ? "#4f46e5" : "transparent", display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0, transition: "all .15s",
      }}>
        {checked && <span style={{ color: "#fff", fontSize: 10, lineHeight: 1 }}>✓</span>}
      </div>
      {label}
    </label>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ToolsManagementPage({ onBack }) {
  const [selectedDomainId, setSelectedDomainId] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [perms, setPerms] = useState(INITIAL_PERMS);
  const [saved, setSaved] = useState(false);

  const filteredAgents = MOCK_AGENTS.filter(a => a.domain_id === Number(selectedDomainId));
  const selectedDomain = MOCK_DOMAINS.find(d => d.id === Number(selectedDomainId));
  const selectedAgent = MOCK_AGENTS.find(a => a.id === Number(selectedAgentId));

  const agentPerms = perms[selectedAgentId] || {};

  const togglePerm = (toolId, permKey) => {
    setPerms(prev => {
      const agentMap = { ...(prev[selectedAgentId] || {}) };
      const toolSet = new Set(agentMap[toolId] || []);
      toolSet.has(permKey) ? toolSet.delete(permKey) : toolSet.add(permKey);
      agentMap[toolId] = toolSet;
      return { ...prev, [selectedAgentId]: agentMap };
    });
    setSaved(false);
  };

  const handleDomainChange = (e) => {
    setSelectedDomainId(e.target.value);
    setSelectedAgentId("");
    setSaved(false);
  };

  const handleSave = () => setSaved(true);

  return (
    <div style={c.page}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 36 }}>
        <div>
          <h1 style={c.title}>Tools Management</h1>
          <p style={c.subtitle}>Define tool capabilities and assign access to agents</p>
        </div>
        <button
          onClick={onBack}
          style={{ background: "none", border: "1px solid #2d3748", borderRadius: 8, color: "#94a3b8", padding: "8px 16px", cursor: "pointer", fontSize: 13 }}
        >
          ← Back
        </button>
      </div>

      {/* Tool Specifications */}
      <div style={{ marginBottom: 48 }}>
        <div style={c.sectionTitle}>Tool Specifications</div>
        <div style={c.toolGrid}>
          {TOOLS.map(tool => <ToolCard key={tool.id} tool={tool} />)}
        </div>
      </div>

      {/* Agent Access Assignment */}
      <div style={c.assignSection}>
        <div style={c.assignTitle}>Agent Access Assignment</div>

        <div style={c.row}>
          <div style={c.field}>
            <label style={c.label}>Domain</label>
            <select style={c.select} value={selectedDomainId} onChange={handleDomainChange}>
              <option value="">Select domain...</option>
              {MOCK_DOMAINS.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>

          <div style={c.field}>
            <label style={c.label}>Agent</label>
            <select
              style={{ ...c.select, opacity: selectedDomainId ? 1 : 0.4 }}
              value={selectedAgentId}
              onChange={e => { setSelectedAgentId(e.target.value); setSaved(false); }}
              disabled={!selectedDomainId}
            >
              <option value="">Select agent...</option>
              {filteredAgents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
        </div>

        {/* Breadcrumb hierarchy */}
        {selectedDomain && selectedAgent && (
          <div style={c.breadcrumb}>
            <span style={c.breadcrumbDomain}>{selectedDomain.name}</span>
            <span style={c.breadcrumbSep}>›</span>
            <span style={c.breadcrumbAgent}>{selectedAgent.name}</span>
          </div>
        )}

        {/* Tool permission checkboxes */}
        {selectedAgent ? (
          <>
            <div style={c.toolAssignGrid}>
              {TOOLS.map(tool => {
                const granted = agentPerms[tool.id] || new Set();
                return (
                  <div key={tool.id} style={c.assignCard}>
                    <div style={c.assignCardHeader}>
                      <span style={c.assignCardIcon}>{tool.icon}</span>
                      <span style={c.assignCardName}>{tool.name}</span>
                      {tool.risk && <span style={{ fontSize: 11, color: "#fca5a5", marginLeft: "auto" }}>⚠ High Risk</span>}
                    </div>
                    <div style={c.assignPermList}>
                      {tool.permissions.map(p => (
                        <Checkbox
                          key={p.key}
                          checked={granted.has(p.key)}
                          onChange={() => togglePerm(tool.id, p.key)}
                          label={p.label}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            <button style={c.saveBtn} onClick={handleSave}
              onMouseEnter={e => e.currentTarget.style.background = "#4338ca"}
              onMouseLeave={e => e.currentTarget.style.background = "#4f46e5"}
            >
              Save Permissions
            </button>
            {saved && <div style={c.savedMsg}>✓ Permissions saved for {selectedDomain?.name} › {selectedAgent.name}</div>}
          </>
        ) : (
          <div style={{ fontSize: 13, color: "#475569", padding: "12px 0" }}>
            Select a domain and agent above to assign tool access.
          </div>
        )}
      </div>
    </div>
  );
}
