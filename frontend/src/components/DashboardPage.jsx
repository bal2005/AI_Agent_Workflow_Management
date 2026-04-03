/**
 * DashboardPage — operational overview of the Agent Studio system.
 * Replaces the static landing page as the default route.
 */
import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { fetchDashboardSummary } from "../api";

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmt = (iso) => iso ? new Date(iso).toLocaleString() : "—";
const dur = (s) => s != null ? `${s.toFixed(1)}s` : "—";

// ── Styles ────────────────────────────────────────────────────────────────────
const s = {
  page:      { flex: 1, overflowY: "auto", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif", padding: "28px 36px 60px" },
  header:    { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 },
  title:     { fontSize: 22, fontWeight: 700, color: "#f8fafc" },
  sub:       { fontSize: 13, color: "#475569", marginTop: 3 },
  refreshBtn:{ padding: "7px 16px", borderRadius: 8, border: "1px solid #2d3148", background: "none", color: "#94a3b8", fontSize: 12, fontWeight: 600, cursor: "pointer" },

  // Section
  secTitle:  { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#475569", marginBottom: 14 },
  section:   { marginBottom: 32 },

  // KPI grid
  kpiGrid:   { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 },
  kpiGrid3:  { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 },
  kpiCard:   (accent) => ({
    background: "#1e2130", borderRadius: 12, padding: "18px 20px",
    border: `1px solid ${accent || "#2d3148"}`,
    cursor: "default",
  }),
  kpiVal:    (color) => ({ fontSize: 28, fontWeight: 800, color: color || "#f1f5f9", marginBottom: 4, lineHeight: 1 }),
  kpiLabel:  { fontSize: 11, color: "#475569", textTransform: "uppercase", letterSpacing: 0.8 },
  kpiSub:    { fontSize: 11, color: "#64748b", marginTop: 4 },

  // Table
  tableWrap: { background: "#1e2130", borderRadius: 12, border: "1px solid #2d3148", overflow: "hidden" },
  table:     { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th:        { textAlign: "left", padding: "10px 14px", color: "#475569", fontWeight: 600, borderBottom: "1px solid #2d3148", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.8, background: "#13151f" },
  td:        { padding: "11px 14px", borderBottom: "1px solid #1a1d2e", color: "#94a3b8", verticalAlign: "middle" },
  tdName:    { color: "#e2e8f0", fontWeight: 600 },

  // Badges
  statusBadge: (st) => ({
    display: "inline-block", padding: "2px 9px", borderRadius: 10, fontSize: 11, fontWeight: 700,
    background: st === "success" ? "#14532d" : st === "failed" ? "#450a0a" : st === "running" ? "#1e3a5f" : "#1e2130",
    color:      st === "success" ? "#4ade80" : st === "failed" ? "#f87171" : st === "running" ? "#60a5fa" : "#64748b",
  }),
  triggerBadge: (t) => ({
    display: "inline-block", padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700,
    background: t === "scheduler" ? "#1a2e1a" : "#2d1f3a",
    color:      t === "scheduler" ? "#4ade80" : "#c084fc",
  }),

  // Trend bar chart
  trendWrap: { background: "#1e2130", borderRadius: 12, border: "1px solid #2d3148", padding: "18px 20px" },
  trendBars: { display: "flex", alignItems: "flex-end", gap: 8, height: 80, marginTop: 12 },
  trendBar:  (pct) => ({
    flex: 1, background: "#6366f1", borderRadius: "4px 4px 0 0",
    height: `${Math.max(pct * 100, 4)}%`, minHeight: 4,
    transition: "height .3s",
  }),
  trendLabel:{ display: "flex", gap: 8, marginTop: 6 },
  trendLbl:  { flex: 1, textAlign: "center", fontSize: 10, color: "#475569" },

  // Status donut (simple bar)
  statusRow: { display: "flex", gap: 8, marginTop: 10 },
  statusSeg: (color, pct) => ({
    height: 8, borderRadius: 4, background: color,
    width: `${pct}%`, minWidth: pct > 0 ? 4 : 0,
    transition: "width .3s",
  }),

  // Insight cards
  insightGrid: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 },
  insightCard: { background: "#1e2130", borderRadius: 12, padding: "16px 18px", border: "1px solid #2d3148" },
  insightVal:  { fontSize: 22, fontWeight: 800, color: "#f1f5f9", marginBottom: 4 },
  insightLbl:  { fontSize: 11, color: "#475569", textTransform: "uppercase", letterSpacing: 0.8 },

  // Empty / loading
  empty:     { color: "#475569", fontSize: 13, padding: "24px 14px", textAlign: "center" },
  loading:   { color: "#475569", fontSize: 13, padding: "60px 0", textAlign: "center" },

  // Two-col layout
  twoCol:    { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 },

  // Log modal
  overlay:   { position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 },
  modal:     { background: "#13151f", border: "1px solid #2d3148", borderRadius: 14, width: "100%", maxWidth: 820, maxHeight: "88vh", display: "flex", flexDirection: "column", overflow: "hidden" },
  modalHead: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 22px", borderBottom: "1px solid #1e2130", flexShrink: 0 },
  modalTitle:{ fontSize: 15, fontWeight: 700, color: "#f8fafc" },
  closeBtn:  { background: "none", border: "none", color: "#64748b", fontSize: 20, cursor: "pointer", lineHeight: 1, padding: "2px 6px" },
  modalBody: { overflowY: "auto", padding: "18px 22px", flex: 1 },
  logBox:    { background: "#0a0c14", borderRadius: 6, padding: "10px 14px", fontFamily: "monospace", fontSize: 11, color: "#94a3b8", whiteSpace: "pre-wrap", maxHeight: 220, overflowY: "auto", border: "1px solid #1e2130", marginTop: 6 },
  taskBlock: { background: "#1e2130", borderRadius: 8, padding: "12px 16px", marginBottom: 10, border: "1px solid #2d3148" },
  viewBtn:   { background: "none", border: "1px solid #2d3148", borderRadius: 6, color: "#6366f1", cursor: "pointer", fontSize: 11, padding: "3px 10px", fontWeight: 600 },
};

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiCard({ value, label, sub, color, accent, onClick }) {
  return (
    <div style={{ ...s.kpiCard(accent), cursor: onClick ? "pointer" : "default" }} onClick={onClick}>
      <div style={s.kpiVal(color)}>{value ?? "—"}</div>
      <div style={s.kpiLabel}>{label}</div>
      {sub && <div style={s.kpiSub}>{sub}</div>}
    </div>
  );
}

function RunTable({ runs, columns, emptyMsg }) {
  if (!runs || runs.length === 0) {
    return <div style={s.empty}>{emptyMsg || "No data"}</div>;
  }
  return (
    <table style={s.table}>
      <thead>
        <tr>{columns.map(c => <th key={c.key} style={s.th}>{c.label}</th>)}</tr>
      </thead>
      <tbody>
        {runs.map((row, i) => (
          <tr key={i} onMouseEnter={e => e.currentTarget.style.background = "#1a1d2e"} onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
            {columns.map(c => (
              <td key={c.key} style={{ ...s.td, ...(c.bold ? s.tdName : {}) }}>
                {c.render ? c.render(row) : row[c.key] ?? "—"}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TrendChart({ data }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map(d => d.runs), 1);
  return (
    <div>
      <div style={s.trendBars}>
        {data.map((d, i) => (
          <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", height: "100%", justifyContent: "flex-end" }}>
            <div style={{ ...s.trendBar(d.runs / max), width: "100%" }} title={`${d.runs} runs`} />
          </div>
        ))}
      </div>
      <div style={s.trendLabel}>
        {data.map((d, i) => <span key={i} style={s.trendLbl}>{d.date}</span>)}
      </div>
    </div>
  );
}

function StatusBar({ breakdown, total }) {
  if (!total) return <div style={{ ...s.kpiSub, marginTop: 8 }}>No runs yet</div>;
  const colors = { success: "#4ade80", failed: "#f87171", running: "#60a5fa", pending: "#475569" };
  return (
    <div>
      <div style={s.statusRow}>
        {breakdown.map(b => (
          b.count > 0 && (
            <div key={b.status} style={s.statusSeg(colors[b.status] || "#475569", (b.count / total) * 100)} title={`${b.status}: ${b.count}`} />
          )
        ))}
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 8, flexWrap: "wrap" }}>
        {breakdown.filter(b => b.count > 0).map(b => (
          <span key={b.status} style={{ fontSize: 11, color: colors[b.status] || "#475569" }}>
            ● {b.status} {b.count}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Log Modal ─────────────────────────────────────────────────────────────────

/**
 * LogModal — shows execution logs for a schedule run or a single task run.
 * For schedule runs: shows each task as a collapsible block with output + logs.
 * For task runs: shows output + logs directly.
 */
function LogModal({ item, type, onClose }) {
  if (!item) return null;

  const handleOverlay = (e) => { if (e.target === e.currentTarget) onClose(); };

  return (
    <div style={s.overlay} onClick={handleOverlay}>
      <div style={s.modal}>
        {/* Header */}
        <div style={s.modalHead}>
          <div>
            <div style={s.modalTitle}>
              {type === "schedule"
                ? `Schedule Run #${item.id} — ${item.schedule_name}`
                : `Task Run — ${item.task_name}`}
            </div>
            <div style={{ fontSize: 11, color: "#475569", marginTop: 3 }}>
              <span style={s.statusBadge(item.status)}>{item.status}</span>
              {" "}{fmt(item.started_at)} · {dur(item.duration_s ?? item.duration_seconds)}
            </div>
          </div>
          <button style={s.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div style={s.modalBody}>
          {/* Schedule run: show each task block */}
          {type === "schedule" && (
            <>
              {item.error && (
                <div style={{ background: "#450a0a", border: "1px solid #7f1d1d", borderRadius: 8, padding: "10px 14px", marginBottom: 14, fontSize: 12, color: "#f87171" }}>
                  ✗ Run Error: {item.error}
                </div>
              )}
              {(!item.task_runs || item.task_runs.length === 0) ? (
                <div style={{ color: "#475569", fontSize: 13 }}>No task runs recorded.</div>
              ) : (
                item.task_runs.map((tr, i) => (
                  <TaskLogBlock key={tr.id} tr={tr} index={i} />
                ))
              )}
            </>
          )}

          {/* Single task run */}
          {type === "task" && (
            <TaskLogBlock tr={item} index={0} expanded />
          )}
        </div>
      </div>
    </div>
  );
}

function TaskLogBlock({ tr, index, expanded: initExpanded = false }) {
  const [open, setOpen] = useState(initExpanded);

  return (
    <div style={s.taskBlock}>
      {/* Task header — click to expand */}
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", userSelect: "none" }}
        onClick={() => setOpen(p => !p)}
      >
        <span style={{ fontSize: 11, color: "#475569", minWidth: 20 }}>{index + 1}.</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: "#e2e8f0", flex: 1 }}>
          {tr.task_name || `Task #${tr.task_id || tr.id}`}
        </span>
        <span style={s.statusBadge(tr.status)}>{tr.status}</span>
        {tr.duration_s != null && <span style={{ fontSize: 11, color: "#475569" }}>{dur(tr.duration_s)}</span>}
        {tr.duration_seconds != null && <span style={{ fontSize: 11, color: "#475569" }}>{dur(tr.duration_seconds)}</span>}
        <span style={{ fontSize: 12, color: "#475569" }}>{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div style={{ marginTop: 12 }}>
          {/* Output */}
          {tr.output && (
            <>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, color: "#475569", marginBottom: 4 }}>Output</div>
              <div style={{ ...s.logBox, color: "#a3e635" }}>{tr.output}</div>
            </>
          )}

          {/* Tool call logs */}
          {tr.logs && tr.logs.length > 0 && (
            <>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, color: "#475569", marginTop: 10, marginBottom: 4 }}>
                Execution Logs ({tr.logs.length} steps)
              </div>
              <div style={s.logBox}>
                {tr.logs.map((line, li) => (
                  <div key={li} style={{
                    color: line.startsWith("🔧") || line.includes("Executing tool:") ? "#818cf8"
                         : line.startsWith("⛔") || line.includes("[ERROR]") ? "#f87171"
                         : line.startsWith("✅") ? "#4ade80"
                         : line.startsWith("⚠") || line.includes("[WARNING]") ? "#f59e0b"
                         : line.includes("Tool result [") ? "#22d3ee"
                         : "#94a3b8",
                    marginBottom: 1,
                  }}>
                    {line}
                  </div>
                ))}
              </div>
            </>
          )}

          {!tr.output && (!tr.logs || tr.logs.length === 0) && (
            <div style={{ fontSize: 12, color: "#475569", marginTop: 8 }}>No output or logs recorded.</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [modal, setModal]     = useState(null); // { item, type: "schedule"|"task" }
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetchDashboardSummary();
      setData(d);
    } catch (e) {
      setError("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={s.loading}>Loading dashboard...</div>;
  if (error)   return <div style={s.loading}>{error}</div>;
  if (!data)   return null;

  const scheduleRunCols = [
    { key: "id",            label: "#",           render: r => `#${r.id}` },
    { key: "schedule_name", label: "Schedule",    bold: true },
    { key: "status",        label: "Status",      render: r => <span style={s.statusBadge(r.status)}>{r.status}</span> },
    { key: "triggered_by",  label: "Trigger",     render: r => <span style={s.triggerBadge(r.triggered_by)}>{r.triggered_by}</span> },
    { key: "started_at",    label: "Started",     render: r => fmt(r.started_at) },
    { key: "duration_s",    label: "Duration",    render: r => dur(r.duration_s) },
    { key: "task_count",    label: "Tasks" },
    { key: "_logs",         label: "",            render: r => (
      <button style={s.viewBtn} onClick={() => setModal({ item: r, type: "schedule" })}>
        View Logs
      </button>
    )},
  ];

  const taskRunCols = [
    { key: "task_name",     label: "Task",        bold: true },
    { key: "agent_name",    label: "Agent",       render: r => r.agent_name || "—" },
    { key: "schedule_name", label: "Schedule",    render: r => r.schedule_name || "—" },
    { key: "status",        label: "Status",      render: r => <span style={s.statusBadge(r.status)}>{r.status}</span> },
    { key: "started_at",    label: "Started",     render: r => fmt(r.started_at) },
    { key: "duration_s",    label: "Duration",    render: r => dur(r.duration_s) },
    { key: "_logs",         label: "",            render: r => (
      <button style={s.viewBtn} onClick={() => setModal({ item: r, type: "task" })}>
        View Logs
      </button>
    )},
  ];

  return (
    <div style={s.page}>
      {/* Log modal */}
      {modal && (
        <LogModal item={modal.item} type={modal.type} onClose={() => setModal(null)} />
      )}

      {/* Header */}
      <div style={s.header}>
        <div>
          <div style={s.title}>📊 Dashboard</div>
          <div style={s.sub}>System overview — {new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</div>
        </div>
        <button style={s.refreshBtn} onClick={load}>↻ Refresh</button>
      </div>

      {/* ── Row 1: Entity KPIs ── */}
      <div style={s.section}>
        <div style={s.secTitle}>System Overview</div>
        <div style={s.kpiGrid}>
          <KpiCard value={data.agents}    label="Agents"    color="#818cf8" accent="#2d2f4a" onClick={() => navigate("/agents")} />
          <KpiCard value={data.tasks}     label="Tasks"     color="#22d3ee" accent="#0e2a30" onClick={() => navigate("/task-create")} />
          <KpiCard value={data.schedules} label="Schedules" color="#4ade80" accent="#0f2a1a"
            sub={`${data.active_schedules} active · ${data.inactive_schedules} inactive`}
            onClick={() => navigate("/scheduler")} />
          <KpiCard value={data.workflows} label="Workflows with Nodes" color="#f59e0b" accent="#2a1f0e" />
        </div>
      </div>

      {/* ── Row 2: Run KPIs ── */}
      <div style={s.section}>
        <div style={s.secTitle}>Execution Metrics</div>
        <div style={s.kpiGrid}>
          <KpiCard value={data.total_schedule_runs} label="Total Runs"     color="#f1f5f9" />
          <KpiCard value={data.successful_runs}     label="Successful"     color="#4ade80" accent="#0f2a1a" />
          <KpiCard value={data.failed_runs}         label="Failed"         color="#f87171" accent="#2a0a0a" />
          <KpiCard
            value={data.success_rate != null ? `${data.success_rate}%` : "—"}
            label="Success Rate"
            color={data.success_rate >= 80 ? "#4ade80" : data.success_rate >= 50 ? "#f59e0b" : "#f87171"}
          />
        </div>
        <div style={s.kpiGrid3}>
          <KpiCard value={data.runs_today}     label="Runs Today"     color="#60a5fa" />
          <KpiCard value={data.runs_this_week} label="Runs This Week" color="#a78bfa" />
          <KpiCard
            value={data.avg_duration_s != null ? `${data.avg_duration_s}s` : "—"}
            label="Avg Task Duration"
            color="#94a3b8"
            sub="successful tasks only"
          />
        </div>
      </div>

      {/* ── Row 3: Charts ── */}
      <div style={{ ...s.section, ...s.twoCol }}>
        {/* Run trend */}
        <div style={s.trendWrap}>
          <div style={s.secTitle}>Runs — Last 7 Days</div>
          <TrendChart data={data.run_trend} />
        </div>

        {/* Status breakdown */}
        <div style={s.trendWrap}>
          <div style={s.secTitle}>Run Status Breakdown</div>
          <StatusBar breakdown={data.status_breakdown} total={data.total_schedule_runs} />
          <div style={{ marginTop: 20 }}>
            <div style={s.secTitle}>Quick Insights</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {[
                { label: "Failures (24h)",       value: data.recent_failures_24h, color: data.recent_failures_24h > 0 ? "#f87171" : "#4ade80" },
                { label: "Tasks in Schedules",   value: data.tasks_in_schedules,  color: "#94a3b8" },
                { label: "Active Schedules",     value: data.active_schedules,    color: "#4ade80" },
                { label: "Domains",              value: data.domains,             color: "#94a3b8" },
              ].map(item => (
                <div key={item.label} style={{ background: "#13151f", borderRadius: 8, padding: "10px 14px", border: "1px solid #2d3148" }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: item.color }}>{item.value ?? "—"}</div>
                  <div style={{ fontSize: 10, color: "#475569", textTransform: "uppercase", letterSpacing: 0.8, marginTop: 2 }}>{item.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Row 4: Recent Schedule Runs ── */}
      <div style={s.section}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={s.secTitle}>Recent Schedule Runs</div>
          <button style={{ ...s.refreshBtn, fontSize: 11 }} onClick={() => navigate("/run-history")}>View All →</button>
        </div>
        <div style={s.tableWrap}>
          <RunTable runs={data.recent_schedule_runs} columns={scheduleRunCols} emptyMsg="No schedule runs yet" />
        </div>
      </div>

      {/* ── Row 5: Recent Task Runs ── */}
      <div style={s.section}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={s.secTitle}>Recent Task Executions</div>
        </div>
        <div style={s.tableWrap}>
          <RunTable runs={data.recent_task_runs} columns={taskRunCols} emptyMsg="No task executions yet" />
        </div>
      </div>
    </div>
  );
}
