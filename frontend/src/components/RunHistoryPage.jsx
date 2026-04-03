import React, { useState, useEffect, useCallback } from "react";
import { fetchAllRuns, fetchSchedules, fetchDashboardSummary } from "../api";

const s = {
  page:         { display: "flex", flexDirection: "column", flex: 1, overflow: "hidden", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif" },
  header:       { padding: "24px 36px 16px", borderBottom: "1px solid #1e2130", flexShrink: 0 },
  titleRow:     { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 },
  pageTitle:    { fontSize: 22, fontWeight: 700, color: "#f8fafc" },
  filters:      { display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" },
  select:       { padding: "7px 12px", borderRadius: 8, border: "1px solid #2d3148", background: "#13151f", color: "#e2e8f0", fontSize: 12, outline: "none" },
  input:        { padding: "7px 12px", borderRadius: 8, border: "1px solid #2d3148", background: "#13151f", color: "#e2e8f0", fontSize: 12, outline: "none", width: 160 },
  refreshBtn:   { padding: "7px 16px", borderRadius: 8, border: "1px solid #2d3148", background: "none", color: "#94a3b8", fontSize: 12, fontWeight: 600, cursor: "pointer" },
  body:         { flex: 1, overflowY: "auto", padding: "20px 36px" },
  table:        { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th:           { textAlign: "left", padding: "9px 12px", color: "#475569", fontWeight: 600, borderBottom: "1px solid #2d3148", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.8, background: "#13151f" },
  td:           { padding: "10px 12px", borderBottom: "1px solid #1e2130", color: "#94a3b8", verticalAlign: "middle" },
  statusBadge:  (st) => ({
    display: "inline-block", padding: "2px 9px", borderRadius: 10, fontSize: 11, fontWeight: 700,
    background: st === "success" ? "#14532d" : st === "failed" ? "#450a0a" : st === "running" ? "#1e3a5f" : "#1e2130",
    color:      st === "success" ? "#4ade80" : st === "failed" ? "#f87171" : st === "running" ? "#60a5fa" : "#64748b",
  }),
  triggerBadge: (t) => ({
    display: "inline-block", padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700,
    background: t === "scheduler" ? "#1a2e1a" : t === "manual" ? "#2d1f3a" : t === "filesystem" ? "#1a2a1a" : t === "email_imap" ? "#1f1a2e" : "#2d2d2d",
    color:      t === "scheduler" ? "#4ade80" : t === "manual" ? "#c084fc" : t === "filesystem" ? "#86efac" : t === "email_imap" ? "#a78bfa" : "#94a3b8",
  }),
  detailBtn:    { background: "none", border: "1px solid #2d3148", borderRadius: 6, color: "#6366f1", cursor: "pointer", fontSize: 11, padding: "4px 10px", fontWeight: 600 },
  emptyMsg:     { color: "#475569", fontSize: 13, padding: "40px 0", textAlign: "center" },
  // summary cards
  cards:        { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 },
  card:         { background: "#1e2130", borderRadius: 10, padding: "14px 18px", border: "1px solid #2d3148" },
  cardVal:      { fontSize: 24, fontWeight: 700, color: "#f1f5f9", marginBottom: 2 },
  cardLabel:    { fontSize: 11, color: "#475569", textTransform: "uppercase", letterSpacing: 0.8 },
  // modal overlay
  overlay:      { position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 },
  modal:        { background: "#13151f", border: "1px solid #2d3148", borderRadius: 14, width: "100%", maxWidth: 780, maxHeight: "88vh", display: "flex", flexDirection: "column", overflow: "hidden" },
  modalHead:    { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 24px", borderBottom: "1px solid #1e2130", flexShrink: 0 },
  modalTitle:   { fontSize: 16, fontWeight: 700, color: "#f8fafc" },
  closeBtn:     { background: "none", border: "none", color: "#64748b", fontSize: 20, cursor: "pointer", lineHeight: 1, padding: "2px 6px" },
  modalBody:    { overflowY: "auto", padding: "20px 24px", flex: 1 },
  secTitle:     { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 12 },
  metaGrid:     { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 20 },
  metaItem:     { background: "#1e2130", borderRadius: 8, padding: "10px 14px", border: "1px solid #2d3148" },
  metaLabel:    { fontSize: 10, color: "#475569", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 4 },
  metaValue:    { fontSize: 13, color: "#e2e8f0", fontWeight: 600 },
  taskRow:      { background: "#1e2130", borderRadius: 8, padding: "12px 16px", marginBottom: 10, border: "1px solid #2d3148" },
  logBox:       { background: "#0a0c14", borderRadius: 6, padding: "10px 12px", fontFamily: "monospace", fontSize: 11, color: "#94a3b8", whiteSpace: "pre-wrap", maxHeight: 200, overflowY: "auto", marginTop: 6 },
  divider:      { borderTop: "1px solid #1e2130", margin: "16px 0" },
};

const fmt = (dt) => dt ? new Date(dt).toLocaleString() : "—";
const dur = (s, e) => {
  if (s && e) return ((new Date(e) - new Date(s)) / 1000).toFixed(1) + "s";
  return "—";
};

export default function RunHistoryPage() {
  const [runs, setRuns]           = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [stats, setStats]         = useState(null);   // real DB-wide totals
  const [loading, setLoading]     = useState(true);
  const [modalRun, setModalRun]   = useState(null);
  // filters
  const [filterStatus, setFilterStatus]     = useState("");
  const [filterTrigger, setFilterTrigger]   = useState("");
  const [filterSchedule, setFilterSchedule] = useState("");
  const [filterSearch, setFilterSearch]     = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const [r, sc, dash] = await Promise.all([
      fetchAllRuns({ limit: 200 }).catch(() => []),
      fetchSchedules().catch(() => []),
      fetchDashboardSummary().catch(() => null),
    ]);
    setRuns(r);
    setSchedules(sc);
    setStats(dash);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = runs.filter(r => {
    if (filterStatus && r.status !== filterStatus) return false;
    if (filterTrigger && r.triggered_by !== filterTrigger) return false;
    if (filterSchedule && String(r.schedule_id) !== filterSchedule) return false;
    if (filterSearch) {
      const q = filterSearch.toLowerCase();
      const name = (r.schedule_name || "").toLowerCase();
      if (!name.includes(q) && !String(r.id).includes(q)) return false;
    }
    return true;
  });

  // ── Summary stats: use real DB-wide totals from dashboard, not the 200-run slice ──
  const totalRuns   = stats?.total_schedule_runs ?? runs.length;
  const successRuns = stats?.successful_runs     ?? runs.filter(r => r.status === "success").length;
  const failedRuns  = stats?.failed_runs         ?? runs.filter(r => r.status === "failed").length;
  const runningRuns = runs.filter(r => r.status === "running").length;  // live count from fetched slice
  const pendingRuns = runs.filter(r => r.status === "pending").length;
  const successRate = stats?.success_rate        ?? null;
  const avgDur      = stats?.avg_duration_s      ?? null;
  const runsToday   = stats?.runs_today          ?? null;
  const runsWeek    = stats?.runs_this_week      ?? null;

  // Filtered table count (for the "showing X results" context)
  const filteredCount = filtered.length;

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <div style={s.titleRow}>
          <div style={s.pageTitle}>📋 Run History</div>
          <button style={s.refreshBtn} onClick={load}>⟳ Refresh</button>
        </div>

        {/* Filters */}
        <div style={s.filters}>
          <input
            style={s.input}
            placeholder="Search schedule / run #..."
            value={filterSearch}
            onChange={e => setFilterSearch(e.target.value)}
          />
          <select style={s.select} value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
            <option value="">All Statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
            <option value="pending">Pending</option>
          </select>
          <select style={s.select} value={filterTrigger} onChange={e => setFilterTrigger(e.target.value)}>
            <option value="">All Triggers</option>
            <option value="manual">Manual</option>
            <option value="scheduler">Scheduler</option>
            <option value="filesystem">File Watch</option>
            <option value="email_imap">Email IMAP</option>
          </select>
          <select style={s.select} value={filterSchedule} onChange={e => setFilterSchedule(e.target.value)}>
            <option value="">All Schedules</option>
            {schedules.map(sc => (
              <option key={sc.id} value={sc.id}>{sc.name}</option>
            ))}
          </select>
          {(filterStatus || filterTrigger || filterSchedule || filterSearch) && (
            <button
              style={{ ...s.refreshBtn, color: "#f87171", borderColor: "#7f1d1d" }}
              onClick={() => { setFilterStatus(""); setFilterTrigger(""); setFilterSchedule(""); setFilterSearch(""); }}
            >
              ✕ Clear
            </button>
          )}
        </div>
      </div>

      <div style={s.body}>
        {/* Summary cards — DB-wide totals, not limited to the 200-run page slice */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 }}>
          <div style={s.card}><div style={s.cardVal}>{totalRuns}</div><div style={s.cardLabel}>Total Runs (all time)</div></div>
          <div style={s.card}><div style={{ ...s.cardVal, color: "#4ade80" }}>{successRuns}</div><div style={s.cardLabel}>Successful</div></div>
          <div style={s.card}><div style={{ ...s.cardVal, color: "#f87171" }}>{failedRuns}</div><div style={s.cardLabel}>Failed</div></div>
          <div style={s.card}>
            <div style={{ ...s.cardVal, color: successRate != null ? (successRate >= 80 ? "#4ade80" : successRate >= 50 ? "#f59e0b" : "#f87171") : "#475569" }}>
              {successRate != null ? `${successRate}%` : "—"}
            </div>
            <div style={s.cardLabel}>Success Rate</div>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
          <div style={s.card}><div style={{ ...s.cardVal, color: "#60a5fa" }}>{runningRuns}</div><div style={s.cardLabel}>Currently Running</div></div>
          <div style={s.card}><div style={{ ...s.cardVal, color: "#94a3b8" }}>{pendingRuns}</div><div style={s.cardLabel}>Pending</div></div>
          <div style={s.card}><div style={{ ...s.cardVal, color: "#a78bfa" }}>{runsToday ?? "—"}</div><div style={s.cardLabel}>Runs Today</div></div>
          <div style={s.card}>
            <div style={{ ...s.cardVal, color: "#f59e0b" }}>{avgDur != null ? `${avgDur}s` : "—"}</div>
            <div style={s.cardLabel}>Avg Task Duration</div>
          </div>
        </div>
        {/* Filtered table context */}
        {(filterStatus || filterTrigger || filterSchedule || filterSearch) && (
          <div style={{ fontSize: 12, color: "#475569", marginBottom: 10 }}>
            Showing {filteredCount} filtered run{filteredCount !== 1 ? "s" : ""} (from last 200 fetched)
          </div>
        )}

        {/* Table */}
        {loading ? (
          <div style={s.emptyMsg}>Loading...</div>
        ) : filtered.length === 0 ? (
          <div style={s.emptyMsg}>No runs found{filterStatus || filterTrigger || filterSchedule ? " for selected filters" : ""}.</div>
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Run #</th>
                <th style={s.th}>Schedule</th>
                <th style={s.th}>Status</th>
                <th style={s.th}>Triggered By</th>
                <th style={s.th}>Started</th>
                <th style={s.th}>Duration</th>
                <th style={s.th}>Tasks</th>
                <th style={s.th}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(run => (
                <tr
                  key={run.id}
                  onMouseEnter={e => e.currentTarget.style.background = "#1a1d2e"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                >
                  <td style={s.td}>#{run.id}</td>
                  <td style={{ ...s.td, color: "#e2e8f0", fontWeight: 600 }}>
                    {run.schedule_name || `Schedule #${run.schedule_id}`}
                  </td>
                  <td style={s.td}><span style={s.statusBadge(run.status)}>{run.status}</span></td>
                  <td style={s.td}><span style={s.triggerBadge(run.triggered_by)}>{run.triggered_by}</span></td>
                  <td style={s.td}>{fmt(run.started_at)}</td>
                  <td style={s.td}>{dur(run.started_at, run.finished_at)}</td>
                  <td style={s.td}>{run.task_runs?.length || 0}</td>
                  <td style={s.td}>
                    <button style={s.detailBtn} onClick={() => setModalRun(run)}>
                      Detail ▶
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal */}
      {modalRun && (
        <RunTraceModal run={modalRun} onClose={() => setModalRun(null)} />
      )}
    </div>
  );
}

function RunTraceModal({ run, onClose }) {
  // Close on overlay click
  const handleOverlay = (e) => { if (e.target === e.currentTarget) onClose(); };

  return (
    <div style={s.overlay} onClick={handleOverlay}>
      <div style={s.modal}>
        {/* Modal header */}
        <div style={s.modalHead}>
          <div>
            <div style={s.modalTitle}>Run Trace Details — #{run.id}</div>
            <div style={{ fontSize: 12, color: "#475569", marginTop: 2 }}>
              {run.schedule_name || `Schedule #${run.schedule_id}`}
            </div>
          </div>
          <button style={s.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div style={s.modalBody}>
          {/* 1. Run Metadata */}
          <div style={s.secTitle}>Run Metadata</div>
          <div style={s.metaGrid}>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Run ID</div>
              <div style={s.metaValue}>#{run.id}</div>
            </div>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Status</div>
              <span style={s.statusBadge(run.status)}>{run.status}</span>
            </div>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Triggered By</div>
              <span style={s.triggerBadge(run.triggered_by)}>{run.triggered_by}</span>
            </div>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Started At</div>
              <div style={s.metaValue}>{fmt(run.started_at)}</div>
            </div>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Ended At</div>
              <div style={s.metaValue}>{fmt(run.finished_at)}</div>
            </div>
            <div style={s.metaItem}>
              <div style={s.metaLabel}>Duration</div>
              <div style={s.metaValue}>{dur(run.started_at, run.finished_at)}</div>
            </div>
          </div>

          {run.error && (
            <div style={{ background: "#450a0a", border: "1px solid #7f1d1d", borderRadius: 8, padding: "10px 14px", marginBottom: 16, fontSize: 12, color: "#f87171" }}>
              ✗ Run Error: {run.error}
            </div>
          )}

          <div style={s.divider} />

          {/* 2. Task Execution Trace */}
          <div style={s.secTitle}>Task Execution Trace ({run.task_runs?.length || 0} tasks)</div>
          {!run.task_runs?.length ? (
            <div style={{ fontSize: 12, color: "#475569", marginBottom: 16 }}>No task runs recorded.</div>
          ) : run.task_runs.map((tr, i) => (
            <div key={tr.id} style={s.taskRow}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span style={{ fontSize: 11, color: "#475569", minWidth: 20 }}>{i + 1}.</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#e2e8f0", flex: 1 }}>
                  {tr.task?.name || `Task #${tr.task_id}`}
                </span>
                <span style={s.statusBadge(tr.status)}>{tr.status}</span>
                {tr.duration_seconds != null && (
                  <span style={{ fontSize: 11, color: "#475569" }}>{tr.duration_seconds}s</span>
                )}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
                <div>
                  <div style={s.metaLabel}>Started</div>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{fmt(tr.started_at)}</div>
                </div>
                <div>
                  <div style={s.metaLabel}>Ended</div>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{fmt(tr.finished_at)}</div>
                </div>
                <div>
                  <div style={s.metaLabel}>Duration</div>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{dur(tr.started_at, tr.finished_at)}</div>
                </div>
              </div>
              {tr.output && (
                <>
                  <div style={s.metaLabel}>Output</div>
                  <div style={{ ...s.logBox, color: "#a3e635" }}>{tr.output}</div>
                </>
              )}
              {tr.logs?.length > 0 && (
                <>
                  <div style={{ ...s.metaLabel, marginTop: 8 }}>Execution Logs</div>
                  <div style={s.logBox}>
                    {tr.logs.map((line, li) => {
                      const clean = line
                        .replace(/\?\?\?/g, "✅")
                        .replace(/\?\?\?\?/g, "🔧");
                      // Detailed run.log format: "2026-04-03 11:06:08,353 [INFO] Executing tool: ..."
                      const isInfo    = clean.includes("[INFO]");
                      const isWarning = clean.includes("[WARNING]") || clean.includes("[WARN]");
                      const isError   = clean.includes("[ERROR]");
                      const isExec    = clean.includes("Executing tool:");
                      const isResult  = clean.includes("Tool result [");
                      const color =
                        clean.startsWith("🔧") || isExec  ? "#818cf8"
                        : clean.startsWith("✅")           ? "#4ade80"
                        : clean.startsWith("⛔") || isError ? "#f87171"
                        : clean.startsWith("⚠") || isWarning ? "#f59e0b"
                        : isResult                         ? "#22d3ee"
                        : isInfo                           ? "#94a3b8"
                        : "#64748b";
                      return (
                        <div key={li} style={{ color, marginBottom: 1 }}>{clean}</div>
                      );
                    })}
                  </div>
                </>
              )}
              {tr.status === "failed" && !tr.output && !tr.logs?.length && (
                <div style={{ fontSize: 11, color: "#f87171" }}>Task failed with no output recorded.</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
