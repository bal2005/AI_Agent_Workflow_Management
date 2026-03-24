import React, { useState } from "react";

const s = {
  panel: {
    width: 240, minWidth: 240, background: "#13151f", borderRight: "1px solid #1e2130",
    overflowY: "auto", padding: "24px 0", display: "flex", flexDirection: "column",
  },
  header: {
    fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1.2,
    color: "#475569", padding: "0 18px 14px", borderBottom: "1px solid #1e2130", marginBottom: 8,
  },
  domainBlock: { marginBottom: 2 },
  domainRow: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "8px 18px", cursor: "pointer", userSelect: "none",
    transition: "background .1s",
  },
  domainName: { fontSize: 13, fontWeight: 600, color: "#94a3b8" },
  chevron: { fontSize: 9, color: "#475569", transition: "transform .2s", display: "inline-block" },
  agentRow: {
    padding: "6px 18px 6px 30px", cursor: "pointer", fontSize: 13,
    color: "#64748b", transition: "background .1s, color .1s",
  },
  agentRowActive: { background: "#1e2130", color: "#818cf8" },
  empty: { padding: "5px 18px 5px 30px", fontSize: 12, color: "#374151", fontStyle: "italic" },
  noData: { padding: "16px 18px", fontSize: 12, color: "#475569" },
};

export default function SidePanel({ domains, agents, onSelectAgent, selectedAgent }) {
  const [openDomains, setOpenDomains] = useState({});

  const toggle = (id) =>
    setOpenDomains(prev => ({ ...prev, [id]: prev[id] === false ? true : false }));

  const isOpen = (id) => openDomains[id] !== false; // default open

  const agentsByDomain = (domainId) => agents.filter(a => a.domain_id === domainId);

  return (
    <aside style={s.panel}>
      <div style={s.header}>Domains & Agents</div>

      {domains.length === 0 ? (
        <div style={s.noData}>No domains yet. Add one above.</div>
      ) : (
        domains.map(domain => {
          const expanded = isOpen(domain.id);
          const domainAgents = agentsByDomain(domain.id);
          return (
            <div key={domain.id} style={s.domainBlock}>
              <div
                style={{ ...s.domainRow }}
                onClick={() => toggle(domain.id)}
                onMouseEnter={e => e.currentTarget.style.background = "#1a1d2e"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <span style={s.domainName}>{domain.name}</span>
                <span style={{ ...s.chevron, transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}>▶</span>
              </div>

              {expanded && (
                domainAgents.length === 0
                  ? <div style={s.empty}>No agents</div>
                  : domainAgents.map(agent => (
                    <div
                      key={agent.id}
                      style={{ ...s.agentRow, ...(selectedAgent?.id === agent.id ? s.agentRowActive : {}) }}
                      onClick={() => onSelectAgent(agent)}
                      title={agent.system_prompt}
                      onMouseEnter={e => { if (selectedAgent?.id !== agent.id) e.currentTarget.style.background = "#1a1d2e"; }}
                      onMouseLeave={e => { if (selectedAgent?.id !== agent.id) e.currentTarget.style.background = "transparent"; }}
                    >
                      {agent.name}
                    </div>
                  ))
              )}
            </div>
          );
        })
      )}
    </aside>
  );
}
