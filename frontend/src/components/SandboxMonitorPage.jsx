/**
 * SandboxMonitorPage
 * ───────────────────
 * Live view of Docker sandbox containers and workspace files.
 * Auto-refreshes every 3 seconds while any container is running.
 */
import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";

const api = axios.create({ baseURL: "/" });
const fetchStatus      = () => api.get("/sandbox/status").then(r => r.data);
const fetchContainers  = () => api.get("/sandbox/containers").then(r => r.data);
const fetchWorkspaces  = () => api.get("/sandbox/workspaces").then(r => r.data);
const fetchWorkspace   = (id) => api.get(`/sandbox/workspaces/${id}`).then(r => r.data);

const s = {
  page:      { display: "flex", flexDirection: "column", flex: 1, overflow: "hidden", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif" },
  header:    { padding: "20px 32px 14px", borderBottom: "1px solid #1e2130", flexShrink: 0 },
  title:     { fontSize: 20, fontWeight: 700, color: "#f8fafc", marginBottom: 4 },
  sub:       { fontSize: 12, color: "#475569" },
  body:      { display: "flex", flex: 1, overflow: "hidden" },
  left:      { width: 340, minWidth: 340, borderRight: "1px solid #1e2130", display: "flex", flexDirection: "column", overflow: "hidden" },
  right:     { flex: 1, overflowY: "auto", padding: "20px 28px" },
  section:   { background: "#1e2130", borderRadius: 10, padding: "16px 20px", marginBottom: 14, border: "1px solid #2d3148" },
  secTitle:  { fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#475569", marginBottom: 12 },
  badge:     (color) => ({ display: "inline-block", padding: "2px 8px", borderRadius: 8, fontSize: 11, fontWeight: 700, background: color + "22", color, border: `1px solid ${color}44` }),
  dot:       (on) => ({ width: 8, height: 8, borderRadius: "50%", background: on ? "#4ade80" : "#475569", display: "inline-block", marginRight: 6 }),
  row:       { display: "flex", alignItems: "center", gap: 8, marginBottom: 8 },
  label:     { fontSize: 11, color: "#64748b", minWidth: 120 },
  val:       { fontSize: 12, color: "#e2e8f0", fontWeight: 600 },
  // Container list
  cList:     { flex: 1, overflowY: "auto", padding: "8px 0" },
  cItem:     (active) => ({ padding: "10px 16px", cursor: "pointer", borderLeft: `3px solid ${active ? "#6366f1" : "transparent"}`, background: active ? "#1a1d2e" : "transparent", transition: "all .1s" }),
  cName:     { fontSize: 12, fontWeight: 700, color: "#e2e8f0", marginBottom: 2, fontFamily: "monospace" },
  cStatus:   { fontSize: 11, color: "#64748b" },
  // Workspace list
  wsItem:    (active) => ({ padding: "10px 16px", cursor: "pointer", borderLeft: `3px solid ${active ? "#22d3ee" : "transparent"}`, background: active ? "#0e2a30" : "transparent", transition: "all .1s" }),
  wsName:    { fontSize: 11, fontFamily: "monospace", color: "#94a3b8", marginBottom: 2 },
  // Log box
  logBox:    { background: "#0a0c14", borderRadius: 6, padding: "12px 14px", fontFamily: "monospace", fontSize: 11, color: "#94a3b8", whiteSpace: "pre-wrap", maxHeight: 320, overflowY: "auto", border: "1px solid #1e2130" },
  // Tabs
  tabs:      { display: "flex", gap: 4, marginBottom: 16 },
  tab:       (active) => ({ padding: "5px 14px", borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: "pointer", border: `1px solid ${active ? "#6366f1" : "#2d3148"}`, background: active ? "#1e1f3a" : "transparent", color: active ? "#818cf8" : "#64748b" }),
  // Status colors
  statusColor: (s) => s === "success" ? "#4ade80" : s === "failed" ? "#f87171" : s === "running" ? "#60a5fa" : "#94a3b8",
  refreshBtn: { background: "none", border: "1px solid #2d3148", borderRadius: 6, color: "#64748b", padding: "4px 10px", cursor: "pointer", fontSize: 11 },
};

const fmt = (iso) => iso ? new Date(iso).toLocaleTimeString() : "—";

export default function SandboxMonitorPage() {
  const [status,     setStatus]     = useState(null);
  const [containers, setContainers] = useState([]);
  const [workspaces, setWorkspaces] = useState([]);
  const [selected,   setSelected]   = useState(null);  // { type: "container"|"workspace", id }
  const [detail,     setDetail]     = useState(null);
  const [tab,        setTab]        = useState("output"); // output | log | input
  const [autoRefresh, setAutoRefresh] = useState(true);
  const timerRef = useRef(null);

  const loadAll = useCallback(async () => {
    const [st, ct, ws] = await Promise.all([
      fetchStatus().catch(() => null),
      fetchContainers().catch(() => ({ containers: [] })),
      fetchWorkspaces().catch(() => ({ workspaces: [] })),
    ]);
    setStatus(st);
    setContainers(ct.containers || []);
    setWorkspaces(ws.workspaces || []);
  }, []);

  // Auto-refresh every 3s when any container is running
  useEffect(() => {
    loadAll();
    if (!autoRefresh) return;
    timerRef.current = setInterval(loadAll, 3000);
    return () => clearInterval(timerRef.current);
  }, [loadAll, autoRefresh]);

  const selectWorkspace = async (ws) => {
    setSelected({ type: "workspace", id: ws.id });
    setTab("output");
    try {
      const d = await fetchWorkspace(ws.id);
      setDetail(d);
    } catch {
      setDetail(null);
    }
  };

  const selectContainer = (c) => {
    setSelected({ type: "container", id: c.id });
    setDetail(null);
  };

  const hasRunning = containers.some(c => c.running);

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={s.title}>🐳 Sandbox Monitor</div>
            <div style={s.sub}>Live view of Docker sandbox containers and workspace files</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {hasRunning && <span style={{ ...s.badge("#60a5fa"), animation: "pulse 1s infinite" }}>● Live</span>}
            <button style={s.refreshBtn} onClick={loadAll}>↻ Refresh</button>
            <button
              style={{ ...s.refreshBtn, color: autoRefresh ? "#4ade80" : "#64748b", borderColor: autoRefresh ? "#166534" : "#2d3148" }}
              onClick={() => setAutoRefresh(p => !p)}
            >
              {autoRefresh ? "⏸ Auto" : "▶ Auto"}
            </button>
          </div>
        </div>

        {/* Status bar */}
        {status && (
          <div style={{ display: "flex", gap: 20, marginTop: 12, flexWrap: "wrap" }}>
            <span><span style={s.dot(status.sandbox_mode)} /><span style={{ fontSize: 11, color: "#94a3b8" }}>Sandbox {status.sandbox_mode ? "ON" : "OFF"}</span></span>
            <span><span style={s.dot(status.docker_available)} /><span style={{ fontSize: 11, color: "#94a3b8" }}>Docker {status.docker_available ? status.docker_version : "unavailable"}</span></span>
            <span><span style={s.dot(status.agent_image_ready)} /><span style={{ fontSize: 11, color: "#94a3b8" }}>agent-runner image {status.agent_image_ready ? "ready" : "not built"}</span></span>
            {!status.sandbox_mode && (
              <span style={{ fontSize: 11, color: "#f59e0b" }}>⚠ Set SANDBOX_MODE=true in docker-compose.yml to enable sandboxed execution</span>
            )}
            {status.sandbox_mode && !status.agent_image_ready && (
              <span style={{ fontSize: 11, color: "#f87171" }}>⚠ Run: docker build -f backend/agent_runner.Dockerfile -t agent-runner:latest ./backend</span>
            )}
          </div>
        )}
      </div>

      <div style={s.body}>
        {/* Left panel — containers + workspaces */}
        <div style={s.left}>
          {/* Containers */}
          <div style={{ padding: "12px 16px 6px", borderBottom: "1px solid #1e2130", flexShrink: 0 }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#475569" }}>
              Containers ({containers.length})
            </div>
          </div>
          <div style={{ maxHeight: 220, overflowY: "auto", borderBottom: "1px solid #1e2130" }}>
            {containers.length === 0 ? (
              <div style={{ padding: "12px 16px", fontSize: 11, color: "#475569" }}>
                No agent-run containers found.<br />Trigger a workflow to see containers here.
              </div>
            ) : containers.map(c => (
              <div key={c.id} style={s.cItem(selected?.id === c.id)} onClick={() => selectContainer(c)}>
                <div style={s.cName}>{c.name}</div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={s.badge(c.running ? "#4ade80" : "#475569")}>{c.running ? "running" : "exited"}</span>
                  <span style={s.cStatus}>{c.created_at}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Workspaces */}
          <div style={{ padding: "12px 16px 6px", flexShrink: 0 }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#475569" }}>
              Workspaces ({workspaces.length})
            </div>
          </div>
          <div style={s.cList}>
            {workspaces.length === 0 ? (
              <div style={{ padding: "12px 16px", fontSize: 11, color: "#475569" }}>No sandbox workspaces yet.</div>
            ) : workspaces.map(ws => (
              <div key={ws.id} style={s.wsItem(selected?.id === ws.id)} onClick={() => selectWorkspace(ws)}>
                <div style={s.wsName}>{ws.id}</div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={s.badge(s.statusColor(ws.status))}>{ws.status}</span>
                  <span style={{ fontSize: 10, color: "#475569" }}>{ws.files.length} files · {fmt(ws.modified)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right panel — detail */}
        <div style={s.right}>
          {!selected ? (
            <div style={{ textAlign: "center", marginTop: 60, color: "#475569", fontSize: 13 }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🐳</div>
              Select a container or workspace from the left to inspect it.
              {!status?.sandbox_mode && (
                <div style={{ marginTop: 20, padding: "14px 20px", background: "#1a1200", border: "1px solid #78350f", borderRadius: 10, fontSize: 12, color: "#f59e0b", maxWidth: 480, margin: "20px auto 0" }}>
                  Sandbox mode is currently OFF. Workflows run in-process inside the backend container.<br /><br />
                  To enable sandboxed execution:<br />
                  1. Set <code style={{ color: "#fbbf24" }}>SANDBOX_MODE=true</code> in docker-compose.yml<br />
                  2. Build the agent runner image:<br />
                  <code style={{ color: "#fbbf24" }}>docker build -f backend/agent_runner.Dockerfile -t agent-runner:latest ./backend</code><br />
                  3. Restart: <code style={{ color: "#fbbf24" }}>docker-compose up --build -d</code>
                </div>
              )}
            </div>
          ) : selected.type === "container" ? (
            <ContainerDetail container={containers.find(c => c.id === selected.id)} />
          ) : detail ? (
            <WorkspaceDetail detail={detail} tab={tab} setTab={setTab} />
          ) : (
            <div style={{ color: "#475569", fontSize: 12, marginTop: 40, textAlign: "center" }}>Loading...</div>
          )}
        </div>
      </div>
    </div>
  );
}

function ContainerDetail({ container }) {
  const [logs, setLogs] = useState("");
  useEffect(() => {
    if (!container) return;
    axios.get(`/sandbox/containers/${container.id}/logs`)
      .then(r => setLogs(r.data.logs + (r.data.stderr ? `\n[stderr]\n${r.data.stderr}` : "")))
      .catch(() => setLogs("Could not fetch logs"));
  }, [container?.id]);

  if (!container) return null;
  return (
    <div>
      <div style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9", marginBottom: 16, fontFamily: "monospace" }}>
        {container.name}
      </div>
      <div style={s.section}>
        <div style={s.secTitle}>Container Info</div>
        <div style={s.row}><span style={s.label}>ID</span><span style={{ ...s.val, fontFamily: "monospace" }}>{container.id}</span></div>
        <div style={s.row}><span style={s.label}>Status</span><span style={s.badge(container.running ? "#4ade80" : "#475569")}>{container.status}</span></div>
        <div style={s.row}><span style={s.label}>Created</span><span style={s.val}>{container.created_at}</span></div>
        <div style={s.row}><span style={s.label}>Image</span><span style={{ ...s.val, fontFamily: "monospace" }}>{container.image}</span></div>
      </div>
      <div style={s.section}>
        <div style={s.secTitle}>Container Logs</div>
        <div style={s.logBox}>{logs || "(no logs)"}</div>
      </div>
    </div>
  );
}

function WorkspaceDetail({ detail, tab, setTab }) {
  return (
    <div>
      <div style={{ fontSize: 14, fontWeight: 700, color: "#f1f5f9", marginBottom: 16, fontFamily: "monospace" }}>
        {detail.id}
      </div>

      {/* Files */}
      {detail.files.length > 0 && (
        <div style={s.section}>
          <div style={s.secTitle}>Workspace Files</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {detail.files.map(f => (
              <span key={f.name} style={{ padding: "3px 10px", background: "#0f1117", borderRadius: 6, fontSize: 11, fontFamily: "monospace", color: "#94a3b8", border: "1px solid #2d3148" }}>
                {f.name} <span style={{ color: "#475569" }}>({f.size}b)</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={s.tabs}>
        {["output", "log", "input"].map(t => (
          <div key={t} style={s.tab(tab === t)} onClick={() => setTab(t)}>
            {t === "output" ? "📤 Output" : t === "log" ? "📋 Run Log" : "📥 Task Input"}
          </div>
        ))}
      </div>

      {tab === "output" && (
        <div style={s.section}>
          <div style={s.secTitle}>Agent Output</div>
          {detail.output ? (
            <>
              <div style={s.row}>
                <span style={s.label}>Status</span>
                <span style={s.badge(detail.output.success ? "#4ade80" : "#f87171")}>
                  {detail.output.success ? "success" : "failed"}
                </span>
              </div>
              {detail.output.final_text && (
                <div style={{ ...s.logBox, color: "#a3e635", marginTop: 8 }}>{detail.output.final_text}</div>
              )}
              {detail.output.tool_usage?.length > 0 && (
                <>
                  <div style={{ ...s.secTitle, marginTop: 12 }}>Tool Calls</div>
                  <div style={s.logBox}>
                    {detail.output.tool_usage.map((line, i) => (
                      <div key={i} style={{ color: line.startsWith("PERMISSION") ? "#f87171" : line.startsWith("🔧") ? "#818cf8" : "#94a3b8" }}>
                        {line}
                      </div>
                    ))}
                  </div>
                </>
              )}
              {detail.output.error && (
                <div style={{ marginTop: 8, padding: "8px 12px", background: "#450a0a", borderRadius: 6, fontSize: 12, color: "#f87171" }}>
                  {detail.output.error}
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: 12, color: "#475569" }}>No output yet — task may still be running.</div>
          )}
        </div>
      )}

      {tab === "log" && (
        <div style={s.section}>
          <div style={s.secTitle}>Run Log</div>
          <div style={s.logBox}>{detail.run_log || "(no log file yet)"}</div>
        </div>
      )}

      {tab === "input" && (
        <div style={s.section}>
          <div style={s.secTitle}>Task Input (api_key redacted)</div>
          <div style={s.logBox}>{detail.task_input ? JSON.stringify(detail.task_input, null, 2) : "(no input file)"}</div>
        </div>
      )}
    </div>
  );
}
