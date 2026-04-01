import React, { useState, useEffect } from "react";
import { fetchDomains, fetchAgents, fetchLLMConfigs, fetchTasks, fetchAgentToolAccess, createTask, updateTask, deleteTask, dryRunTask } from "../api";
import { toPlainText } from "../utils/sanitizeLlmResponse";
import FolderPicker from "./FolderPicker";

const PROVIDERS = [
  { id: "ollama", label: "Ollama" },
  { id: "openai", label: "OpenAI" },
  { id: "gemini", label: "Gemini" },
  { id: "claude", label: "Claude" },
  { id: "custom", label: "Custom" },
];

const TOOL_MODES = [
  { id: "allowed", label: "Allowed", desc: "Agent can use all available tools" },
  { id: "restricted", label: "Restricted", desc: "Read-only tool access" },
  { id: "none", label: "None", desc: "No tool access" },
];

const s = {
  layout: { display: "flex", flex: 1, overflow: "hidden", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif" },
  // Left panel
  left: { width: 260, minWidth: 260, background: "#13151f", borderRight: "1px solid #1e2130", display: "flex", flexDirection: "column", overflowY: "auto" },
  leftHeader: { padding: "20px 18px 14px", borderBottom: "1px solid #1e2130" },
  leftTitle: { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1.2, color: "#475569", marginBottom: 10 },
  newTaskBtn: { width: "100%", padding: "9px 14px", background: "#4f46e5", border: "none", borderRadius: 8, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", textAlign: "left", display: "flex", alignItems: "center", gap: 8 },
  searchBox: { padding: "10px 18px", borderBottom: "1px solid #1e2130" },
  searchInput: { width: "100%", padding: "7px 11px", borderRadius: 7, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 13, outline: "none", boxSizing: "border-box" },
  taskList: { flex: 1, overflowY: "auto", padding: "8px 0" },
  taskItem: (active) => ({
    padding: "10px 18px", cursor: "pointer", fontSize: 13, color: active ? "#818cf8" : "#94a3b8",
    background: active ? "#1e2130" : "transparent", borderLeft: `3px solid ${active ? "#6366f1" : "transparent"}`,
    transition: "all .1s",
  }),
  taskItemName: { fontWeight: 600, marginBottom: 2 },
  taskItemMeta: { fontSize: 11, color: "#475569" },
  // Right form
  right: { flex: 1, overflowY: "auto", padding: "32px 40px", maxWidth: 860 },
  title: { fontSize: 24, fontWeight: 700, color: "#f8fafc", marginBottom: 4 },
  subtitle: { fontSize: 13, color: "#64748b", marginBottom: 28 },
  section: { background: "#1e2130", borderRadius: 12, padding: "22px 26px", marginBottom: 18, border: "1px solid #2d3148" },
  sectionTitle: { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 16 },
  label: { fontSize: 13, color: "#94a3b8", marginBottom: 6, display: "block" },
  input: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none", boxSizing: "border-box" },
  textarea: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none", resize: "vertical", minHeight: 110, boxSizing: "border-box", fontFamily: "inherit" },
  row2: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 },
  row3: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 14 },
  fieldGroup: { marginBottom: 14 },
  inputSmall: { width: "100%", padding: "8px 11px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 13, outline: "none", boxSizing: "border-box" },
  select: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none" },
  hint: { fontSize: 12, color: "#475569", marginTop: 4 },
  error: { color: "#f87171", fontSize: 12, marginTop: 4 },
  success: { color: "#4ade80", fontSize: 12, marginTop: 4 },
  // Agent tree
  domainRow: { display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", cursor: "pointer", borderRadius: 7, fontSize: 13, fontWeight: 600, color: "#94a3b8", userSelect: "none" },
  agentRow: (active) => ({ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px 6px 26px", cursor: "pointer", borderRadius: 7, fontSize: 13, color: active ? "#818cf8" : "#64748b", background: active ? "#1a1d2e" : "transparent", fontWeight: active ? 600 : 400 }),
  selectedPath: { fontSize: 12, color: "#818cf8", marginTop: 8, padding: "5px 10px", background: "#1a1d2e", borderRadius: 6, display: "inline-block" },
  // Tool mode chips
  modeChip: (active) => ({ padding: "7px 14px", borderRadius: 8, border: `1px solid ${active ? "#6366f1" : "#2d3148"}`, background: active ? "#1e1f3a" : "#0f1117", color: active ? "#818cf8" : "#64748b", cursor: "pointer", fontSize: 13, fontWeight: 600, transition: "all .15s" }),
  // Action buttons
  btnRow: { display: "flex", gap: 10, marginTop: 8, flexWrap: "wrap", alignItems: "center" },
  btn: { padding: "9px 20px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 14, fontWeight: 600 },
  btnPrimary: { background: "#6366f1", color: "#fff" },
  btnSuccess: { background: "#22c55e", color: "#fff" },
  btnSecondary: { background: "#2d3148", color: "#cbd5e1" },
  btnDanger: { background: "#7f1d1d", color: "#fca5a5" },
  btnDryRun: { background: "#0f2a1a", border: "1px solid #166534", color: "#4ade80", padding: "9px 20px", borderRadius: 8, cursor: "pointer", fontSize: 14, fontWeight: 600 },
  accessCard: { background: "#0f1117", border: "1px solid #2d3148", borderRadius: 10, padding: "14px 16px", marginTop: 12 },
  accessTitle: { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 10 },
  pillRow: { display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 },
  pill: (active, tone = "blue") => ({
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 10px",
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 600,
    border: `1px solid ${active ? (tone === "green" ? "#166534" : "#6366f1") : "#2d3148"}`,
    background: active ? (tone === "green" ? "#0f2a1a" : "#1e1f3a") : "#13151f",
    color: active ? (tone === "green" ? "#4ade80" : "#818cf8") : "#64748b",
  }),
  // Result
  resultBox: { background: "#0a0c14", border: "1px solid #1e2130", borderRadius: 8, padding: "14px 16px", minHeight: 100, fontFamily: "monospace", fontSize: 13, color: "#a3e635", whiteSpace: "pre-wrap", lineHeight: 1.6 },
  stepsBox: { background: "#0f1117", border: "1px solid #1e2130", borderRadius: 8, padding: "12px 14px", marginBottom: 12 },
  stepLine: { fontSize: 12, fontFamily: "monospace", color: "#94a3b8", lineHeight: 1.8 },
  stepTool: { color: "#818cf8" },
};

const emptyForm = {
  name: "", description: "", agent_id: null,
  llm_config_id: null, llm_provider: "", llm_model: "", llm_temperature: "", llm_max_tokens: "", llm_top_p: "",
  llm_system_behavior: "", tool_usage_mode: "allowed", workflow: "", folder_path: "", status: "draft",
};

export default function TaskCreationPage({ onViewTask }) {
  const [domains, setDomains] = useState([]);
  const [agents, setAgents] = useState([]);
  const [llmConfigs, setLlmConfigs] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [search, setSearch] = useState("");
  const [selectedTask, setSelectedTask] = useState(null); // task being edited
  const [form, setForm] = useState(emptyForm);
  const [openDomains, setOpenDomains] = useState({});
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [dryRunResult, setDryRunResult] = useState(null);
  const [dryRunRunning, setDryRunRunning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showFolderPicker, setShowFolderPicker] = useState(false);
  const [agentWebAccess, setAgentWebAccess] = useState(null);

  const load = async () => {
    const [d, a, c, t] = await Promise.all([
      fetchDomains().catch(() => []),
      fetchAgents().catch(() => []),
      fetchLLMConfigs().catch(() => []),
      fetchTasks().catch(() => []),
    ]);
    setDomains(d);
    setAgents(a);
    setLlmConfigs(c);
    setTasks(t);
    // default all domains open
    const open = {};
    d.forEach(dom => { open[dom.id] = true; });
    setOpenDomains(open);
  };

  useEffect(() => { load(); }, []);

  const startNew = () => {
    setSelectedTask(null);
    setForm(emptyForm);
    setFormError(""); setFormSuccess(""); setDryRunResult(null);
  };

  const selectTask = (task) => {
    setSelectedTask(task);
    setForm({
      name: task.name,
      description: task.description,
      agent_id: task.agent_id || null,
      llm_config_id: task.llm_config_id || null,
      llm_provider: task.llm_provider || "",
      llm_model: task.llm_model || "",
      llm_temperature: task.llm_temperature ?? "",
      llm_max_tokens: task.llm_max_tokens ?? "",
      llm_top_p: task.llm_top_p ?? "",
      llm_system_behavior: task.llm_system_behavior || "",
      tool_usage_mode: task.tool_usage_mode || "allowed",
      workflow: task.workflow || "",
      folder_path: task.folder_path || "",
      status: task.status || "draft",
    });
    setFormError(""); setFormSuccess(""); setDryRunResult(null);
  };

  const f = (key) => (e) => {
    setForm(prev => ({ ...prev, [key]: e.target.value }));
    setFormError(""); setFormSuccess("");
  };

  const toggleDomain = (id) => setOpenDomains(prev => ({ ...prev, [id]: !prev[id] }));

  const selectAgent = (agentId) => {
    setForm(prev => ({ ...prev, agent_id: prev.agent_id === agentId ? null : agentId }));
  };

  useEffect(() => {
    const loadAgentWebAccess = async () => {
      if (!form.agent_id) {
        setAgentWebAccess(null);
        return;
      }
      try {
        const rows = await fetchAgentToolAccess(form.agent_id);
        const webRow = rows.find(r => r.tool_key === "web" || r.tool_key === "web_search");
        setAgentWebAccess(webRow || null);
      } catch {
        setAgentWebAccess(null);
      }
    };
    loadAgentWebAccess();
  }, [form.agent_id]);

  const selectedAgent = agents.find(a => a.id === form.agent_id);
  const selectedDomain = selectedAgent ? domains.find(d => d.id === selectedAgent.domain_id) : null;

  const buildPayload = () => ({
    name: form.name.trim(),
    description: form.description.trim(),
    agent_id: form.agent_id || null,
    llm_config_id: form.llm_config_id ? Number(form.llm_config_id) : null,
    llm_provider: form.llm_provider || null,
    llm_model: form.llm_model || null,
    llm_temperature: form.llm_temperature !== "" ? parseFloat(form.llm_temperature) : null,
    llm_max_tokens: form.llm_max_tokens !== "" ? parseInt(form.llm_max_tokens) : null,
    llm_top_p: form.llm_top_p !== "" ? parseFloat(form.llm_top_p) : null,
    llm_system_behavior: form.llm_system_behavior || null,
    tool_usage_mode: form.tool_usage_mode,
    workflow: form.workflow || null,
    folder_path: form.folder_path || null,
    status: form.status,
  });

  const handleSave = async () => {
    setFormError(""); setFormSuccess("");
    if (!form.name.trim()) { setFormError("Task name is required"); return; }
    if (!form.description.trim()) { setFormError("Task description is required"); return; }
    setSaving(true);
    try {
      const payload = buildPayload();
      if (selectedTask) {
        const updated = await updateTask(selectedTask.id, payload);
        setSelectedTask(updated);
        setFormSuccess("Task updated");
      } else {
        const created = await createTask(payload);
        setSelectedTask(created);
        setFormSuccess("Task created");
      }
      await load();
    } catch (e) {
      setFormError(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedTask || !confirm(`Delete task "${selectedTask.name}"?`)) return;
    await deleteTask(selectedTask.id);
    startNew();
    await load();
  };

  const handleDryRun = async () => {
    if (!form.description.trim()) { setFormError("Task description is required for dry run"); return; }
    setDryRunRunning(true); setDryRunResult(null); setFormError("");
    try {
      const payload = { ...buildPayload() };
      const data = await dryRunTask(payload);
      setDryRunResult({ ...data, result: toPlainText(data.result) });
    } catch (e) {
      setFormError(e.response?.data?.detail || "Dry run failed");
    } finally {
      setDryRunRunning(false);
    }
  };

  const filteredTasks = tasks.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={s.layout}>
      {/* ── Left Panel ── */}
      <aside style={s.left}>
        <div style={s.leftHeader}>
          <div style={s.leftTitle}>Tasks</div>
          <button style={s.newTaskBtn} onClick={startNew}>
            <span>＋</span> Create New Task
          </button>
        </div>
        <div style={s.searchBox}>
          <input
            style={s.searchInput}
            placeholder="Search tasks..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div style={s.taskList}>
          {filteredTasks.length === 0 ? (
            <div style={{ padding: "14px 18px", fontSize: 12, color: "#475569" }}>
              {search ? "No tasks match" : "No tasks yet"}
            </div>
          ) : filteredTasks.map(task => (
            <div
              key={task.id}
              style={s.taskItem(selectedTask?.id === task.id)}
              onClick={() => selectTask(task)}
              onMouseEnter={e => { if (selectedTask?.id !== task.id) e.currentTarget.style.background = "#1a1d2e"; }}
              onMouseLeave={e => { if (selectedTask?.id !== task.id) e.currentTarget.style.background = "transparent"; }}
            >
              <div style={s.taskItemName}>{task.name}</div>
              <div style={s.taskItemMeta}>
                {task.agent ? `${task.agent.domain?.name} › ${task.agent.name}` : "No agent"}
                {" · "}{task.status}
              </div>
              {onViewTask && (
                <div
                  style={{ fontSize: 11, color: "#6366f1", marginTop: 3, cursor: "pointer" }}
                  onClick={e => { e.stopPropagation(); onViewTask(task.id); }}
                >
                  📊 View Details →
                </div>
              )}
            </div>
          ))}
        </div>
      </aside>

      {/* ── Right Form ── */}
      <div style={s.right}>
        <div style={s.title}>{selectedTask ? "Edit Task" : "New Task"}</div>
        <div style={s.subtitle}>
          {selectedTask ? `Editing: ${selectedTask.name}` : "Define a task with agent, LLM config, and optional workflow steps."}
        </div>

        {/* 1. Task Basics */}
        <div style={s.section}>
          <div style={s.sectionTitle}>Task Basics</div>
          <div style={s.fieldGroup}>
            <label style={s.label}>Task Name *</label>
            <input style={s.input} placeholder="e.g. Weekly Report Generator" value={form.name} onChange={f("name")} />
          </div>
          <div style={s.fieldGroup}>
            <label style={s.label}>Task Description *</label>
            <textarea
              style={{ ...s.textarea, minHeight: 130 }}
              placeholder="Describe what this task should do. This acts as the instruction/prompt for the agent..."
              value={form.description}
              onChange={f("description")}
            />
            <div style={s.hint}>This is the main prompt sent to the agent.</div>
          </div>
        </div>

        {/* 2. Agent Selection */}
        <AgentTree
          domains={domains}
          agents={agents}
          openDomains={openDomains}
          toggleDomain={toggleDomain}
          selectedAgentId={form.agent_id}
          onSelect={selectAgent}
          selectedAgent={selectedAgent}
          selectedDomain={selectedDomain}
        />

        {selectedAgent && (
          <div style={s.accessCard}>
            <div style={s.accessTitle}>Web Access</div>
            <div style={{ fontSize: 13, color: "#94a3b8", lineHeight: 1.5 }}>
              Web search is controlled by the selected agent&apos;s tool permissions.
              Configure Tavily access in Tools Management for this agent.
            </div>
            <div style={s.pillRow}>
              <span style={s.pill(!!agentWebAccess?.granted_permissions?.includes("perform_search"), "blue")}>
                perform_search
              </span>
              <span style={s.pill(!!agentWebAccess?.granted_permissions?.includes("open_result_links"), "green")}>
                open_result_links
              </span>
            </div>
          </div>
        )}

        {/* 3. LLM Configuration */}
        <LLMConfigSection
          llmConfigs={llmConfigs}
          form={form}
          setForm={setForm}
          f={f}
        />

        {/* 4. Workflow */}
        <div style={s.section}>
          <div style={s.sectionTitle}>Step-by-Step Workflow (Optional)</div>
          <textarea
            style={{ ...s.textarea, minHeight: 120, fontFamily: "monospace", fontSize: 13 }}
            placeholder={"One step per line, e.g.:\nRead the files in the folder\nExtract key information\nSummarize findings\nReturn structured output"}
            value={form.workflow}
            onChange={f("workflow")}
          />
          <div style={s.hint}>Each line is treated as a step. Leave blank to let the agent decide.</div>
        </div>

        {/* 5. Folder Path */}
        <div style={s.section}>
          <div style={s.sectionTitle}>Working Folder</div>
          <div style={s.fieldGroup}>
            <label style={s.label}>Folder Path</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                style={{ ...s.input, fontFamily: "monospace", fontSize: 13 }}
                placeholder="Click Browse to select a folder..."
                value={form.folder_path}
                onChange={f("folder_path")}
              />
              <button
                style={{ ...s.btn, ...s.btnSecondary, whiteSpace: "nowrap", fontSize: 13 }}
                onClick={() => setShowFolderPicker(true)}
                type="button"
              >
                📁 Browse
              </button>
            </div>
            <div style={s.hint}>
              Folder is mounted from your host machine. Path shown is the container path (under /workspace).
            </div>
          </div>
        </div>

        {showFolderPicker && (
          <FolderPicker
            onSelect={(path) => setForm(prev => ({ ...prev, folder_path: path }))}
            onClose={() => setShowFolderPicker(false)}
          />
        )}

        {/* Errors / Success */}
        {formError && <div style={{ ...s.error, marginBottom: 12 }}>⚠ {formError}</div>}
        {formSuccess && <div style={{ ...s.success, marginBottom: 12 }}>✓ {formSuccess}</div>}

        {/* 6. Actions */}
        <div style={s.btnRow}>
          <button style={s.btnDryRun} onClick={handleDryRun} disabled={dryRunRunning}>
            {dryRunRunning ? "⏳ Running..." : "⚗ Dry Run"}
          </button>
          <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : selectedTask ? "Update Task" : "Create Task"}
          </button>
          <button style={{ ...s.btn, ...s.btnSecondary }} onClick={startNew}>Reset</button>
          {selectedTask && (
            <button style={{ ...s.btn, ...s.btnDanger }} onClick={handleDelete}>Delete</button>
          )}
          {selectedTask && onViewTask && (
            <button
              style={{ ...s.btn, background: "#0f2a1a", border: "1px solid #166534", color: "#4ade80" }}
              onClick={() => onViewTask(selectedTask.id)}
            >
              📊 View Details
            </button>
          )}
          {!selectedTask && (
            <button
              style={{ ...s.btn, ...s.btnSecondary }}
              onClick={() => { setForm(prev => ({ ...prev, status: "draft" })); handleSave(); }}
            >
              Save as Draft
            </button>
          )}
        </div>

        {/* Dry Run Result */}
        {dryRunResult && (
          <div style={{ ...s.section, marginTop: 20 }}>
            <div style={s.sectionTitle}>Dry Run Result</div>
            {dryRunResult.steps?.length > 0 && (
              <div style={s.stepsBox}>
                {dryRunResult.steps.map((step, i) => (
                  <div key={i} style={{ ...s.stepLine, ...(step.startsWith("🔧") ? s.stepTool : {}) }}>
                    {step}
                  </div>
                ))}
              </div>
            )}
            <div style={s.resultBox}>{dryRunResult.result}</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function AgentTree({ domains, agents, openDomains, toggleDomain, selectedAgentId, onSelect, selectedAgent, selectedDomain }) {
  const agentsByDomain = (domainId) => agents.filter(a => a.domain_id === domainId);

  return (
    <div style={{ background: "#1e2130", borderRadius: 12, padding: "22px 26px", marginBottom: 18, border: "1px solid #2d3148" }}>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 12 }}>
        Agent Selection
      </div>
      {selectedAgent && (
        <div style={{ fontSize: 12, color: "#818cf8", marginBottom: 12, padding: "5px 10px", background: "#1a1d2e", borderRadius: 6, display: "inline-block" }}>
          ✓ {selectedDomain?.name} › {selectedAgent.name}
        </div>
      )}
      <div style={{ background: "#0f1117", borderRadius: 8, border: "1px solid #2d3148", padding: "8px 0", maxHeight: 260, overflowY: "auto" }}>
        {domains.length === 0 ? (
          <div style={{ padding: "12px 14px", fontSize: 12, color: "#475569" }}>No domains yet</div>
        ) : domains.map(domain => {
          const domAgents = agentsByDomain(domain.id);
          const isOpen = openDomains[domain.id] !== false;
          return (
            <div key={domain.id}>
              <div
                style={{ ...s.domainRow, justifyContent: "space-between" }}
                onClick={() => toggleDomain(domain.id)}
                onMouseEnter={e => e.currentTarget.style.background = "#1a1d2e"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 10, color: "#475569", transition: "transform .2s", display: "inline-block", transform: isOpen ? "rotate(90deg)" : "rotate(0deg)" }}>▶</span>
                  📁 {domain.name}
                </span>
                <span style={{ fontSize: 11, color: "#475569" }}>{domAgents.length}</span>
              </div>
              {isOpen && (
                domAgents.length === 0
                  ? <div style={{ padding: "4px 14px 4px 26px", fontSize: 12, color: "#374151", fontStyle: "italic" }}>No agents</div>
                  : domAgents.map(agent => (
                    <div
                      key={agent.id}
                      style={s.agentRow(selectedAgentId === agent.id)}
                      onClick={() => onSelect(agent.id)}
                      onMouseEnter={e => { if (selectedAgentId !== agent.id) e.currentTarget.style.background = "#1a1d2e"; }}
                      onMouseLeave={e => { if (selectedAgentId !== agent.id) e.currentTarget.style.background = "transparent"; }}
                    >
                      <span style={{ fontSize: 11 }}>📄</span> {agent.name}
                    </div>
                  ))
              )}
            </div>
          );
        })}
      </div>
      <div style={{ fontSize: 12, color: "#475569", marginTop: 6 }}>Click an agent to select. Click again to deselect.</div>
    </div>
  );
}

function LLMConfigSection({ llmConfigs, form, setForm, f }) {
  const activeConfig = llmConfigs.find(c => c.is_active);

  return (
    <div style={{ background: "#1e2130", borderRadius: 12, padding: "22px 26px", marginBottom: 18, border: "1px solid #2d3148" }}>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 16 }}>
        LLM Configuration
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
        <div>
          <label style={s.label}>Base Config</label>
          <select
            style={s.select}
            value={form.llm_config_id || ""}
            onChange={e => setForm(prev => ({ ...prev, llm_config_id: e.target.value || null }))}
          >
            <option value="">{activeConfig ? `Active: ${activeConfig.label}` : "Use active config"}</option>
            {llmConfigs.map(c => (
              <option key={c.id} value={c.id}>{c.label} ({c.provider})</option>
            ))}
          </select>
          <div style={s.hint}>Leave blank to use the currently active config.</div>
        </div>
        <div>
          <label style={s.label}>Provider Override</label>
          <select style={s.select} value={form.llm_provider} onChange={f("llm_provider")}>
            <option value="">— inherit from config —</option>
            {PROVIDERS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
        <div>
          <label style={s.label}>Model Override</label>
          <input style={s.inputSmall} placeholder="e.g. gpt-4o" value={form.llm_model} onChange={f("llm_model")} />
        </div>
        <div>
          <label style={s.label}>Temperature</label>
          <input style={s.inputSmall} type="number" min="0" max="2" step="0.1" placeholder="inherit" value={form.llm_temperature} onChange={f("llm_temperature")} />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 14 }}>
        <div>
          <label style={s.label}>Max Tokens</label>
          <input style={s.inputSmall} type="number" min="1" placeholder="inherit" value={form.llm_max_tokens} onChange={f("llm_max_tokens")} />
        </div>
        <div>
          <label style={s.label}>Top-P</label>
          <input style={s.inputSmall} type="number" min="0" max="1" step="0.05" placeholder="inherit" value={form.llm_top_p} onChange={f("llm_top_p")} />
        </div>
        <div>
          <label style={s.label}>Tool Usage Mode</label>
          <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
            {TOOL_MODES.map(m => (
              <div
                key={m.id}
                style={s.modeChip(form.tool_usage_mode === m.id)}
                onClick={() => setForm(prev => ({ ...prev, tool_usage_mode: m.id }))}
                title={m.desc}
              >
                {m.label}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <label style={s.label}>System Behavior (Optional)</label>
        <textarea
          style={{ ...s.textarea, minHeight: 70 }}
          placeholder="Optional system-level instructions to prepend to the agent's skill..."
          value={form.llm_system_behavior}
          onChange={f("llm_system_behavior")}
        />
      </div>
    </div>
  );
}
