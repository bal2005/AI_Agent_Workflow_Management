import { useState, useEffect } from "react";
import { fetchDomains, fetchAgentsByDomain, runTaskPlayground } from "../api";

const c = {
  page: { minHeight: "100vh", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif", padding: "32px 40px", maxWidth: 900 },
  title: { fontSize: 26, fontWeight: 700, color: "#f1f5f9", margin: 0 },
  subtitle: { fontSize: 14, color: "#64748b", marginTop: 6, marginBottom: 32 },
  section: { background: "#13151f", border: "1px solid #1e2130", borderRadius: 12, padding: "24px 28px", marginBottom: 20 },
  sectionTitle: { fontSize: 11, fontWeight: 700, color: "#94a3b8", marginBottom: 16, textTransform: "uppercase", letterSpacing: 1 },
  row: { display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 },
  field: { display: "flex", flexDirection: "column", gap: 6, flex: 1, minWidth: 200 },
  label: { fontSize: 12, color: "#64748b", fontWeight: 600 },
  select: { background: "#0f1117", border: "1px solid #2d3748", borderRadius: 8, padding: "9px 14px", fontSize: 13, color: "#e2e8f0", outline: "none" },
  input: { background: "#0f1117", border: "1px solid #2d3748", borderRadius: 8, padding: "9px 14px", fontSize: 13, color: "#e2e8f0", outline: "none", width: "100%", boxSizing: "border-box" },
  textarea: { background: "#0f1117", border: "1px solid #2d3748", borderRadius: 8, padding: "9px 14px", fontSize: 13, color: "#e2e8f0", outline: "none", width: "100%", minHeight: 100, resize: "vertical", fontFamily: "inherit", boxSizing: "border-box" },
  permGrid: { display: "flex", flexWrap: "wrap", gap: 10 },
  permChip: (active) => ({
    padding: "5px 14px", borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: "pointer", userSelect: "none",
    background: active ? "#4f46e5" : "#1e2130",
    border: `1px solid ${active ? "#6366f1" : "#2d3748"}`,
    color: active ? "#fff" : "#64748b",
    transition: "all .15s",
  }),
  runBtn: { padding: "11px 32px", background: "#4f46e5", border: "none", borderRadius: 8, color: "#fff", fontSize: 14, fontWeight: 700, cursor: "pointer", marginTop: 8 },
  resultBox: { background: "#0a0c14", border: "1px solid #1e2130", borderRadius: 8, padding: "16px", minHeight: 120, fontFamily: "monospace", fontSize: 13, color: "#a3e635", whiteSpace: "pre-wrap", lineHeight: 1.6 },
  stepsBox: { background: "#0f1117", border: "1px solid #1e2130", borderRadius: 8, padding: "14px 16px", marginBottom: 16 },
  stepLine: { fontSize: 12, fontFamily: "monospace", color: "#94a3b8", lineHeight: 1.8 },
  stepTool: { color: "#818cf8" },
  stepResult: { color: "#475569", paddingLeft: 16 },
  errorMsg: { color: "#f87171", fontSize: 13, marginTop: 8 },
  pill: (color) => ({ display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600, background: color === "green" ? "#14532d" : "#1e3a5f", color: color === "green" ? "#4ade80" : "#60a5fa" }),
};

const ALL_FS_PERMISSIONS = [
  { key: "read_files", label: "Read Files" },
  { key: "write_files", label: "Write Files" },
  { key: "browse_folders", label: "Browse Folders" },
  { key: "detect_file_changes", label: "Detect File Changes" },
  { key: "detect_folder_changes", label: "Detect Folder Changes" },
];

const SHELL_READONLY_TOOLS = [
  "get_system_info", "get_runtime_versions", "list_processes",
  "check_port_status", "list_listening_ports", "check_http_endpoint",
  "check_dns_resolution", "test_host_reachability",
  "read_log_tail", "search_logs", "check_docker_status", "list_containers",
  "search_files", "check_path_exists",
];

const SHELL_WRITE_TOOLS = [
  "create_file", "append_file", "delete_file", "rename_file",
  "start_process", "stop_process", "restart_service",
  "run_script", "run_shell_command", "install_package",
  "git_checkout", "git_commit", "docker_start", "docker_stop",
];

export default function TaskPlaygroundPage({ onBack }) {
  const [domains, setDomains] = useState([]);
  const [agents, setAgents] = useState([]);
  const [selectedDomainId, setSelectedDomainId] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [rootPath, setRootPath] = useState("");
  const [task, setTask] = useState("");
  const [permissions, setPermissions] = useState(["read_files", "browse_folders"]);
  const [shellPerms, setShellPerms] = useState({
    execute_commands: true,
    allow_read_only_commands: true,
    allow_write_impacting_commands: false,
  });
  const [webPerms, setWebPerms] = useState({
    perform_search: false,
    open_result_links: false,
  });

  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);   // { result, steps, engine }
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDomains().then(setDomains).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedDomainId) { setAgents([]); return; }
    fetchAgentsByDomain(selectedDomainId).then(setAgents).catch(() => {});
  }, [selectedDomainId]);

  const togglePerm = (key) => {
    setPermissions(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
  };

  const toggleShellPerm = (key) => {
    setShellPerms(prev => {
      const next = { ...prev, [key]: !prev[key] };
      // If execute_commands turned off, disable sub-permissions too
      if (key === "execute_commands" && !next.execute_commands) {
        next.allow_read_only_commands = false;
        next.allow_write_impacting_commands = false;
      }
      return next;
    });
  };

  const handleRun = async () => {
    if (!selectedAgentId) { setError("Select an agent first"); return; }
    if (!rootPath.trim()) { setError("Enter a root path"); return; }
    if (!task.trim()) { setError("Enter a task description"); return; }

    setRunning(true); setResult(null); setError("");
    try {
      const data = await runTaskPlayground({
        agent_id: Number(selectedAgentId),
        task: task.trim(),
        root_path: rootPath.trim(),
        allowed_permissions: permissions,
        shell_permissions: shellPerms,
        web_permissions: webPerms,
      });
      setResult(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Request failed");
    } finally {
      setRunning(false);
    }
  };

  const selectedAgent = agents.find(a => a.id === Number(selectedAgentId));
  const selectedDomain = domains.find(d => d.id === Number(selectedDomainId));

  return (
    <div style={c.page}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 8 }}>
        <div>
          <h1 style={c.title}>Task Playground</h1>
          <p style={c.subtitle}>Run agents against real tools using the GitHub Copilot SDK</p>
        </div>
        <button onClick={onBack} style={{ background: "none", border: "1px solid #2d3748", borderRadius: 8, color: "#94a3b8", padding: "8px 16px", cursor: "pointer", fontSize: 13 }}>
          ← Back
        </button>
      </div>

      {/* Agent Selection */}
      <div style={c.section}>
        <div style={c.sectionTitle}>Agent</div>
        <div style={c.row}>
          <div style={c.field}>
            <label style={c.label}>Domain</label>
            <select style={c.select} value={selectedDomainId} onChange={e => { setSelectedDomainId(e.target.value); setSelectedAgentId(""); }}>
              <option value="">Select domain...</option>
              {domains.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          <div style={c.field}>
            <label style={c.label}>Agent</label>
            <select style={{ ...c.select, opacity: selectedDomainId ? 1 : 0.4 }} value={selectedAgentId} onChange={e => setSelectedAgentId(e.target.value)} disabled={!selectedDomainId}>
              <option value="">Select agent...</option>
              {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
        </div>

        {selectedAgent && (
          <div style={{ background: "#0f1117", border: "1px solid #1e2130", borderRadius: 8, padding: "12px 16px" }}>
            <div style={{ fontSize: 11, color: "#475569", marginBottom: 6, textTransform: "uppercase", letterSpacing: 1 }}>System Prompt (Skill)</div>
            <div style={{ fontSize: 13, color: "#94a3b8", whiteSpace: "pre-wrap", maxHeight: 100, overflowY: "auto" }}>
              {selectedAgent.system_prompt}
            </div>
          </div>
        )}
      </div>

      {/* Filesystem Tool Config */}
      <div style={c.section}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <div style={c.sectionTitle}>📁 Filesystem Tool</div>
          <span style={c.pill("blue")}>Active</span>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={c.label}>Root Path (local directory the agent can access)</label>
          <input
            style={{ ...c.input, marginTop: 6 }}
            placeholder="e.g. C:\Users\you\projects\myapp  or  /home/user/workspace"
            value={rootPath}
            onChange={e => setRootPath(e.target.value)}
          />
        </div>

        <div>
          <label style={{ ...c.label, marginBottom: 10, display: "block" }}>Granted Permissions</label>
          <div style={c.permGrid}>
            {ALL_FS_PERMISSIONS.map(p => (
              <div key={p.key} style={c.permChip(permissions.includes(p.key))} onClick={() => togglePerm(p.key)}>
                {permissions.includes(p.key) ? "✓ " : ""}{p.label}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Shell Access */}
      <div style={c.section}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <div style={c.sectionTitle}>⚡ Shell Access</div>
          <span style={{ fontSize: 11, color: "#fca5a5", background: "#2d1515", border: "1px solid #7f1d1d", borderRadius: 6, padding: "2px 8px" }}>⚠ High Risk</span>
        </div>

        {/* Top-level toggles */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>
          {[
            { key: "execute_commands", label: "Execute Commands", desc: "Master switch — must be on for any shell access" },
            { key: "allow_read_only_commands", label: "Allow Read-Only Commands", desc: "Diagnostics: system info, process list, port checks, log reading", disabled: !shellPerms.execute_commands },
            { key: "allow_write_impacting_commands", label: "Allow Write-Impacting Commands", desc: "File ops, process control, scripts, git, docker", disabled: !shellPerms.execute_commands, warn: true },
          ].map(({ key, label, desc, disabled, warn }) => (
            <div key={key} style={{ display: "flex", alignItems: "flex-start", gap: 12, opacity: disabled ? 0.4 : 1 }}>
              <div
                onClick={() => !disabled && toggleShellPerm(key)}
                style={{
                  width: 40, height: 22, borderRadius: 11, flexShrink: 0, marginTop: 2,
                  cursor: disabled ? "not-allowed" : "pointer",
                  background: shellPerms[key] ? (warn ? "#7f1d1d" : "#4f46e5") : "#1e2130",
                  border: `1px solid ${shellPerms[key] ? (warn ? "#ef4444" : "#6366f1") : "#2d3748"}`,
                  position: "relative", transition: "background .2s",
                }}
              >
                <div style={{
                  position: "absolute", top: 3, width: 14, height: 14, borderRadius: "50%",
                  background: "#e2e8f0", transition: "left .2s",
                  left: shellPerms[key] ? 22 : 3,
                }} />
              </div>
              <div>
                <div style={{ fontSize: 13, color: warn && shellPerms[key] ? "#fca5a5" : "#e2e8f0", fontWeight: 600 }}>{label}</div>
                <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>{desc}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Tool previews */}
        {shellPerms.execute_commands && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ opacity: shellPerms.allow_read_only_commands ? 1 : 0.35 }}>
              <div style={{ fontSize: 11, color: "#475569", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>Read-Only Diagnostics</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {SHELL_READONLY_TOOLS.map(t => (
                  <span key={t} style={{ fontSize: 11, background: "#0f1117", border: "1px solid #1e2130", borderRadius: 4, padding: "2px 8px", color: "#64748b", fontFamily: "monospace" }}>{t}</span>
                ))}
              </div>
            </div>
            <div style={{ opacity: shellPerms.allow_write_impacting_commands ? 1 : 0.35 }}>
              <div style={{ fontSize: 11, color: "#7f1d1d", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>Write-Impacting</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {SHELL_WRITE_TOOLS.map(t => (
                  <span key={t} style={{ fontSize: 11, background: "#0f1117", border: "1px solid #2d1515", borderRadius: 4, padding: "2px 8px", color: "#7f1d1d", fontFamily: "monospace" }}>{t}</span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Web Search */}
      <div style={c.section}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <div style={c.sectionTitle}>🔍 Web Search</div>
          {(webPerms.perform_search || webPerms.open_result_links) && (
            <span style={c.pill("blue")}>Active</span>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* perform_search */}
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
            <div
              onClick={() => setWebPerms(p => ({ ...p, perform_search: !p.perform_search }))}
              style={{
                width: 40, height: 22, borderRadius: 11, flexShrink: 0, marginTop: 2,
                cursor: "pointer",
                background: webPerms.perform_search ? "#4f46e5" : "#1e2130",
                border: `1px solid ${webPerms.perform_search ? "#6366f1" : "#2d3748"}`,
                position: "relative", transition: "background .2s",
              }}
            >
              <div style={{ position: "absolute", top: 3, width: 14, height: 14, borderRadius: "50%", background: "#e2e8f0", transition: "left .2s", left: webPerms.perform_search ? 22 : 3 }} />
            </div>
            <div>
              <div style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>Perform Search</div>
              <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>Web search, news search, domain-scoped search via DuckDuckGo</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, opacity: webPerms.perform_search ? 1 : 0.35 }}>
                {["perform_web_search", "search_news", "search_domain"].map(t => (
                  <span key={t} style={{ fontSize: 11, background: "#0f1117", border: "1px solid #1e2130", borderRadius: 4, padding: "2px 8px", color: "#64748b", fontFamily: "monospace" }}>{t}</span>
                ))}
              </div>
            </div>
          </div>

          {/* open_result_links */}
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
            <div
              onClick={() => setWebPerms(p => ({ ...p, open_result_links: !p.open_result_links }))}
              style={{
                width: 40, height: 22, borderRadius: 11, flexShrink: 0, marginTop: 2,
                cursor: "pointer",
                background: webPerms.open_result_links ? "#4f46e5" : "#1e2130",
                border: `1px solid ${webPerms.open_result_links ? "#6366f1" : "#2d3748"}`,
                position: "relative", transition: "background .2s",
              }}
            >
              <div style={{ position: "absolute", top: 3, width: 14, height: 14, borderRadius: "50%", background: "#e2e8f0", transition: "left .2s", left: webPerms.open_result_links ? 22 : 3 }} />
            </div>
            <div>
              <div style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>Open Result Links</div>
              <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>Fetch and extract readable text content from URLs</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, opacity: webPerms.open_result_links ? 1 : 0.35 }}>
                {["open_result_link", "extract_page_content"].map(t => (
                  <span key={t} style={{ fontSize: 11, background: "#0f1117", border: "1px solid #1e2130", borderRadius: 4, padding: "2px 8px", color: "#64748b", fontFamily: "monospace" }}>{t}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Task */}
      <div style={c.section}>
        <div style={c.sectionTitle}>Task</div>
        <textarea
          style={c.textarea}
          placeholder={`Describe what you want the agent to do...\n\nExamples:\n• List all Python files and summarize what each one does\n• Find all TODO comments across the codebase\n• Create a README.md based on the project structure`}
          value={task}
          onChange={e => setTask(e.target.value)}
        />
        {error && <div style={c.errorMsg}>⚠ {error}</div>}
        <button
          style={{ ...c.runBtn, opacity: running ? 0.6 : 1 }}
          onClick={handleRun}
          disabled={running}
          onMouseEnter={e => { if (!running) e.currentTarget.style.background = "#4338ca"; }}
          onMouseLeave={e => e.currentTarget.style.background = "#4f46e5"}
        >
          {running ? "⏳ Running agent..." : "▶ Run Task"}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div style={c.section}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <div style={c.sectionTitle}>Result</div>
            <span style={c.pill("blue")}>🤖 GitHub Copilot SDK</span>
            {selectedDomain && selectedAgent && (
              <span style={{ fontSize: 12, color: "#475569" }}>{selectedDomain.name} › {selectedAgent.name}</span>
            )}
          </div>

          {result.steps.length > 0 && (
            <>
              <div style={{ fontSize: 11, color: "#475569", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>
                Tool Calls ({result.steps.filter(s => s.startsWith("🔧")).length})
              </div>
              <div style={c.stepsBox}>
                {result.steps.map((step, i) => (
                  <div key={i} style={{ ...c.stepLine, ...(step.startsWith("🔧") ? c.stepTool : c.stepResult) }}>
                    {step}
                  </div>
                ))}
              </div>
            </>
          )}

          <div style={{ fontSize: 11, color: "#475569", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>Agent Response</div>
          <div style={c.resultBox}>{result.result}</div>
        </div>
      )}
    </div>
  );
}
