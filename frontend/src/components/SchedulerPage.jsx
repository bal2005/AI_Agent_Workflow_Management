import React, { useState, useEffect, useCallback } from "react";
import {
  fetchSchedules, createSchedule, updateSchedule, deleteSchedule,
  runScheduleNow, fetchScheduleRuns, fetchTasks,
} from "../api";

// ── Styles ────────────────────────────────────────────────────────────────────
const s = {
  layout:       { display: "flex", flex: 1, overflow: "hidden", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif" },
  // left panel
  left:         { width: 260, minWidth: 260, background: "#13151f", borderRight: "1px solid #1e2130", display: "flex", flexDirection: "column" },
  leftHead:     { padding: "18px 16px 12px", borderBottom: "1px solid #1e2130", display: "flex", alignItems: "center", justifyContent: "space-between" },
  leftTitle:    { fontSize: 13, fontWeight: 700, color: "#f1f5f9" },
  addBtn:       { width: 28, height: 28, borderRadius: 7, background: "#4f46e5", border: "none", color: "#fff", fontSize: 18, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", lineHeight: 1 },
  schedList:    { flex: 1, overflowY: "auto", padding: "6px 0" },
  schedItem:    (active) => ({
    padding: "10px 16px", cursor: "pointer", borderLeft: `3px solid ${active ? "#6366f1" : "transparent"}`,
    background: active ? "#1e2130" : "transparent", transition: "all .1s",
  }),
  schedName:    { fontSize: 13, fontWeight: 600, color: "#e2e8f0", marginBottom: 2 },
  schedMeta:    { fontSize: 11, color: "#475569" },
  triggerBadge: (t) => ({
    display: "inline-block", padding: "1px 7px", borderRadius: 10, fontSize: 10, fontWeight: 700,
    background: t === "cron" ? "#1e3a5f" : t === "interval" ? "#1a2e1a" : "#2d2d2d",
    color: t === "cron" ? "#60a5fa" : t === "interval" ? "#4ade80" : "#94a3b8",
  }),
  // right
  right:        { flex: 1, overflowY: "auto", padding: "28px 36px" },
  pageTitle:    { fontSize: 22, fontWeight: 700, color: "#f8fafc", marginBottom: 4 },
  pageSub:      { fontSize: 13, color: "#64748b", marginBottom: 24 },
  section:      { background: "#1e2130", borderRadius: 12, padding: "20px 24px", marginBottom: 16, border: "1px solid #2d3148" },
  secTitle:     { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 14 },
  label:        { fontSize: 13, color: "#94a3b8", marginBottom: 5, display: "block" },
  input:        { width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 13, outline: "none", boxSizing: "border-box" },
  textarea:     { width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 13, outline: "none", resize: "vertical", minHeight: 70, boxSizing: "border-box", fontFamily: "inherit" },
  select:       { width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 13, outline: "none" },
  row2:         { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 },
  fieldGroup:   { marginBottom: 12 },
  hint:         { fontSize: 11, color: "#475569", marginTop: 4 },
  error:        { color: "#f87171", fontSize: 12, marginTop: 4 },
  success:      { color: "#4ade80", fontSize: 12, marginTop: 4 },
  // radio trigger
  radioRow:     { display: "flex", gap: 10, flexWrap: "wrap" },
  radioChip:    (active) => ({
    padding: "7px 16px", borderRadius: 8, border: `1px solid ${active ? "#6366f1" : "#2d3148"}`,
    background: active ? "#1e1f3a" : "#0f1117", color: active ? "#818cf8" : "#64748b",
    cursor: "pointer", fontSize: 13, fontWeight: 600, transition: "all .15s",
  }),
  // task list
  taskChip:     (sel) => ({
    display: "flex", alignItems: "center", gap: 8, padding: "7px 12px", borderRadius: 8,
    border: `1px solid ${sel ? "#6366f1" : "#2d3148"}`, background: sel ? "#1e1f3a" : "#0f1117",
    cursor: "pointer", fontSize: 12, color: sel ? "#818cf8" : "#64748b", marginBottom: 6,
  }),
  // buttons
  btnRow:       { display: "flex", gap: 10, marginTop: 6, flexWrap: "wrap" },
  btn:          { padding: "8px 18px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600 },
  btnPrimary:   { background: "#6366f1", color: "#fff" },
  btnSuccess:   { background: "#166534", color: "#4ade80", border: "1px solid #166534" },
  btnSecondary: { background: "#2d3148", color: "#cbd5e1" },
  btnDanger:    { background: "#7f1d1d", color: "#fca5a5" },
  btnRun:       { background: "#0f2a1a", border: "1px solid #166534", color: "#4ade80", padding: "8px 18px", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 700 },
  // run history table
  table:        { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th:           { textAlign: "left", padding: "8px 10px", color: "#475569", fontWeight: 600, borderBottom: "1px solid #2d3148", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.8 },
  td:           { padding: "9px 10px", borderBottom: "1px solid #1e2130", color: "#94a3b8", verticalAlign: "top" },
  statusBadge:  (st) => ({
    display: "inline-block", padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700,
    background: st === "success" ? "#14532d" : st === "failed" ? "#450a0a" : st === "running" ? "#1e3a5f" : "#1e2130",
    color: st === "success" ? "#4ade80" : st === "failed" ? "#f87171" : st === "running" ? "#60a5fa" : "#64748b",
  }),
  // summary cards
  cards:        { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 16 },
  card:         { background: "#1e2130", borderRadius: 10, padding: "16px 18px", border: "1px solid #2d3148" },
  cardVal:      { fontSize: 26, fontWeight: 700, color: "#f1f5f9", marginBottom: 2 },
  cardLabel:    { fontSize: 11, color: "#475569", textTransform: "uppercase", letterSpacing: 0.8 },
  // expanded run detail
  logBox:       { background: "#0a0c14", borderRadius: 6, padding: "10px 12px", fontFamily: "monospace", fontSize: 11, color: "#94a3b8", whiteSpace: "pre-wrap", maxHeight: 160, overflowY: "auto", marginTop: 6 },
};

const TRIGGER_TYPES = [
  { id: "manual",   label: "Manual",   desc: "Run on demand only" },
  { id: "interval", label: "Interval", desc: "Every X minutes/hours/days" },
  { id: "cron",     label: "Cron",     desc: "Cron expression" },
];

const INTERVAL_UNITS = ["minutes", "hours", "days"];

const emptyForm = {
  name: "", description: "", trigger_type: "manual",
  interval_value: "", interval_unit: "minutes", cron_expression: "",
  is_active: true, task_ids: [],
};

export default function SchedulerPage() {
  const [schedules, setSchedules]     = useState([]);
  const [allTasks, setAllTasks]       = useState([]);
  const [selected, setSelected]       = useState(null);   // selected schedule
  const [form, setForm]               = useState(emptyForm);
  const [isNew, setIsNew]             = useState(false);
  const [runs, setRuns]               = useState([]);
  const [expandedRun, setExpandedRun] = useState(null);
  const [saving, setSaving]           = useState(false);
  const [running, setRunning]         = useState(false);
  const [msg, setMsg]                 = useState({ type: "", text: "" });

  const load = useCallback(async () => {
    const [sc, tk] = await Promise.all([
      fetchSchedules().catch(() => []),
      fetchTasks().catch(() => []),
    ]);
    setSchedules(sc);
    setAllTasks(tk);
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadRuns = async (scheduleId) => {
    const r = await fetchScheduleRuns(scheduleId).catch(() => []);
    setRuns(r);
  };

  const selectSchedule = (sc) => {
    setSelected(sc);
    setIsNew(false);
    setForm({
      name: sc.name,
      description: sc.description || "",
      trigger_type: sc.trigger_type,
      interval_value: sc.interval_value ?? "",
      interval_unit: sc.interval_unit || "minutes",
      cron_expression: sc.cron_expression || "",
      is_active: sc.is_active,
      task_ids: sc.schedule_tasks.map(st => ({ task_id: st.task_id, position: st.position })),
    });
    setMsg({ type: "", text: "" });
    setExpandedRun(null);
    loadRuns(sc.id);
  };

  const startNew = () => {
    setSelected(null);
    setIsNew(true);
    setForm(emptyForm);
    setRuns([]);
    setMsg({ type: "", text: "" });
  };

  const f = (key) => (e) => setForm(prev => ({ ...prev, [key]: e.target.value }));

  const toggleTask = (taskId) => {
    setForm(prev => {
      const exists = prev.task_ids.find(t => t.task_id === taskId);
      if (exists) return { ...prev, task_ids: prev.task_ids.filter(t => t.task_id !== taskId) };
      return { ...prev, task_ids: [...prev.task_ids, { task_id: taskId, position: prev.task_ids.length }] };
    });
  };

  const buildPayload = () => ({
    name: form.name.trim(),
    description: form.description || null,
    trigger_type: form.trigger_type,
    interval_value: form.interval_value !== "" ? parseInt(form.interval_value) : null,
    interval_unit: form.trigger_type === "interval" ? form.interval_unit : null,
    cron_expression: form.trigger_type === "cron" ? form.cron_expression.trim() || null : null,
    is_active: form.is_active,
    task_ids: form.task_ids,
  });

  const handleSave = async () => {
    if (!form.name.trim()) { setMsg({ type: "error", text: "Schedule name is required" }); return; }
    setSaving(true); setMsg({ type: "", text: "" });
    try {
      const payload = buildPayload();
      if (isNew) {
        const created = await createSchedule(payload);
        await load();
        selectSchedule(created);
        setMsg({ type: "success", text: "Schedule created" });
      } else {
        const updated = await updateSchedule(selected.id, payload);
        await load();
        selectSchedule(updated);
        setMsg({ type: "success", text: "Schedule updated" });
      }
    } catch (e) {
      setMsg({ type: "error", text: e.response?.data?.detail || "Save failed" });
    } finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!selected || !confirm(`Delete schedule "${selected.name}"?`)) return;
    await deleteSchedule(selected.id);
    setSelected(null); setIsNew(false); setForm(emptyForm); setRuns([]);
    await load();
  };

  const handleRunNow = async () => {
    if (!selected) return;
    setRunning(true); setMsg({ type: "", text: "" });
    try {
      await runScheduleNow(selected.id);
      setMsg({ type: "success", text: "Run triggered — refreshing history..." });
      setTimeout(() => loadRuns(selected.id), 1500);
    } catch (e) {
      setMsg({ type: "error", text: e.response?.data?.detail || "Run failed" });
    } finally { setRunning(false); }
  };

  // Summary stats from runs
  const totalRuns   = runs.length;
  const successRuns = runs.filter(r => r.status === "success").length;
  const failedRuns  = runs.filter(r => r.status === "failed").length;
  const lastRun     = runs[0];

  const showForm = isNew || selected;

  return (
    <div style={s.layout}>
      {/* ── Left Panel ── */}
      <aside style={s.left}>
        <div style={s.leftHead}>
          <span style={s.leftTitle}>Task Scheduler</span>
          <button style={s.addBtn} onClick={startNew} title="New schedule">＋</button>
        </div>
        <div style={s.schedList}>
          {schedules.length === 0 && (
            <div style={{ padding: "14px 16px", fontSize: 12, color: "#475569" }}>No schedules yet</div>
          )}
          {schedules.map(sc => (
            <div
              key={sc.id}
              style={s.schedItem(selected?.id === sc.id || (isNew && !selected))}
              onClick={() => selectSchedule(sc)}
              onMouseEnter={e => { if (selected?.id !== sc.id) e.currentTarget.style.background = "#1a1d2e"; }}
              onMouseLeave={e => { if (selected?.id !== sc.id) e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                <span style={s.schedName}>{sc.name}</span>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: sc.is_active ? "#4ade80" : "#475569", flexShrink: 0 }} />
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span style={s.triggerBadge(sc.trigger_type)}>{sc.trigger_type}</span>
                <span style={s.schedMeta}>{sc.schedule_tasks?.length || 0} task{sc.schedule_tasks?.length !== 1 ? "s" : ""}</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* ── Right Content ── */}
      <div style={s.right}>
        {!showForm ? (
          <div style={{ color: "#475569", fontSize: 14, marginTop: 60, textAlign: "center" }}>
            Select a schedule or click ＋ to create one
          </div>
        ) : (
          <>
            <div style={s.pageTitle}>{isNew ? "New Schedule" : selected?.name}</div>
            <div style={s.pageSub}>
              {isNew ? "Configure trigger, assign tasks, then save." : `Last run: ${lastRun ? new Date(lastRun.created_at).toLocaleString() : "never"}`}
            </div>

            {/* ── 1. Schedule Config ── */}
            <div style={s.section}>
              <div style={s.secTitle}>Schedule Configuration</div>
              <div style={s.row2}>
                <div>
                  <label style={s.label}>Schedule Name *</label>
                  <input style={s.input} placeholder="e.g. Daily Report" value={form.name} onChange={f("name")} />
                </div>
                <div style={{ display: "flex", alignItems: "flex-end", gap: 10 }}>
                  <div style={{ flex: 1 }}>
                    <label style={s.label}>Status</label>
                    <div style={{ display: "flex", gap: 8 }}>
                      {[true, false].map(v => (
                        <div key={String(v)} style={s.radioChip(form.is_active === v)} onClick={() => setForm(p => ({ ...p, is_active: v }))}>
                          {v ? "Active" : "Inactive"}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
              <div style={s.fieldGroup}>
                <label style={s.label}>Description (optional)</label>
                <textarea style={s.textarea} placeholder="What does this schedule do?" value={form.description} onChange={f("description")} />
              </div>
            </div>

            {/* ── 2. Trigger Config ── */}
            <TriggerSection form={form} setForm={setForm} f={f} />

            {/* ── 3. Task Assignment ── */}
            <TaskAssignSection allTasks={allTasks} form={form} toggleTask={toggleTask} setForm={setForm} />

            {/* Messages */}
            {msg.text && (
              <div style={{ ...(msg.type === "error" ? s.error : s.success), marginBottom: 12 }}>
                {msg.type === "error" ? "⚠ " : "✓ "}{msg.text}
              </div>
            )}

            {/* ── Action Buttons ── */}
            <div style={s.btnRow}>
              {selected && (
                <button style={s.btnRun} onClick={handleRunNow} disabled={running}>
                  {running ? "⏳ Running..." : "▶ Run Now"}
                </button>
              )}
              <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : isNew ? "Create Schedule" : "Update Schedule"}
              </button>
              <button style={{ ...s.btn, ...s.btnSecondary }} onClick={startNew}>Reset</button>
              {selected && (
                <button style={{ ...s.btn, ...s.btnDanger }} onClick={handleDelete}>Delete</button>
              )}
            </div>

            {/* ── 4. Run History ── */}
            {selected && (
              <RunHistory
                runs={runs}
                expandedRun={expandedRun}
                setExpandedRun={setExpandedRun}
                onRefresh={() => loadRuns(selected.id)}
              />
            )}

            {/* ── 5. Summary Cards ── */}
            {selected && (
              <div style={s.cards}>
                <SummaryCard value={totalRuns} label="Total Runs" />
                <SummaryCard value={successRuns} label="Successful" color="#4ade80" />
                <SummaryCard value={failedRuns} label="Failed" color="#f87171" />
                <SummaryCard
                  value={lastRun ? new Date(lastRun.created_at).toLocaleDateString() : "—"}
                  label="Last Run"
                  small
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TriggerSection({ form, setForm, f }) {
  return (
    <div style={s.section}>
      <div style={s.secTitle}>Trigger Configuration</div>

      {/* Trigger type selector */}
      <div style={{ ...s.fieldGroup }}>
        <label style={s.label}>Trigger Type</label>
        <div style={s.radioRow}>
          {TRIGGER_TYPES.map(t => (
            <div
              key={t.id}
              style={s.radioChip(form.trigger_type === t.id)}
              onClick={() => setForm(p => ({ ...p, trigger_type: t.id }))}
              title={t.desc}
            >
              {t.label}
            </div>
          ))}
        </div>
      </div>

      {/* Interval fields */}
      {form.trigger_type === "interval" && (
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <label style={s.label}>Every</label>
            <input
              style={s.input}
              type="number"
              min="1"
              placeholder="e.g. 30"
              value={form.interval_value}
              onChange={f("interval_value")}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={s.label}>Unit</label>
            <select style={s.select} value={form.interval_unit} onChange={f("interval_unit")}>
              {INTERVAL_UNITS.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div style={{ flex: 2, paddingBottom: 2 }}>
            <div style={{ fontSize: 12, color: "#475569" }}>
              Runs every {form.interval_value || "?"} {form.interval_unit}
            </div>
          </div>
        </div>
      )}

      {/* Cron fields */}
      {form.trigger_type === "cron" && (
        <div style={s.fieldGroup}>
          <label style={s.label}>Cron Expression</label>
          <input
            style={s.input}
            placeholder="*/5 * * * *"
            value={form.cron_expression}
            onChange={f("cron_expression")}
          />
          <div style={s.hint}>
            Format: minute hour day month weekday &nbsp;|&nbsp;
            Examples: <code style={{ color: "#818cf8" }}>*/5 * * * *</code> = every 5 min &nbsp;
            <code style={{ color: "#818cf8" }}>0 9 * * 1-5</code> = weekdays at 9am
          </div>
        </div>
      )}

      {form.trigger_type === "manual" && (
        <div style={{ fontSize: 12, color: "#475569" }}>
          This schedule runs only when triggered manually via Run Now.
        </div>
      )}
    </div>
  );
}

function TaskAssignSection({ allTasks, form, toggleTask, setForm }) {
  const selectedIds = new Set(form.task_ids.map(t => t.task_id));

  // Reorder: move task up/down in the list
  const move = (taskId, dir) => {
    setForm(prev => {
      const list = [...prev.task_ids].sort((a, b) => a.position - b.position);
      const idx = list.findIndex(t => t.task_id === taskId);
      const newIdx = idx + dir;
      if (newIdx < 0 || newIdx >= list.length) return prev;
      [list[idx], list[newIdx]] = [list[newIdx], list[idx]];
      return { ...prev, task_ids: list.map((t, i) => ({ ...t, position: i })) };
    });
  };

  const orderedSelected = [...form.task_ids]
    .sort((a, b) => a.position - b.position)
    .map(t => allTasks.find(at => at.id === t.task_id))
    .filter(Boolean);

  return (
    <div style={s.section}>
      <div style={s.secTitle}>Task Assignment</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Available tasks */}
        <div>
          <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8 }}>Available Tasks (click to add)</div>
          <div style={{ maxHeight: 220, overflowY: "auto" }}>
            {allTasks.length === 0 && (
              <div style={{ fontSize: 12, color: "#475569" }}>No tasks created yet</div>
            )}
            {allTasks.map(task => (
              <div key={task.id} style={s.taskChip(selectedIds.has(task.id))} onClick={() => toggleTask(task.id)}>
                <span style={{ fontSize: 14 }}>{selectedIds.has(task.id) ? "✓" : "○"}</span>
                <div>
                  <div style={{ fontWeight: 600 }}>{task.name}</div>
                  {task.agent && (
                    <div style={{ fontSize: 10, color: "#475569" }}>
                      {task.agent.domain?.name} › {task.agent.name}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Execution order */}
        <div>
          <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8 }}>Execution Order</div>
          {orderedSelected.length === 0 ? (
            <div style={{ fontSize: 12, color: "#475569" }}>No tasks selected</div>
          ) : (
            <div style={{ maxHeight: 220, overflowY: "auto" }}>
              {orderedSelected.map((task, idx) => (
                <div key={task.id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 11, color: "#475569", minWidth: 18 }}>{idx + 1}.</span>
                  <div style={{ flex: 1, fontSize: 12, color: "#e2e8f0", fontWeight: 600 }}>{task.name}</div>
                  <button
                    style={{ background: "none", border: "none", color: "#475569", cursor: "pointer", fontSize: 12, padding: "2px 4px" }}
                    onClick={() => move(task.id, -1)} disabled={idx === 0}
                  >▲</button>
                  <button
                    style={{ background: "none", border: "none", color: "#475569", cursor: "pointer", fontSize: 12, padding: "2px 4px" }}
                    onClick={() => move(task.id, 1)} disabled={idx === orderedSelected.length - 1}
                  >▼</button>
                  <button
                    style={{ background: "none", border: "none", color: "#7f1d1d", cursor: "pointer", fontSize: 12, padding: "2px 4px" }}
                    onClick={() => toggleTask(task.id)}
                  >✕</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RunHistory({ runs, expandedRun, setExpandedRun, onRefresh }) {
  return (
    <div style={{ ...s.section, marginTop: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={s.secTitle}>Run History</div>
        <button
          style={{ background: "none", border: "1px solid #2d3148", borderRadius: 6, color: "#64748b", padding: "4px 10px", cursor: "pointer", fontSize: 11 }}
          onClick={onRefresh}
        >↻ Refresh</button>
      </div>

      {runs.length === 0 ? (
        <div style={{ fontSize: 12, color: "#475569" }}>No runs yet. Use Run Now to trigger the first execution.</div>
      ) : (
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>Run #</th>
              <th style={s.th}>Status</th>
              <th style={s.th}>Triggered By</th>
              <th style={s.th}>Started</th>
              <th style={s.th}>Duration</th>
              <th style={s.th}>Tasks</th>
              <th style={s.th}></th>
            </tr>
          </thead>
          <tbody>
            {runs.map(run => {
              const dur = run.started_at && run.finished_at
                ? ((new Date(run.finished_at) - new Date(run.started_at)) / 1000).toFixed(1) + "s"
                : run.status === "running" ? "running…" : "—";
              const isExpanded = expandedRun === run.id;
              return (
                <React.Fragment key={run.id}>
                  <tr>
                    <td style={s.td}>#{run.id}</td>
                    <td style={s.td}><span style={s.statusBadge(run.status)}>{run.status}</span></td>
                    <td style={s.td}>{run.triggered_by}</td>
                    <td style={s.td}>{run.started_at ? new Date(run.started_at).toLocaleString() : "—"}</td>
                    <td style={s.td}>{dur}</td>
                    <td style={s.td}>{run.task_runs?.length || 0}</td>
                    <td style={s.td}>
                      <button
                        style={{ background: "none", border: "none", color: "#6366f1", cursor: "pointer", fontSize: 11 }}
                        onClick={() => setExpandedRun(isExpanded ? null : run.id)}
                      >
                        {isExpanded ? "▲ hide" : "▼ detail"}
                      </button>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={7} style={{ ...s.td, background: "#0f1117", padding: "12px 16px" }}>
                        <RunDetail run={run} />
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
  );
}

function RunDetail({ run }) {
  if (!run.task_runs || run.task_runs.length === 0) {
    return <div style={{ fontSize: 12, color: "#475569" }}>No task runs recorded.</div>;
  }
  return (
    <div>
      {run.error && (
        <div style={{ color: "#f87171", fontSize: 12, marginBottom: 8 }}>Error: {run.error}</div>
      )}
      {run.task_runs.map((tr, i) => (
        <div key={tr.id} style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: "#475569" }}>{i + 1}.</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#e2e8f0" }}>{tr.task?.name || `Task #${tr.task_id}`}</span>
            <span style={s.statusBadge(tr.status)}>{tr.status}</span>
            {tr.duration_seconds != null && (
              <span style={{ fontSize: 11, color: "#475569" }}>{tr.duration_seconds}s</span>
            )}
          </div>
          {tr.output && (
            <div style={s.logBox}>{tr.output}</div>
          )}
          {tr.logs && tr.logs.length > 0 && (
            <div style={{ ...s.logBox, color: "#818cf8", marginTop: 4 }}>
              {tr.logs.join("\n")}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function SummaryCard({ value, label, color = "#f1f5f9", small = false }) {
  return (
    <div style={s.card}>
      <div style={{ ...s.cardVal, color, fontSize: small ? 16 : 26 }}>{value}</div>
      <div style={s.cardLabel}>{label}</div>
    </div>
  );
}
