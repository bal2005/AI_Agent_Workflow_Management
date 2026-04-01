import React, { useState, useEffect, useCallback } from "react";
import { fetchTasks, fetchTaskRuns, fetchTaskSchedules, fetchAgentToolAccess, runTask } from "../api";

// ── Styles (mirrors SchedulerPage) ────────────────────────────────────────────
const s = {
  layout:       { display: "flex", flex: 1, overflow: "hidden", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif" },
  left:         { width: 260, minWidth: 260, background: "#13151f", borderRight: "1px solid #1e2130", display: "flex", flexDirection: "column" },
  leftHead:     { padding: "18px 16px 12px", borderBottom: "1px solid #1e2130" },
  leftTitle:    { fontSize: 13, fontWeight: 700, color: "#f1f5f9", marginBottom: 8 },
  searchInput:  { width: "100%", padding: "7px 10px", borderRadius: 7, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 12, outline: "none", boxSizing: "border-box" },
  taskList:     { flex: 1, overflowY: "auto", padding: "6px 0" },
  taskItem:     (active) => ({
    padding: "10px 16px", cursor: "pointer",
    borderLeft: `3px solid ${active ? "#6366f1" : "transparent"}`,
    background: active ? "#1e2130" : "transparent", transition: "all .1s",
  }),
  taskName:     { fontSize: 13, fontWeight: 600, color: "#e2e8f0", marginBottom: 2 },
  taskMeta:     { fontSize: 11, color: "#475569" },
  statusDot:    (st) => ({ width: 7, height: 7, borderRadius: "50%", background: st === "active" ? "#4ade80" : "#475569", display: "inline-block", marginLeft: 6 }),
  // right
  right:        { flex: 1, overflowY: "auto", padding: "28px 36px" },
  pageTitle:    { fontSize: 22, fontWeight: 700, color: "#f8fafc", marginBottom: 4 },
  pageSub:      { fontSize: 13, color: "#64748b", marginBottom: 20 },
  section:      { background: "#1e2130", borderRadius: 12, padding: "20px 24px", marginBottom: 16, border: "1px solid #2d3148" },
  secTitle:     { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 14 },
  // badges
  badge:        (color) => {
    const map = {
      standalone: { bg: "#1e3a5f", fg: "#60a5fa" },
      workflow:   { bg: "#1a2e1a", fg: "#4ade80" },
      success:    { bg: "#14532d", fg: "#4ade80" },
      failed:     { bg: "#450a0a", fg: "#f87171" },
      running:    { bg: "#1e3a5f", fg: "#60a5fa" },
      pending:    { bg: "#1c1a10", fg: "#fbbf24" },
      draft:      { bg: "#1c1a10", fg: "#fbbf24" },
      active:     { bg: "#14532d", fg: "#4ade80" },
      manual:     { bg: "#2d1f3a", fg: "#c084fc" },
      scheduler:  { bg: "#1a2e1a", fg: "#4ade80" },
    };
    const c = map[color] || { bg: "#2d3148", fg: "#94a3b8" };
    return { display: "inline-block", padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700, background: c.bg, color: c.fg };
  },
  // detail grid
  grid2:        { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 12 },
  grid3:        { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 12 },
  fieldLabel:   { fontSize: 11, color: "#475569", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 4 },
  fieldValue:   { fontSize: 13, color: "#e2e8f0" },
  monoBox:      { background: "#0a0c14", borderRadius: 6, padding: "10px 12px", fontFamily: "monospace", fontSize: 12, color: "#a3e635", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 180, overflowY: "auto" },
  // table (same as scheduler)
  table:        { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th:           { textAlign: "left", padding: "8px 10px", color: "#475569", fontWeight: 600, borderBottom: "1px solid #2d3148", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.8 },
  td:           { padding: "9px 10px", borderBottom: "1px solid #1e2130", color: "#94a3b8", verticalAlign: "top" },
  statusBadge:  (st) => ({
    display: "inline-block", padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700,
    background: st === "success" ? "#14532d" : st === "failed" ? "#450a0a" : st === "running" ? "#1e3a5f" : "#1e2130",
    color: st === "success" ? "#4ade80" : st === "failed" ? "#f87171" : st === "running" ? "#60a5fa" : "#64748b",
  }),
  logBox:       { background: "#0a0c14", borderRadius: 6, padding: "10px 12px", fontFamily: "monospace", fontSize: 11, color: "#94a3b8", whiteSpace: "pre-wrap", maxHeight: 200, overflowY: "auto", marginTop: 6 },
  // summary cards
  cards:        { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 16 },
  card:         { background: "#1e2130", borderRadius: 10, padding: "16px 18px", border: "1px solid #2d3148" },
  cardVal:      { fontSize: 26, fontWeight: 700, color: "#f1f5f9", marginBottom: 2 },
  cardLabel:    { fontSize: 11, color: "#475569", textTransform: "uppercase", letterSpacing: 0.8 },
  // buttons
  btnRow:       { display: "flex", gap: 10, marginTop: 6, flexWrap: "wrap", alignItems: "center" },
  btn:          { padding: "8px 18px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600 },
  btnPrimary:   { background: "#6366f1", color: "#fff" },
  btnSecondary: { background: "#2d3148", color: "#cbd5e1" },
  btnRun:       { background: "#0f2a1a", border: "1px solid #166534", color: "#4ade80", padding: "8px 18px", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 700 },
};

const fmt = (dt) => dt ? new Date(dt).toLocaleString() : "—";
const dur = (s) => s != null ? `${s.toFixed(1)}s` : "—";

export default function TaskDetailsPage({ taskId, onBack }) {
  const [allTasks, setAllTasks]       = useState([]);
  const [activeId, setActiveId]       = useState(taskId || null);
  const [task, setTask]               = useState(null);
  const [runs, setRuns]               = useState([]);
  const [schedules, setSchedules]     = useState([]);
  const [expandedRun, setExpandedRun] = useState(null);
  const [running, setRunning]         = useState(false);
  const [msg, setMsg]                 = useState({ type: "", text: "" });
  const [loading, setLoading]         = useState(true);
  const [search, setSearch]           = useState("");
  const [agentWebAccess, setAgentWebAccess] = useState(null);

  // Load task list always
  const loadList = useCallback(async () => {
    const list = await fetchTasks().catch(() => []);
    setAllTasks(list);
    setLoading(false);
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  // Load detail when activeId changes
  const loadDetail = useCallback(async (id) => {
    if (!id) return;
    const [list, r, sc] = await Promise.all([
      fetchTasks().catch(() => []),
      fetchTaskRuns(id).catch(() => []),
      fetchTaskSchedules(id).catch(() => []),
    ]);
    setAllTasks(list);
    setTask(list.find(x => x.id === id) || null);
    setRuns(r);
    setSchedules(sc);
    setExpandedRun(null);
    setMsg({ type: "", text: "" });
  }, []);

  useEffect(() => {
    if (activeId) loadDetail(activeId);
    else { setTask(null); setRuns([]); setSchedules([]); }
  }, [activeId, loadDetail]);

  useEffect(() => {
    const loadAccess = async () => {
      if (!task?.agent_id) {
        setAgentWebAccess(null);
        return;
      }
      try {
        const rows = await fetchAgentToolAccess(task.agent_id);
        const webRow = rows.find(r => r.tool_key === "web" || r.tool_key === "web_search");
        setAgentWebAccess(webRow || null);
      } catch {
        setAgentWebAccess(null);
      }
    };
    loadAccess();
  }, [task?.agent_id]);

  useEffect(() => { if (taskId) setActiveId(taskId); }, [taskId]);

  const handleRun = async () => {
    setRunning(true); setMsg({ type: "", text: "" });
    try {
      const result = await runTask(activeId);
      setMsg({ type: "success", text: `Run completed — status: ${result.status}` });
      await loadDetail(activeId);
    } catch (e) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message });
    } finally { setRunning(false); }
  };

  const isWorkflow = schedules.length > 0;
  const lastRun = runs[0] || null;
  const totalRuns = runs.length;
  const successRuns = runs.filter(r => r.status === "success").length;
  const failedRuns = runs.filter(r => r.status === "failed").length;

  const filtered = allTasks.filter(t =>
    !search || t.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={s.layout}>
      {/* ── Left Panel ── */}
      <aside style={s.left}>
        <div style={s.leftHead}>
          <div style={s.leftTitle}>📊 Task Details</div>
          <input
            style={s.searchInput}
            placeholder="Search tasks..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div style={s.taskList}>
          {loading && <div style={{ padding: "14px 16px", fontSize: 12, color: "#475569" }}>Loading...</div>}
          {!loading && filtered.length === 0 && (
            <div style={{ padding: "14px 16px", fontSize: 12, color: "#475569" }}>No tasks found</div>
          )}
          {filtered.map(t => (
            <div
              key={t.id}
              style={s.taskItem(activeId === t.id)}
              onClick={() => setActiveId(t.id)}
              onMouseEnter={e => { if (activeId !== t.id) e.currentTarget.style.background = "#1a1d2e"; }}
              onMouseLeave={e => { if (activeId !== t.id) e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{ display: "flex", alignItems: "center" }}>
                <span style={s.taskName}>{t.name}</span>
                <span style={s.statusDot(t.status)} />
              </div>
              <div style={s.taskMeta}>
                {t.agent ? `${t.agent.domain?.name} › ${t.agent.name}` : "No agent"}
              </div>
              <div style={{ marginTop: 3 }}>
                <span style={s.badge(t.status)}>{t.status}</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* ── Right Panel ── */}
      <div style={s.right}>
        {!activeId || !task ? (
          <div style={{ color: "#475569", fontSize: 14, marginTop: 60, textAlign: "center" }}>
            Select a task from the left panel to view its details
          </div>
        ) : (
          <>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 4 }}>
              <div>
                <div style={s.pageTitle}>{task.name}</div>
                <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                  <span style={s.badge(isWorkflow ? "workflow" : "standalone")}>
                    {isWorkflow ? "⛓ Workflow-linked" : "◎ Standalone"}
                  </span>
                  <span style={s.badge(task.status)}>{task.status}</span>
                  {lastRun && <span style={s.statusBadge(lastRun.status)}>last: {lastRun.status}</span>}
                </div>
              </div>
              {onBack && (
                <button style={{ ...s.btn, ...s.btnSecondary, fontSize: 12 }} onClick={onBack}>
                  ← Back
                </button>
              )}
            </div>
            <div style={s.pageSub}>
              Last run: {lastRun ? fmt(lastRun.started_at) : "never"}
            </div>

            {/* ── Section 1: Task Details ── */}
            <div style={s.section}>
              <div style={s.secTitle}>Task Details</div>
              <div style={s.grid3}>
                <div>
                  <div style={s.fieldLabel}>Task Name</div>
                  <div style={s.fieldValue}>{task.name}</div>
                </div>
                <div>
                  <div style={s.fieldLabel}>Status</div>
                  <span style={s.badge(task.status)}>{task.status}</span>
                </div>
                <div>
                  <div style={s.fieldLabel}>Task Type</div>
                  <span style={s.badge(isWorkflow ? "workflow" : "standalone")}>
                    {isWorkflow ? "Workflow-linked" : "Standalone"}
                  </span>
                </div>
                <div>
                  <div style={s.fieldLabel}>Created At</div>
                  <div style={s.fieldValue}>{fmt(task.created_at)}</div>
                </div>
                <div>
                  <div style={s.fieldLabel}>Updated At</div>
                  <div style={s.fieldValue}>{fmt(task.updated_at)}</div>
                </div>
                <div>
                  <div style={s.fieldLabel}>Tool Usage</div>
                  <div style={s.fieldValue}>{task.tool_usage_mode || "—"}</div>
                </div>
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={s.fieldLabel}>Description / Prompt</div>
                <div style={s.monoBox}>{task.description}</div>
              </div>
              {task.agent && (
                <div style={{ marginBottom: 12 }}>
                  <div style={s.fieldLabel}>Web Access</div>
                  <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8 }}>
                    Web permissions come from the linked agent. Update them in Tools Management.
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <span style={s.badge(agentWebAccess?.granted_permissions?.includes("perform_search") ? "workflow" : "draft")}>
                      perform_search
                    </span>
                    <span style={s.badge(agentWebAccess?.granted_permissions?.includes("open_result_links") ? "workflow" : "draft")}>
                      open_result_links
                    </span>
                  </div>
                </div>
              )}
              {task.workflow && (
                <div>
                  <div style={s.fieldLabel}>Workflow Steps</div>
                  <div style={s.monoBox}>
                    {task.workflow.split("\n").map((step, i) => step.trim() && (
                      <div key={i}><span style={{ color: "#475569" }}>{i + 1}. </span>{step}</div>
                    ))}
                  </div>
                </div>
              )}
              {isWorkflow && (
                <div style={{ marginTop: 12 }}>
                  <div style={s.fieldLabel}>Linked Schedules</div>
                  <table style={s.table}>
                    <thead>
                      <tr>
                        <th style={s.th}>Schedule</th>
                        <th style={s.th}>Trigger</th>
                        <th style={s.th}>Position</th>
                        <th style={s.th}>Active</th>
                      </tr>
                    </thead>
                    <tbody>
                      {schedules.map(sc => (
                        <tr key={sc.schedule_id}>
                          <td style={s.td}>{sc.schedule_name}</td>
                          <td style={s.td}><span style={s.badge(sc.trigger_type)}>{sc.trigger_type}</span></td>
                          <td style={s.td}>#{sc.position}</td>
                          <td style={s.td}><span style={s.statusBadge(sc.is_active ? "success" : "failed")}>{sc.is_active ? "yes" : "no"}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* ── Section 2: Actions ── */}
            <div style={s.section}>
              <div style={s.secTitle}>Execution Actions</div>
              <div style={s.btnRow}>
                <button style={s.btnRun} onClick={handleRun} disabled={running}>
                  {running ? "⏳ Running..." : "▶ Run Task"}
                </button>
                {lastRun && (
                  <button style={{ ...s.btn, ...s.btnSecondary }} onClick={handleRun} disabled={running}>
                    ↺ Re-run
                  </button>
                )}
                <button style={{ ...s.btn, ...s.btnSecondary }} onClick={() => loadDetail(activeId)}>
                  ⟳ Refresh
                </button>
              </div>
              {msg.text && (
                <div style={{ marginTop: 10, fontSize: 13, color: msg.type === "success" ? "#4ade80" : "#f87171" }}>
                  {msg.type === "success" ? "✓ " : "✗ "}{msg.text}
                </div>
              )}
            </div>

            {/* ── Section 3: Last Run Summary ── */}
            <div style={s.section}>
              <div style={s.secTitle}>Last Run Summary</div>
              {!lastRun ? (
                <div style={{ fontSize: 12, color: "#475569" }}>No runs yet. Click Run Task to execute.</div>
              ) : (
                <div style={s.grid3}>
                  <div>
                    <div style={s.fieldLabel}>Status</div>
                    <span style={s.statusBadge(lastRun.status)}>{lastRun.status}</span>
                  </div>
                  <div>
                    <div style={s.fieldLabel}>Triggered By</div>
                    <span style={s.badge(lastRun.triggered_by)}>{lastRun.triggered_by}</span>
                  </div>
                  <div>
                    <div style={s.fieldLabel}>Duration</div>
                    <div style={s.fieldValue}>{dur(lastRun.duration_seconds)}</div>
                  </div>
                  <div>
                    <div style={s.fieldLabel}>Started At</div>
                    <div style={s.fieldValue}>{fmt(lastRun.started_at)}</div>
                  </div>
                  <div>
                    <div style={s.fieldLabel}>Finished At</div>
                    <div style={s.fieldValue}>{fmt(lastRun.finished_at)}</div>
                  </div>
                </div>
              )}
              {lastRun?.output && (
                <div style={{ marginTop: 10 }}>
                  <div style={s.fieldLabel}>Output</div>
                  <div style={s.logBox}>{lastRun.output}</div>
                </div>
              )}
              {lastRun?.error && (
                <div style={{ marginTop: 10 }}>
                  <div style={{ ...s.fieldLabel, color: "#f87171" }}>Error</div>
                  <div style={{ ...s.logBox, color: "#f87171" }}>{lastRun.error}</div>
                </div>
              )}
            </div>

            {/* ── Section 4: Run History Table ── */}
            <div style={{ ...s.section, marginTop: 4 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
                <div style={s.secTitle}>Run History ({totalRuns})</div>
                <button
                  style={{ background: "none", border: "1px solid #2d3148", borderRadius: 6, color: "#64748b", padding: "4px 10px", cursor: "pointer", fontSize: 11 }}
                  onClick={() => loadDetail(activeId)}
                >↻ Refresh</button>
              </div>
              {runs.length === 0 ? (
                <div style={{ fontSize: 12, color: "#475569" }}>No run history yet.</div>
              ) : (
                <table style={s.table}>
                  <thead>
                    <tr>
                      <th style={s.th}>Run #</th>
                      <th style={s.th}>Trigger</th>
                      <th style={s.th}>Status</th>
                      <th style={s.th}>Started</th>
                      <th style={s.th}>Finished</th>
                      <th style={s.th}>Duration</th>
                      <th style={s.th}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map(run => {
                      const isExp = expandedRun === run.id;
                      return (
                        <React.Fragment key={run.id}>
                          <tr>
                            <td style={s.td}>#{run.id}</td>
                            <td style={s.td}><span style={s.badge(run.triggered_by)}>{run.triggered_by}</span></td>
                            <td style={s.td}><span style={s.statusBadge(run.status)}>{run.status}</span></td>
                            <td style={s.td}>{fmt(run.started_at)}</td>
                            <td style={s.td}>{fmt(run.finished_at)}</td>
                            <td style={s.td}>{dur(run.duration_seconds)}</td>
                            <td style={s.td}>
                              <button
                                style={{ background: "none", border: "none", color: "#6366f1", cursor: "pointer", fontSize: 11 }}
                                onClick={() => setExpandedRun(isExp ? null : run.id)}
                              >
                                {isExp ? "▲ hide" : "▼ logs"}
                              </button>
                            </td>
                          </tr>
                          {isExp && (
                            <tr>
                              <td colSpan={7} style={{ ...s.td, background: "#0f1117", padding: "12px 16px" }}>
                                {run.logs?.length > 0 && (
                                  <div style={s.logBox}>
                                    {run.logs.map((line, i) => (
                                      <div key={i} style={{ color: line.startsWith("🔧") ? "#818cf8" : line.startsWith("   →") ? "#475569" : "#a3e635" }}>
                                        {line}
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {run.output && (
                                  <div style={{ ...s.logBox, marginTop: 6, color: "#a3e635" }}>{run.output}</div>
                                )}
                                {run.error && (
                                  <div style={{ ...s.logBox, marginTop: 6, color: "#f87171" }}>{run.error}</div>
                                )}
                                {!run.logs?.length && !run.output && !run.error && (
                                  <div style={{ fontSize: 12, color: "#475569" }}>No logs recorded.</div>
                                )}
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {/* ── Summary Cards ── */}
            <div style={s.cards}>
              <div style={s.card}>
                <div style={s.cardVal}>{totalRuns}</div>
                <div style={s.cardLabel}>Total Runs</div>
              </div>
              <div style={s.card}>
                <div style={{ ...s.cardVal, color: "#4ade80" }}>{successRuns}</div>
                <div style={s.cardLabel}>Successful</div>
              </div>
              <div style={s.card}>
                <div style={{ ...s.cardVal, color: "#f87171" }}>{failedRuns}</div>
                <div style={s.cardLabel}>Failed</div>
              </div>
              <div style={s.card}>
                <div style={{ ...s.cardVal, fontSize: 16 }}>{lastRun ? new Date(lastRun.created_at).toLocaleDateString() : "—"}</div>
                <div style={s.cardLabel}>Last Run</div>
              </div>
            </div>

            {/* ── Section 5: Reproducibility ── */}
            <div style={{ ...s.section, marginTop: 16 }}>
              <div style={s.secTitle}>Reproducibility — Saved Configuration</div>

              {/* Agent */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#6366f1", marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.8 }}>
                  A. Agent Snapshot
                </div>
                {task.agent ? (
                  <>
                    <table style={s.table}>
                      <thead>
                        <tr>
                          <th style={s.th}>Agent</th>
                          <th style={s.th}>Domain</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td style={s.td}>{task.agent.name}</td>
                          <td style={s.td}>{task.agent.domain?.name || "—"}</td>
                        </tr>
                      </tbody>
                    </table>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 14 }}>
                      <div>
                        <div style={{ ...s.fieldLabel, marginBottom: 6 }}>
                          Domain Prompt
                          {!task.agent.domain?.domain_prompt && (
                            <span style={{ color: "#f87171", marginLeft: 8 }}>⚠ not set</span>
                          )}
                        </div>
                        <div style={{ ...s.logBox, maxHeight: 220, color: "#a3e635" }}>
                          {task.agent.domain?.domain_prompt || "— no domain prompt set —"}
                        </div>
                      </div>
                      <div>
                        <div style={{ ...s.fieldLabel, marginBottom: 6 }}>Agent Prompt (Skill)</div>
                        <div style={{ ...s.logBox, maxHeight: 220, color: "#a3e635" }}>
                          {task.agent.system_prompt}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div style={{ fontSize: 12, color: "#475569" }}>No agent linked.</div>
                )}
                {task.llm_system_behavior && (
                  <div style={{ marginTop: 10 }}>
                    <div style={s.fieldLabel}>System Behavior Override</div>
                    <div style={s.monoBox}>{task.llm_system_behavior}</div>
                  </div>
                )}
              </div>

              {/* LLM Config */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#6366f1", marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.8 }}>
                  B. LLM Configuration
                </div>
                <table style={s.table}>
                  <thead>
                    <tr>
                      <th style={s.th}>Provider</th>
                      <th style={s.th}>Model</th>
                      <th style={s.th}>Temperature</th>
                      <th style={s.th}>Max Tokens</th>
                      <th style={s.th}>Top P</th>
                      <th style={s.th}>Config ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={s.td}>{task.llm_provider || "— active config —"}</td>
                      <td style={s.td}>{task.llm_model || "— active config —"}</td>
                      <td style={s.td}>{task.llm_temperature ?? "— inherited —"}</td>
                      <td style={s.td}>{task.llm_max_tokens ?? "— inherited —"}</td>
                      <td style={s.td}>{task.llm_top_p ?? "— inherited —"}</td>
                      <td style={s.td}>{task.llm_config_id ? `#${task.llm_config_id}` : "—"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
