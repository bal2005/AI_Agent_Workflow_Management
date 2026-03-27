/**
 * WorkflowBuilder
 * ────────────────
 * Visual workflow editor inspired by n8n.
 * Renders a linear node canvas with a config panel sidebar.
 *
 * Props:
 *   initialWorkflow  — existing workflow object to edit (null = new)
 *   allTasks         — list of available task definitions from the backend
 *   scheduleName     — name of the parent schedule
 *   onSave(workflow) — called with the final workflow JSON when user saves
 *   onCancel()       — called when user cancels
 *
 * Workflow JSON shape (stored in schedule.workflow_json):
 * {
 *   nodes: [
 *     { id, type, label, description, taskId, triggerType },
 *     ...
 *   ]
 * }
 * Nodes are ordered by array index — position = execution order.
 */
import React, { useState, useCallback } from "react";
import WorkflowNodeCard from "./WorkflowNodeCard";
import WorkflowConfigPanel from "./WorkflowConfigPanel";

// ── Helpers ───────────────────────────────────────────────────────────────────

let _idCounter = Date.now();
const newId = () => `node_${++_idCounter}`;

/** Default trigger node — always the first node */
const makeTriggerNode = () => ({
  id: newId(),
  type: "trigger",
  label: "Start",
  description: "Workflow entry point",
  triggerType: "manual",
});

/** Default task node */
const makeTaskNode = () => ({
  id: newId(),
  type: "task",
  label: "New Task",
  description: "",
  taskId: null,
});

/** Build initial nodes from an existing workflow or create a fresh one */
const initNodes = (workflow) => {
  if (workflow?.nodes?.length) return workflow.nodes;
  return [makeTriggerNode()];
};

// ── Styles ────────────────────────────────────────────────────────────────────
const s = {
  root:       { display: "flex", flexDirection: "column", height: "100%", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif" },
  topBar:     { display: "flex", alignItems: "center", gap: 12, padding: "12px 20px", borderBottom: "1px solid #1e2130", background: "#13151f", flexShrink: 0 },
  topTitle:   { fontSize: 14, fontWeight: 700, color: "#f1f5f9", flex: 1 },
  btn:        { padding: "7px 16px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600 },
  btnPrimary: { background: "#6366f1", color: "#fff" },
  btnGhost:   { background: "none", border: "1px solid #2d3148", color: "#94a3b8" },
  btnAdd:     { background: "#0e2a30", border: "1px solid #0891b2", color: "#22d3ee", padding: "7px 14px", borderRadius: 8, cursor: "pointer", fontSize: 12, fontWeight: 600 },
  body:       { display: "flex", flex: 1, overflow: "hidden" },
  // Canvas
  canvas:     { flex: 1, overflowY: "auto", overflowX: "hidden", padding: "32px 0", display: "flex", flexDirection: "column", alignItems: "center", background: "#0f1117", backgroundImage: "radial-gradient(circle, #1e2130 1px, transparent 1px)", backgroundSize: "28px 28px" },
  addRow:     { display: "flex", gap: 8, marginTop: 8, marginBottom: 4 },
  addNodeBtn: (color) => ({
    padding: "5px 12px", borderRadius: 7, border: `1px solid ${color}`,
    background: color + "15", color, fontSize: 11, fontWeight: 600, cursor: "pointer",
  }),
  emptyHint:  { fontSize: 12, color: "#475569", marginTop: 16, textAlign: "center" },
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function WorkflowBuilder({ initialWorkflow, allTasks, scheduleName, onSave, onCancel }) {
  const [nodes, setNodes]           = useState(() => initNodes(initialWorkflow));
  const [selectedId, setSelectedId] = useState(null);

  const selectedNode = nodes.find(n => n.id === selectedId) || null;

  // ── Node operations ──────────────────────────────────────────────────────

  /** Add a new node after the last node */
  const addNode = useCallback((type = "task") => {
    const node = type === "task" ? makeTaskNode() : { id: newId(), type, label: type === "condition" ? "Condition" : "Parallel", description: "" };
    setNodes(prev => [...prev, node]);
    setSelectedId(node.id);
  }, []);

  /** Delete a node by id (trigger node cannot be deleted) */
  const deleteNode = useCallback((id) => {
    setNodes(prev => prev.filter(n => n.id !== id));
    setSelectedId(prev => prev === id ? null : prev);
  }, []);

  /** Update a node's fields */
  const updateNode = useCallback((updated) => {
    setNodes(prev => prev.map(n => n.id === updated.id ? updated : n));
  }, []);

  // ── Save ─────────────────────────────────────────────────────────────────

  const handleSave = useCallback(() => {
    setNodes(currentNodes => {
      // Read latest nodes via functional updater, then call onSave
      onSave({ nodes: currentNodes });
      return currentNodes; // no change, just reading
    });
  }, [onSave]);

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={s.root}>
      {/* Top bar */}
      <div style={s.topBar}>
        <div style={s.topTitle}>
          🔀 Workflow Builder
          {scheduleName && (
            <span style={{ fontSize: 12, color: "#475569", fontWeight: 400, marginLeft: 8 }}>
              — {scheduleName}
            </span>
          )}
        </div>
        <span style={{ fontSize: 11, color: "#475569" }}>{nodes.length} node{nodes.length !== 1 ? "s" : ""}</span>
        <button style={{ ...s.btn, ...s.btnGhost }} onClick={onCancel}>Cancel</button>
        <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleSave}>Save Workflow</button>
      </div>

      <div style={s.body}>
        {/* ── Canvas ── */}
        <div style={s.canvas}>
          {/* Render nodes in order */}
          {nodes.map((node, idx) => (
            <WorkflowNodeCard
              key={node.id}
              node={node}
              isSelected={node.id === selectedId}
              isLast={idx === nodes.length - 1}
              onClick={(n) => setSelectedId(n.id === selectedId ? null : n.id)}
              onDelete={deleteNode}
            />
          ))}

          {/* Add node buttons */}
          <div style={s.addRow}>
            <button style={s.addNodeBtn("#22d3ee")} onClick={() => addNode("task")}>
              + Task
            </button>
            <button style={s.addNodeBtn("#f59e0b")} onClick={() => addNode("condition")}>
              + Condition
            </button>
            <button style={s.addNodeBtn("#a78bfa")} onClick={() => addNode("parallel")}>
              + Parallel
            </button>
          </div>

          {nodes.length === 1 && (
            <div style={s.emptyHint}>
              Add task nodes below the trigger to build your workflow
            </div>
          )}
        </div>

        {/* ── Config Panel ── */}
        <WorkflowConfigPanel
          node={selectedNode}
          allTasks={allTasks}
          onChange={updateNode}
          onClose={() => setSelectedId(null)}
        />
      </div>
    </div>
  );
}
