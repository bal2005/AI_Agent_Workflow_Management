/**
 * SchedulerPage
 * ──────────────
 * Left panel: list of schedules
 * Right panel: schedule config form OR workflow builder (toggled)
 *
 * Workflow JSON is stored in schedule.workflow_json (frontend-only for now).
 * When saving, task_ids are derived from the workflow nodes so the backend
 * still receives the flat task list it expects.
 */
import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchSchedules, createSchedule, updateSchedule, deleteSchedule,
  runScheduleNow, fetchScheduleRuns, fetchTasks,
  fetchEmailTriggerLogs, testEmailConnection, testImapTrigger,
} from "../api";
import WorkflowBuilder from "./WorkflowBuilder";

// ── Styles ────────────────────────────────────────────────────────────────────
const s = {
  layout:       { display: "flex", flex: 1, overflow: "hidden", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif" },
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
    background: t === "cron" ? "#1e3a5f" : t === "interval" ? "#1a2e1a" : t === "filesystem" ? "#1a2a1a" : t === "email_imap" ? "#1f1a2e" : "#2d2d2d",
    color:      t === "cron" ? "#60a5fa" : t === "interval" ? "#4ade80" : t === "filesystem" ? "#86efac" : t === "email_imap" ? "#a78bfa" : "#94a3b8",
  }),
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
  radioRow:     { display: "flex", gap: 10, flexWrap: "wrap" },
  radioChip:    (active) => ({
    padding: "7px 16px", borderRadius: 8, border: `1px solid ${active ? "#6366f1" : "#2d3148"}`,
    background: active ? "#1e1f3a" : "#0f1117", color: active ? "#818cf8" : "#64748b",
    cursor: "pointer", fontSize: 13, fontWeight: 600, transition: "all .15s",
  }),
  btnRow:       { display: "flex", gap: 10, marginTop: 6, flexWrap: "wrap" },
  btn:          { padding: "8px 18px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600 },
  btnPrimary:   { background: "#6366f1", color: "#fff" },
  btnSecondary: { background: "#2d3148", color: "#cbd5e1" },
  btnDanger:    { background: "#7f1d1d", color: "#fca5a5" },
  btnRun:       { background: "#0f2a1a", border: "1px solid #166534", color: "#4ade80", padding: "8px 18px", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 700 },
  callout:      { background: "#0f1117", border: "1px solid #2d3148", borderRadius: 8, padding: "12px 14px", marginTop: 12, color: "#94a3b8", fontSize: 12, lineHeight: 1.5 },
  pillRow:      { display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 },
  pill:         (active) => ({
    display: "inline-flex",
    padding: "4px 10px",
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 600,
    border: `1px solid ${active ? "#6366f1" : "#2d3148"}`,
    background: active ? "#1e1f3a" : "#13151f",
    color: active ? "#818cf8" : "#64748b",
  }),
  // Workflow preview strip
  wfStrip:      { display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", padding: "10px 14px", background: "#0f1117", borderRadius: 8, border: "1px solid #2d3148", marginTop: 8 },
  wfNode:       (type) => ({
    padding: "3px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600,
    background: type === "trigger" ? "#1e1f3a" : type === "task" ? "#0e2a30" : "#2a1f0e",
    color: type === "trigger" ? "#818cf8" : type === "task" ? "#22d3ee" : "#f59e0b",
    border: `1px solid ${type === "trigger" ? "#4f46e5" : type === "task" ? "#0891b2" : "#d97706"}`,
  }),
  wfArrow:      { color: "#2d3148", fontSize: 14 },
  table:        { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th:           { textAlign: "left", padding: "8px 10px", color: "#475569", fontWeight: 600, borderBottom: "1px solid #2d3148", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.8 },
  td:           { padding: "9px 10px", borderBottom: "1px solid #1e2130", color: "#94a3b8", verticalAlign: "top" },
  statusBadge:  (st) => ({
    display: "inline-block", padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700,
    background: st === "success" ? "#14532d" : st === "failed" ? "#450a0a" : st === "running" ? "#1e3a5f" : "#1e2130",
    color: st === "success" ? "#4ade80" : st === "failed" ? "#f87171" : st === "running" ? "#60a5fa" : "#64748b",
  }),
  logBox:       { background: "#0a0c14", borderRadius: 6, padding: "10px 12px", fontFamily: "monospace", fontSize: 11, color: "#94a3b8", whiteSpace: "pre-wrap", maxHeight: 160, overflowY: "auto", marginTop: 6 },
};

const TRIGGER_TYPES = [
  { id: "manual",     label: "Manual",        desc: "Run on demand only" },
  { id: "interval",   label: "Interval",      desc: "Every X minutes/hours/days" },
  { id: "cron",       label: "Cron",          desc: "Cron expression" },
  { id: "filesystem", label: "📁 File Watch", desc: "Trigger on file/folder changes" },
  { id: "email_imap", label: "📧 Email IMAP", desc: "Trigger on incoming email" },
];
const INTERVAL_UNITS = ["minutes", "hours", "days"];

const emptyForm = {
  name: "", description: "", trigger_type: "manual",
  interval_value: "", interval_unit: "minutes", cron_expression: "",
  is_active: true, task_ids: [], workflow_json: null,
  // Filesystem trigger config
  fs_watch_path: "", fs_recursive: true, fs_events: ["created", "modified"],
  fs_extension_filter: "", fs_filename_pattern: "", fs_debounce_seconds: 3,
  fs_enabled: true, fs_target: "both",
  // Email IMAP trigger config
  em_host: "", em_port: 993, em_use_ssl: true,
  em_username: "", em_password: "",
  em_mailbox: "INBOX", em_poll_interval_minutes: 5,
  em_filter_sender: "", em_filter_subject: "", em_filter_body: "",
  em_unread_only: true, em_has_attachment: false,
  em_attachment_extensions: "", em_enabled: true,
};

export default function SchedulerPage({ onOpenRunHistory }) {
  const [schedules, setSchedules]       = useState([]);
  const [allTasks, setAllTasks]         = useState([]);
  const [selected, setSelected]         = useState(null);
  const [form, setForm]                 = useState(emptyForm);
  const [isNew, setIsNew]               = useState(false);
  const [saving, setSaving]             = useState(false);
  const [running, setRunning]           = useState(false);
  const [msg, setMsg]                   = useState({ type: "", text: "" });
  const [showBuilder, setShowBuilder]   = useState(false);

  // Always-current ref to form — updated synchronously, never stale
  const formRef = useRef(form);
  // Keep ref in sync on every state change — also update synchronously in setForm calls below
  const setFormAndRef = useCallback((updater) => {
    setForm(prev => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      formRef.current = next;
      return next;
    });
  }, []);

  const load = useCallback(async () => {
    const [sc, tk] = await Promise.all([
      fetchSchedules().catch(() => []),
      fetchTasks().catch(() => []),
    ]);
    setSchedules(sc);
    setAllTasks(tk);
  }, []);

  useEffect(() => { load(); }, [load]);

  const selectSchedule = (sc, workflowOverride = undefined) => {
    const wf = workflowOverride !== undefined ? workflowOverride : (sc.workflow_json ?? null);
    console.log("[WF] selectSchedule id:", sc.id, "override:", workflowOverride, "sc.workflow_json:", sc.workflow_json, "→ using:", wf);
    setSelected(sc);
    setIsNew(false);
    setShowBuilder(false);
    setFormAndRef({
      name: sc.name,
      description: sc.description || "",
      trigger_type: sc.trigger_type,
      interval_value: sc.interval_value ?? "",
      interval_unit: sc.interval_unit || "minutes",
      cron_expression: sc.cron_expression || "",
      is_active: sc.is_active,
      task_ids: sc.schedule_tasks?.map(st => ({ task_id: st.task_id, position: st.position })) || [],
      workflow_json: wf,
      // Filesystem trigger config
      fs_watch_path:        sc.trigger_config?.watch_path || "",
      fs_recursive:         sc.trigger_config?.recursive ?? true,
      fs_events:            sc.trigger_config?.events || ["created", "modified"],
      fs_extension_filter:  (sc.trigger_config?.extension_filter || []).join(", "),
      fs_filename_pattern:  sc.trigger_config?.filename_pattern || "",
      fs_debounce_seconds:  sc.trigger_config?.debounce_seconds ?? 3,
      fs_enabled:           sc.trigger_config?.enabled ?? true,
      fs_target:            sc.trigger_config?.target || "both",
      // Email IMAP trigger config
      em_host:                    sc.trigger_config?.host || "",
      em_port:                    sc.trigger_config?.port ?? 993,
      em_use_ssl:                 sc.trigger_config?.use_ssl ?? true,
      em_username:                sc.trigger_config?.username || "",
      em_password:                "",   // never pre-fill password from server
      em_mailbox:                 sc.trigger_config?.mailbox || "INBOX",
      em_poll_interval_minutes:   sc.trigger_config?.poll_interval_minutes ?? 5,
      em_filter_sender:           sc.trigger_config?.filter_sender || "",
      em_filter_subject:          sc.trigger_config?.filter_subject || "",
      em_filter_body:             sc.trigger_config?.filter_body || "",
      em_unread_only:             sc.trigger_config?.unread_only ?? true,
      em_has_attachment:          sc.trigger_config?.has_attachment ?? false,
      em_attachment_extensions:   (sc.trigger_config?.attachment_extensions || []).join(", "),
      em_enabled:                 sc.trigger_config?.enabled ?? true,
    });
    setMsg({ type: "", text: "" });
  };

  const startNew = () => {
    setSelected(null);
    setIsNew(true);
    setShowBuilder(false);
    setFormAndRef(emptyForm);
    setMsg({ type: "", text: "" });
  };

  const f = (key) => (e) => setFormAndRef(prev => ({ ...prev, [key]: e.target.value }));

  // ── Workflow builder ──────────────────────────────────────────────────────

  const handleWorkflowSave = (workflow) => {
    console.log("[WF] handleWorkflowSave called, nodes:", workflow?.nodes?.length, workflow);
    const taskNodes = workflow.nodes.filter(n => n.type === "task" && n.taskId);
    const task_ids = taskNodes.map((n, i) => ({ task_id: n.taskId, position: i }));
    const triggerNode = workflow.nodes.find(n => n.type === "trigger");
    const trigger_type = triggerNode?.triggerType || formRef.current.trigger_type;
    setFormAndRef(prev => {
      const next = { ...prev, task_ids, workflow_json: workflow, trigger_type };
      console.log("[WF] setFormAndRef after workflow save, workflow_json nodes:", next.workflow_json?.nodes?.length);
      return next;
    });
    setShowBuilder(false);
  };

  // ── Save ─────────────────────────────────────────────────────────────────

  const buildPayload = () => {
    const f = formRef.current;
    const p = {
      name: f.name.trim(),
      description: f.description || null,
      trigger_type: f.trigger_type,
      interval_value: f.interval_value !== "" ? parseInt(f.interval_value) : null,
      interval_unit: f.trigger_type === "interval" ? f.interval_unit : null,
      cron_expression: f.trigger_type === "cron" ? f.cron_expression.trim() || null : null,
      is_active: f.is_active,
      task_ids: f.task_ids,
      workflow_json: f.workflow_json || null,
      // Build trigger_config for filesystem triggers
      trigger_config: f.trigger_type === "filesystem" ? {
        watch_path:       f.fs_watch_path.trim(),
        recursive:        f.fs_recursive,
        events:           f.fs_events,
        target:           f.fs_target || "both",
        extension_filter: f.fs_extension_filter
          ? f.fs_extension_filter.split(",").map(e => e.trim()).filter(Boolean)
          : null,
        filename_pattern: f.fs_filename_pattern.trim() || null,
        debounce_seconds: Number(f.fs_debounce_seconds) || 3,
        enabled:          f.fs_enabled,
      } : f.trigger_type === "email_imap" ? {
        host:                    f.em_host.trim(),
        port:                    Number(f.em_port) || 993,
        use_ssl:                 f.em_use_ssl,
        username:                f.em_username.trim(),
        // Only send password if user typed one; empty string = keep existing encrypted value
        ...(f.em_password ? { password: f.em_password } : {}),
        mailbox:                 f.em_mailbox.trim() || "INBOX",
        poll_interval_minutes:   Number(f.em_poll_interval_minutes) || 5,
        filter_sender:           f.em_filter_sender.trim() || null,
        filter_subject:          f.em_filter_subject.trim() || null,
        filter_body:             f.em_filter_body.trim() || null,
        unread_only:             f.em_unread_only,
        has_attachment:          f.em_has_attachment,
        attachment_extensions:   f.em_attachment_extensions
          ? f.em_attachment_extensions.split(",").map(e => e.trim()).filter(Boolean)
          : [],
        enabled:                 f.em_enabled,
      } : null,
    };
    console.log("[WF] buildPayload workflow_json:", p.workflow_json);
    return p;
  };

  const handleSave = async () => {
    if (!formRef.current.name.trim()) { setMsg({ type: "error", text: "Schedule name is required" }); return; }
    setSaving(true); setMsg({ type: "", text: "" });
    try {
      const payload = buildPayload();
      const savedWorkflow = payload.workflow_json;
      console.log("[WF] handleSave payload.workflow_json:", savedWorkflow);

      if (isNew) {
        const created = await createSchedule(payload);
        console.log("[WF] created response workflow_json:", created.workflow_json);
        const [sc, tk] = await Promise.all([fetchSchedules().catch(() => []), fetchTasks().catch(() => [])]);
        setSchedules(sc); setAllTasks(tk);
        const fresh = sc.find(s => s.id === created.id) || created;
        console.log("[WF] fresh from list workflow_json:", fresh.workflow_json);
        selectSchedule(fresh, savedWorkflow);
        setMsg({ type: "success", text: "Schedule created" });
      } else {
        const updated = await updateSchedule(selected.id, payload);
        console.log("[WF] updated response workflow_json:", updated.workflow_json);
        const [sc, tk] = await Promise.all([fetchSchedules().catch(() => []), fetchTasks().catch(() => [])]);
        setSchedules(sc); setAllTasks(tk);
        const fresh = sc.find(s => s.id === updated.id) || updated;
        console.log("[WF] fresh from list workflow_json:", fresh.workflow_json);
        selectSchedule(fresh, savedWorkflow);
        setMsg({ type: "success", text: "Schedule updated" });
      }
    } catch (e) {
      setMsg({ type: "error", text: e.response?.data?.detail || "Save failed" });
    } finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!selected || !confirm(`Delete schedule "${selected.name}"?`)) return;
    await deleteSchedule(selected.id);
    setSelected(null); setIsNew(false); setFormAndRef(emptyForm);
    await load();
  };

  const handleRunNow = async () => {
    if (!selected) return;
    setRunning(true); setMsg({ type: "", text: "" });
    try {
      await runScheduleNow(selected.id);
      setMsg({ type: "success", text: "Run triggered — check Run History for results." });
    } catch (e) {
      setMsg({ type: "error", text: e.response?.data?.detail || "Run failed" });
    } finally { setRunning(false); }
  };

  // ── Workflow builder fullscreen overlay ───────────────────────────────────
  if (showBuilder) {
    return (
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <WorkflowBuilder
          initialWorkflow={form.workflow_json}
          allTasks={allTasks}
          scheduleName={form.name || "New Schedule"}
          onSave={handleWorkflowSave}
          onCancel={() => setShowBuilder(false)}
        />
      </div>
    );
  }

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
              style={s.schedItem(selected?.id === sc.id)}
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
          <EmptyState onNew={startNew} />
        ) : (
          <>
            <div style={s.pageTitle}>{isNew ? "New Schedule" : selected?.name}</div>
            <div style={s.pageSub}>
              {isNew ? "Configure trigger, build your workflow, then save." : `Editing schedule — ${form.task_ids.length} task(s) in workflow`}
            </div>

            {/* ── 1. Schedule Config ── */}
            <div style={s.section}>
              <div style={s.secTitle}>Schedule Configuration</div>
              <div style={s.row2}>
                <div>
                  <label style={s.label}>Schedule Name *</label>
                  <input style={s.input} placeholder="e.g. Daily Report" value={form.name} onChange={f("name")} />
                </div>
                <div>
                  <label style={s.label}>Status</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    {[true, false].map(v => (
                      <div key={String(v)} style={s.radioChip(form.is_active === v)} onClick={() => setFormAndRef(p => ({ ...p, is_active: v }))}>
                        {v ? "Active" : "Inactive"}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div style={s.fieldGroup}>
                <label style={s.label}>Description (optional)</label>
                <textarea style={s.textarea} placeholder="What does this schedule do?" value={form.description} onChange={f("description")} />
              </div>
            </div>

            {/* ── 2. Trigger Config ── */}
            <TriggerSection form={form} setForm={setForm} f={f} scheduleId={selected?.id} />

            {/* ── 3. Workflow Builder entry point ── */}
      <WorkflowSection
              form={form}
              allTasks={allTasks}
              onOpenBuilder={() => setShowBuilder(true)}
            />

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

            {/* Run History link */}
            {selected && (
              <div style={{ marginTop: 16 }}>
                <button
                  style={{ ...s.btnRun, display: "inline-flex", alignItems: "center", gap: 8 }}
                  onClick={() => onOpenRunHistory && onOpenRunHistory(selected.id)}
                >
                  📋 View Run History
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function EmptyState({ onNew }) {
  return (
    <div style={{ textAlign: "center", marginTop: 80 }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>🔀</div>
      <div style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9", marginBottom: 8 }}>No schedule selected</div>
      <div style={{ fontSize: 13, color: "#475569", marginBottom: 24 }}>
        Select a schedule from the left, or create a new one.
      </div>
      <button
        style={{ padding: "10px 24px", borderRadius: 9, background: "#6366f1", border: "none", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer" }}
        onClick={onNew}
      >
        + Create Schedule
      </button>
    </div>
  );
}

function TriggerSection({ form, setForm, f, scheduleId }) {
  return (
    <div style={s.section}>
      <div style={s.secTitle}>Trigger Configuration</div>
      <div style={{ ...s.fieldGroup }}>
        <label style={s.label}>Trigger Type</label>
        <div style={s.radioRow}>
          {TRIGGER_TYPES.map(t => (
            <div key={t.id} style={s.radioChip(form.trigger_type === t.id)}
              onClick={() => setForm(p => ({ ...p, trigger_type: t.id }))} title={t.desc}>
              {t.label}
            </div>
          ))}
        </div>
      </div>
      {form.trigger_type === "interval" && (
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <label style={s.label}>Every</label>
            <input style={s.input} type="number" min="1" placeholder="e.g. 30" value={form.interval_value} onChange={f("interval_value")} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={s.label}>Unit</label>
            <select style={s.select} value={form.interval_unit} onChange={f("interval_unit")}>
              {INTERVAL_UNITS.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div style={{ flex: 2, paddingBottom: 2 }}>
            <div style={{ fontSize: 12, color: "#475569" }}>Runs every {form.interval_value || "?"} {form.interval_unit}</div>
          </div>
        </div>
      )}
      {form.trigger_type === "cron" && (
        <div style={s.fieldGroup}>
          <label style={s.label}>Cron Expression</label>
          <input style={s.input} placeholder="*/5 * * * *" value={form.cron_expression} onChange={f("cron_expression")} />
          <div style={s.hint}>
            Format: minute hour day month weekday &nbsp;|&nbsp;
            Examples: <code style={{ color: "#818cf8" }}>*/5 * * * *</code> = every 5 min &nbsp;
            <code style={{ color: "#818cf8" }}>0 9 * * 1-5</code> = weekdays at 9am
          </div>
        </div>
      )}
      {form.trigger_type === "manual" && (
        <div style={{ fontSize: 12, color: "#475569" }}>This schedule runs only when triggered manually via Run Now.</div>
      )}

      {form.trigger_type === "filesystem" && (
        <FilesystemTriggerConfig form={form} setForm={setForm} />
      )}

      {form.trigger_type === "email_imap" && (
        <EmailTriggerConfig form={form} setForm={setForm} scheduleId={scheduleId} />
      )}
    </div>
  );
}

/**
 * WorkflowSection
 * Shows a preview of the current workflow nodes and an "Open Builder" button.
 */
function WorkflowSection({ form, allTasks, onOpenBuilder }) {
  const workflow = form.workflow_json;
  const nodes = workflow?.nodes || [];
  console.log("[WF] WorkflowSection render — workflow_json:", workflow, "nodes:", nodes.length);

  // Build a readable preview of the node chain
  const taskNodes = nodes.filter(n => n.type === "task" && n.taskId);
  const linkedTaskNames = taskNodes.map(n => {
    const t = allTasks.find(at => at.id === n.taskId);
    return t ? t.name : `Task #${n.taskId}`;
  });

  return (
    <div style={s.section}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={s.secTitle}>Workflow</div>
        <button
          onClick={onOpenBuilder}
          style={{
            padding: "6px 14px", borderRadius: 8, border: "1px solid #4f46e5",
            background: "#1e1f3a", color: "#818cf8", fontSize: 12, fontWeight: 700, cursor: "pointer",
            display: "flex", alignItems: "center", gap: 6,
          }}
        >
          🔀 {nodes.length > 0 ? "Edit Workflow" : "Build Workflow"}
        </button>
      </div>

      {nodes.length === 0 ? (
        <div style={{ fontSize: 12, color: "#475569" }}>
          No workflow built yet. Click "Build Workflow" to open the visual editor.
        </div>
      ) : (
        <>
          {/* Visual node chain preview */}
          <div style={s.wfStrip}>
            {nodes.map((node, idx) => (
              <React.Fragment key={node.id}>
                <span style={s.wfNode(node.type)}>{node.label || node.type}</span>
                {idx < nodes.length - 1 && <span style={s.wfArrow}>→</span>}
              </React.Fragment>
            ))}
          </div>

          {/* Linked tasks summary */}
          {linkedTaskNames.length > 0 && (
            <div style={{ marginTop: 10, fontSize: 11, color: "#475569" }}>
              Linked tasks: {linkedTaskNames.join(" → ")}
            </div>
          )}

          {/* Warn if task nodes have no linked task */}
          {nodes.filter(n => n.type === "task" && !n.taskId).length > 0 && (
            <div style={{ marginTop: 8, fontSize: 11, color: "#f59e0b" }}>
              ⚠ {nodes.filter(n => n.type === "task" && !n.taskId).length} task node(s) have no linked task — open the builder to configure them.
            </div>
          )}
        </>
      )}

      <div style={s.callout}>
        Web permissions are not stored on the schedule itself. Each linked task uses the selected agent&apos;s
        Tavily permissions. Use Tools Management to control <code>perform_search</code> and <code>open_result_links</code>.
      </div>
    </div>
  );
}

// ── Filesystem Trigger Configuration ─────────────────────────────────────────

const FS_EVENT_OPTIONS = [
  { id: "created",  label: "Created" },
  { id: "modified", label: "Modified" },
  { id: "deleted",  label: "Deleted" },
  { id: "moved",    label: "Moved / Renamed" },
];

function FilesystemTriggerConfig({ form, setForm }) {
  const toggleEvent = (evtId) => {
    setForm(prev => {
      const current = prev.fs_events || [];
      const next = current.includes(evtId)
        ? current.filter(e => e !== evtId)
        : [...current, evtId];
      return { ...prev, fs_events: next };
    });
  };

  return (
    <div style={{ marginTop: 16 }}>
      {/* Watch path */}
      <div style={s.fieldGroup}>
        <label style={s.label}>Watch Path *</label>
        <input
          style={s.input}
          placeholder="/workspace/incoming  or  C:/Users/you/Documents/incoming"
          value={form.fs_watch_path || ""}
          onChange={e => setForm(p => ({ ...p, fs_watch_path: e.target.value }))}
        />
        <div style={s.hint}>Absolute path to the folder to watch. Must be accessible by the backend.</div>
      </div>

      {/* Events */}
      <div style={s.fieldGroup}>
        <label style={s.label}>Watch Events</label>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {FS_EVENT_OPTIONS.map(opt => {
            const active = (form.fs_events || []).includes(opt.id);
            return (
              <div
                key={opt.id}
                style={{
                  padding: "5px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: "pointer",
                  border: `1px solid ${active ? "#6366f1" : "#2d3148"}`,
                  background: active ? "#1e1f3a" : "#0f1117",
                  color: active ? "#818cf8" : "#64748b",
                  transition: "all .12s",
                }}
                onClick={() => toggleEvent(opt.id)}
              >
                {opt.label}
              </div>
            );
          })}
        </div>
      </div>

      {/* Recursive + Target + Enabled */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div>
          <label style={s.label}>Recursive</label>
          <div style={{ display: "flex", gap: 8 }}>
            {[true, false].map(v => (
              <div
                key={String(v)}
                style={s.radioChip(form.fs_recursive === v)}
                onClick={() => setForm(p => ({ ...p, fs_recursive: v }))}
              >
                {v ? "Yes (subfolders)" : "No (top level only)"}
              </div>
            ))}
          </div>
        </div>
        <div>
          <label style={s.label}>Target</label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {[
              { id: "file",   label: "Files only" },
              { id: "folder", label: "Folders only" },
              { id: "both",   label: "Both" },
            ].map(opt => (
              <div
                key={opt.id}
                style={s.radioChip((form.fs_target || "both") === opt.id)}
                onClick={() => setForm(p => ({ ...p, fs_target: opt.id }))}
              >
                {opt.label}
              </div>
            ))}
          </div>
        </div>
        <div>
          <label style={s.label}>Enabled</label>
          <div style={{ display: "flex", gap: 8 }}>
            {[true, false].map(v => (
              <div
                key={String(v)}
                style={s.radioChip(form.fs_enabled === v)}
                onClick={() => setForm(p => ({ ...p, fs_enabled: v }))}
              >
                {v ? "Active" : "Paused"}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Extension filter + filename pattern */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div>
          <label style={s.label}>Extension Filter (optional)</label>
          <input
            style={s.input}
            placeholder=".pdf, .txt, .csv"
            value={form.fs_extension_filter || ""}
            onChange={e => setForm(p => ({ ...p, fs_extension_filter: e.target.value }))}
          />
          <div style={s.hint}>Comma-separated. Leave blank for all files.</div>
        </div>
        <div>
          <label style={s.label}>Filename Pattern (optional)</label>
          <input
            style={s.input}
            placeholder="report_*.pdf"
            value={form.fs_filename_pattern || ""}
            onChange={e => setForm(p => ({ ...p, fs_filename_pattern: e.target.value }))}
          />
          <div style={s.hint}>fnmatch pattern. Leave blank to match all filenames.</div>
        </div>
      </div>

      {/* Debounce */}
      <div style={s.fieldGroup}>
        <label style={s.label}>Debounce (seconds)</label>
        <input
          style={{ ...s.input, width: 120 }}
          type="number"
          min="0"
          max="60"
          value={form.fs_debounce_seconds ?? 3}
          onChange={e => setForm(p => ({ ...p, fs_debounce_seconds: e.target.value }))}
        />
        <div style={s.hint}>
          Minimum seconds between workflow triggers. Prevents duplicate runs from rapid file saves.
          Default: 3s.
        </div>
      </div>

      {/* Summary */}
      {form.fs_watch_path && (
        <div style={{ padding: "10px 14px", background: "#0f1117", borderRadius: 8, border: "1px solid #2d3148", fontSize: 12, color: "#64748b", marginTop: 8 }}>
          Watching <span style={{ color: "#818cf8" }}>{form.fs_watch_path}</span>
          {form.fs_recursive ? " (recursive)" : " (top level)"}
          {" · "}target: <span style={{ color: "#f59e0b" }}>{form.fs_target || "both"}</span>
          {" · "}events: <span style={{ color: "#22d3ee" }}>{(form.fs_events || []).join(", ") || "none"}</span>
          {form.fs_extension_filter ? ` · ext: ${form.fs_extension_filter}` : ""}
          {form.fs_filename_pattern ? ` · pattern: ${form.fs_filename_pattern}` : ""}
          {" · "}debounce: {form.fs_debounce_seconds}s
        </div>
      )}
    </div>
  );
}

// ── Email IMAP Trigger Configuration ─────────────────────────────────────────

function EmailTriggerConfig({ form, setForm, scheduleId }) {
  const [testStatus, setTestStatus]   = useState(null);   // null | {ok, message}
  const [testing, setTesting]         = useState(false);
  const [logs, setLogs]               = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [showLogs, setShowLogs]       = useState(false);

  const set = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }));
  const setBool = (key, val) => setForm(p => ({ ...p, [key]: val }));

  // Test connection — uses saved schedule if id exists, otherwise raw form values
  const handleTest = async () => {
    setTesting(true); setTestStatus(null);
    try {
      let result;
      if (scheduleId) {
        result = await testEmailConnection(scheduleId);
      } else {
        result = await testImapTrigger({
          host:     form.em_host,
          port:     Number(form.em_port) || 993,
          use_ssl:  form.em_use_ssl,
          username: form.em_username,
          password: form.em_password,
          mailbox:  form.em_mailbox || "INBOX",
        });
      }
      setTestStatus(result);
    } catch (e) {
      setTestStatus({ ok: false, message: e.response?.data?.detail || String(e) });
    } finally {
      setTesting(false);
    }
  };

  const handleLoadLogs = async () => {
    if (!scheduleId) return;
    setLogsLoading(true);
    try {
      const data = await fetchEmailTriggerLogs(scheduleId, 20);
      setLogs(data);
      setShowLogs(true);
    } catch (e) {
      setLogs([]);
    } finally {
      setLogsLoading(false);
    }
  };

  return (
    <div style={{ marginTop: 16 }}>

      {/* ── Connection ── */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div>
          <label style={s.label}>IMAP Host *</label>
          <input style={s.input} placeholder="imap.gmail.com" value={form.em_host || ""} onChange={set("em_host")} />
        </div>
        <div>
          <label style={s.label}>Port</label>
          <input style={s.input} type="number" placeholder="993" value={form.em_port ?? 993} onChange={set("em_port")} />
        </div>
        <div>
          <label style={s.label}>SSL</label>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            {[true, false].map(v => (
              <div key={String(v)} style={s.radioChip(form.em_use_ssl === v)} onClick={() => setBool("em_use_ssl", v)}>
                {v ? "SSL/TLS" : "STARTTLS"}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div>
          <label style={s.label}>Email / Username *</label>
          <input style={s.input} placeholder="you@gmail.com" value={form.em_username || ""} onChange={set("em_username")} autoComplete="off" />
        </div>
        <div>
          <label style={s.label}>Password / App Password *</label>
          <input style={s.input} type="password" placeholder={scheduleId ? "Leave blank to keep saved" : "App password"} value={form.em_password || ""} onChange={set("em_password")} autoComplete="new-password" />
          <div style={s.hint}>Stored encrypted. Use an app-specific password for Gmail/Outlook.</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div>
          <label style={s.label}>Mailbox</label>
          <input style={s.input} placeholder="INBOX" value={form.em_mailbox || "INBOX"} onChange={set("em_mailbox")} />
        </div>
        <div>
          <label style={s.label}>Poll Interval (minutes)</label>
          <input style={s.input} type="number" min="1" max="1440" placeholder="5" value={form.em_poll_interval_minutes ?? 5} onChange={set("em_poll_interval_minutes")} />
          <div style={s.hint}>How often to check for new emails. Min 1 min.</div>
        </div>
      </div>

      {/* ── Test connection ── */}
      <div style={{ marginBottom: 16 }}>
        <button
          style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#94a3b8", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
          onClick={handleTest}
          disabled={testing}
        >
          {testing ? "Testing…" : "🔌 Test Connection"}
        </button>
        {testStatus && (
          <span style={{ marginLeft: 12, fontSize: 12, color: testStatus.ok ? "#4ade80" : "#f87171" }}>
            {testStatus.ok ? "✓ " : "✗ "}{testStatus.message}
          </span>
        )}
      </div>

      {/* ── Filters ── */}
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 10 }}>Email Filters (all optional)</div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div>
          <label style={s.label}>Sender contains</label>
          <input style={s.input} placeholder="boss@company.com" value={form.em_filter_sender || ""} onChange={set("em_filter_sender")} />
        </div>
        <div>
          <label style={s.label}>Subject contains</label>
          <input style={s.input} placeholder="Invoice" value={form.em_filter_subject || ""} onChange={set("em_filter_subject")} />
        </div>
      </div>

      <div style={s.fieldGroup}>
        <label style={s.label}>Body contains</label>
        <input style={s.input} placeholder="urgent" value={form.em_filter_body || ""} onChange={set("em_filter_body")} />
        <div style={s.hint}>Fetches full message body to check — slightly slower.</div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div>
          <label style={s.label}>Unread only</label>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            {[true, false].map(v => (
              <div key={String(v)} style={s.radioChip(form.em_unread_only === v)} onClick={() => setBool("em_unread_only", v)}>
                {v ? "Yes" : "No"}
              </div>
            ))}
          </div>
        </div>
        <div>
          <label style={s.label}>Has attachment</label>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            {[false, true].map(v => (
              <div key={String(v)} style={s.radioChip(form.em_has_attachment === v)} onClick={() => setBool("em_has_attachment", v)}>
                {v ? "Required" : "Any"}
              </div>
            ))}
          </div>
        </div>
        <div>
          <label style={s.label}>Enabled</label>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            {[true, false].map(v => (
              <div key={String(v)} style={s.radioChip(form.em_enabled === v)} onClick={() => setBool("em_enabled", v)}>
                {v ? "Active" : "Paused"}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={s.fieldGroup}>
        <label style={s.label}>Attachment extensions (optional)</label>
        <input style={s.input} placeholder=".pdf, .csv, .xlsx" value={form.em_attachment_extensions || ""} onChange={set("em_attachment_extensions")} />
        <div style={s.hint}>Comma-separated. Only fires if attachment matches. Leave blank for any.</div>
      </div>

      {/* ── Processed emails log ── */}
      {scheduleId && (
        <div style={{ marginTop: 8 }}>
          <button
            style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#64748b", fontSize: 11, fontWeight: 600, cursor: "pointer" }}
            onClick={handleLoadLogs}
            disabled={logsLoading}
          >
            {logsLoading ? "Loading…" : "📬 Show Processed Emails"}
          </button>

          {showLogs && (
            <div style={{ marginTop: 10 }}>
              {logs.length === 0 ? (
                <div style={{ fontSize: 12, color: "#475569" }}>No emails processed yet.</div>
              ) : (
                <table style={s.table}>
                  <thead>
                    <tr>
                      <th style={s.th}>UID</th>
                      <th style={s.th}>From</th>
                      <th style={s.th}>Subject</th>
                      <th style={s.th}>Seen at</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map(l => (
                      <tr key={l.id}>
                        <td style={s.td}>{l.message_uid}</td>
                        <td style={s.td}>{l.sender || "—"}</td>
                        <td style={s.td}>{l.subject || "—"}</td>
                        <td style={s.td}>{l.seen_at ? new Date(l.seen_at).toLocaleString() : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
