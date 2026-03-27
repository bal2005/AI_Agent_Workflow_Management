/**
 * WorkflowNodeCard
 * ─────────────────
 * A single node in the workflow canvas.
 * Supports: trigger, task, condition (placeholder), parallel (placeholder)
 */
import React from "react";

// Node type visual config
const NODE_TYPE_META = {
  trigger:   { icon: "⚡", color: "#6366f1", bg: "#1e1f3a", border: "#4f46e5", label: "Trigger" },
  task:      { icon: "⚙", color: "#22d3ee", bg: "#0e2a30", border: "#0891b2", label: "Task" },
  condition: { icon: "◇", color: "#f59e0b", bg: "#2a1f0e", border: "#d97706", label: "Condition" },
  parallel:  { icon: "⫸", color: "#a78bfa", bg: "#1e1a2e", border: "#7c3aed", label: "Parallel" },
};

export default function WorkflowNodeCard({ node, isSelected, onClick, onDelete, isLast }) {
  const meta = NODE_TYPE_META[node.type] || NODE_TYPE_META.task;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      {/* Node card */}
      <div
        onClick={() => onClick(node)}
        style={{
          width: 200,
          background: meta.bg,
          border: `2px solid ${isSelected ? "#f1f5f9" : meta.border}`,
          borderRadius: 12,
          padding: "12px 16px",
          cursor: "pointer",
          position: "relative",
          boxShadow: isSelected ? `0 0 0 3px ${meta.color}44` : "0 2px 8px rgba(0,0,0,0.4)",
          transition: "all .15s",
          userSelect: "none",
        }}
      >
        {/* Type badge */}
        <div style={{
          position: "absolute", top: -10, left: 12,
          background: meta.color, color: "#fff",
          fontSize: 9, fontWeight: 700, padding: "2px 7px",
          borderRadius: 6, textTransform: "uppercase", letterSpacing: 0.8,
        }}>
          {meta.label}
        </div>

        {/* Delete button — hidden for trigger node */}
        {node.type !== "trigger" && (
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(node.id); }}
            style={{
              position: "absolute", top: 6, right: 8,
              background: "none", border: "none", color: "#475569",
              cursor: "pointer", fontSize: 13, lineHeight: 1, padding: 2,
            }}
            title="Remove node"
          >✕</button>
        )}

        {/* Icon + name */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
          <span style={{ fontSize: 20 }}>{meta.icon}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 13, fontWeight: 700, color: "#f1f5f9",
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
            }}>
              {node.label || "Untitled"}
            </div>
            {node.description && (
              <div style={{
                fontSize: 10, color: "#64748b", marginTop: 2,
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }}>
                {node.description}
              </div>
            )}
          </div>
        </div>

        {/* Task reference badge */}
        {node.taskId && (
          <div style={{
            marginTop: 8, padding: "3px 8px", background: "#0f1117",
            borderRadius: 6, fontSize: 10, color: "#475569",
            border: "1px solid #2d3148",
          }}>
            🔗 Task linked
          </div>
        )}

        {/* Placeholder badge for condition/parallel */}
        {(node.type === "condition" || node.type === "parallel") && (
          <div style={{
            marginTop: 8, padding: "3px 8px", background: "#1a1200",
            borderRadius: 6, fontSize: 10, color: "#92400e",
            border: "1px solid #78350f",
          }}>
            ⚠ Coming soon
          </div>
        )}
      </div>

      {/* Connector arrow — shown between nodes, not after the last */}
      {!isLast && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", margin: "4px 0" }}>
          <div style={{ width: 2, height: 16, background: "#2d3148" }} />
          <div style={{
            width: 0, height: 0,
            borderLeft: "6px solid transparent",
            borderRight: "6px solid transparent",
            borderTop: "8px solid #2d3148",
          }} />
        </div>
      )}
    </div>
  );
}
