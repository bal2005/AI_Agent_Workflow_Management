/**
 * WorkflowConfigPanel
 * ────────────────────
 * Right sidebar shown when a node is selected.
 * Lets the user configure the node's label, description, linked task, etc.
 */
import React from "react";

const s = {
  panel:     { width: 280, background: "#13151f", borderLeft: "1px solid #1e2130", display: "flex", flexDirection: "column", overflow: "hidden" },
  head:      { padding: "16px 18px 12px", borderBottom: "1px solid #1e2130", display: "flex", alignItems: "center", justifyContent: "space-between" },
  title:     { fontSize: 13, fontWeight: 700, color: "#f1f5f9" },
  closeBtn:  { background: "none", border: "none", color: "#475569", cursor: "pointer", fontSize: 16, lineHeight: 1 },
  body:      { flex: 1, overflowY: "auto", padding: "16px 18px" },
  label:     { fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 5, display: "block", fontWeight: 600 },
  input:     { width: "100%", padding: "8px 10px", borderRadius: 7, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 12, outline: "none", boxSizing: "border-box" },
  textarea:  { width: "100%", padding: "8px 10px", borderRadius: 7, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 12, outline: "none", resize: "vertical", minHeight: 60, boxSizing: "border-box", fontFamily: "inherit" },
  select:    { width: "100%", padding: "8px 10px", borderRadius: 7, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 12, outline: "none" },
  field:     { marginBottom: 14 },
  divider:   { borderTop: "1px solid #1e2130", margin: "14px 0" },
  typeChip:  (active, color) => ({
    padding: "5px 12px", borderRadius: 7, fontSize: 11, fontWeight: 600, cursor: "pointer",
    border: `1px solid ${active ? color : "#2d3148"}`,
    background: active ? color + "22" : "#0f1117",
    color: active ? color : "#64748b",
    transition: "all .12s",
  }),
  hint:      { fontSize: 10, color: "#475569", marginTop: 4 },
  emptyMsg:  { fontSize: 12, color: "#475569", textAlign: "center", marginTop: 40, lineHeight: 1.6 },
};

const NODE_TYPES = [
  { id: "task",      label: "Task",      color: "#22d3ee" },
  { id: "condition", label: "Condition", color: "#f59e0b" },
  { id: "parallel",  label: "Parallel",  color: "#a78bfa" },
];

export default function WorkflowConfigPanel({ node, allTasks, onChange, onClose }) {
  if (!node) {
    return (
      <div style={s.panel}>
        <div style={s.head}>
          <span style={s.title}>Node Config</span>
        </div>
        <div style={s.emptyMsg}>
          Click a node<br />to configure it
        </div>
      </div>
    );
  }

  const isTrigger = node.type === "trigger";

  const update = (key, val) => onChange({ ...node, [key]: val });

  return (
    <div style={s.panel}>
      <div style={s.head}>
        <span style={s.title}>{isTrigger ? "Trigger Node" : "Node Config"}</span>
        <button style={s.closeBtn} onClick={onClose}>✕</button>
      </div>

      <div style={s.body}>
        {/* Label */}
        <div style={s.field}>
          <label style={s.label}>Label</label>
          <input
            style={s.input}
            value={node.label || ""}
            onChange={e => update("label", e.target.value)}
            placeholder="Node name..."
          />
        </div>

        {/* Description */}
        <div style={s.field}>
          <label style={s.label}>Description</label>
          <textarea
            style={s.textarea}
            value={node.description || ""}
            onChange={e => update("description", e.target.value)}
            placeholder="What does this node do?"
          />
        </div>

        {/* Trigger-specific: trigger type */}
        {isTrigger && (
          <div style={s.field}>
            <label style={s.label}>Trigger Type</label>
            <select
              style={s.select}
              value={node.triggerType || "manual"}
              onChange={e => update("triggerType", e.target.value)}
            >
              <option value="manual">Manual</option>
              <option value="interval">Interval</option>
              <option value="cron">Cron</option>
            </select>
            <div style={s.hint}>Controls when this workflow fires</div>
          </div>
        )}

        {/* Non-trigger: node type selector */}
        {!isTrigger && (
          <>
            <div style={s.field}>
              <label style={s.label}>Node Type</label>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {NODE_TYPES.map(t => (
                  <div
                    key={t.id}
                    style={s.typeChip(node.type === t.id, t.color)}
                    onClick={() => update("type", t.id)}
                  >
                    {t.label}
                  </div>
                ))}
              </div>
            </div>

            <div style={s.divider} />

            {/* Task link — only for task nodes */}
            {node.type === "task" && (
              <div style={s.field}>
                <label style={s.label}>Linked Task</label>
                <select
                  style={s.select}
                  value={node.taskId || ""}
                  onChange={e => update("taskId", e.target.value ? parseInt(e.target.value) : null)}
                >
                  <option value="">— Select a task —</option>
                  {allTasks.map(t => (
                    <option key={t.id} value={t.id}>
                      {t.name}{t.agent ? ` (${t.agent.name})` : ""}
                    </option>
                  ))}
                </select>
                <div style={s.hint}>Links this node to an existing task definition</div>
              </div>
            )}

            {/* Condition placeholder */}
            {node.type === "condition" && (
              <div style={{ padding: "10px 12px", background: "#1a1200", borderRadius: 8, border: "1px solid #78350f", fontSize: 11, color: "#92400e" }}>
                Conditional branching will be available in a future release. This node is a placeholder.
              </div>
            )}

            {/* Parallel placeholder */}
            {node.type === "parallel" && (
              <div style={{ padding: "10px 12px", background: "#1a1200", borderRadius: 8, border: "1px solid #78350f", fontSize: 11, color: "#92400e" }}>
                Parallel execution will be available in a future release. This node is a placeholder.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
