import React, { useState, useEffect } from "react";
import {
  fetchDomains, fetchAgents,
  updateAgent, deleteAgent,
  updateDomain, createDomain,
} from "../api";

const s = {
  layout: { display: "flex", flex: 1, overflow: "hidden", background: "#0f1117", color: "#e2e8f0", fontFamily: "Inter, sans-serif" },
  left: { width: 280, minWidth: 280, background: "#13151f", borderRight: "1px solid #1e2130", display: "flex", flexDirection: "column", overflowY: "auto" },
  leftHeader: { padding: "20px 18px 14px", borderBottom: "1px solid #1e2130" },
  leftTitle: { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1.2, color: "#475569", marginBottom: 4 },
  searchInput: { width: "100%", padding: "7px 11px", borderRadius: 7, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 13, outline: "none", boxSizing: "border-box", marginTop: 10 },
  domainBlock: { borderBottom: "1px solid #1a1d2e" },
  domainRow: (active) => ({
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "10px 18px", cursor: "pointer", fontSize: 13, fontWeight: 600,
    color: active ? "#818cf8" : "#94a3b8",
    background: active ? "#1e2130" : "transparent",
    borderLeft: `3px solid ${active ? "#6366f1" : "transparent"}`,
  }),
  agentRow: (active) => ({
    padding: "8px 18px 8px 32px", cursor: "pointer", fontSize: 13,
    color: active ? "#818cf8" : "#64748b",
    background: active ? "#1e2130" : "transparent",
    borderLeft: `3px solid ${active ? "#6366f1" : "transparent"}`,
    display: "flex", alignItems: "center", justifyContent: "space-between",
  }),
  badge: (color) => ({
    fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 4,
    background: color === "warn" ? "#451a03" : "#1a2e1a",
    color: color === "warn" ? "#fb923c" : "#4ade80",
  }),
  right: { flex: 1, overflowY: "auto", padding: "32px 40px", maxWidth: 820 },
  section: { background: "#1e2130", borderRadius: 12, padding: "22px 26px", marginBottom: 18, border: "1px solid #2d3148" },
  sectionTitle: { fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 16 },
  label: { fontSize: 13, color: "#94a3b8", marginBottom: 6, display: "block" },
  input: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none", boxSizing: "border-box" },
  textarea: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none", resize: "vertical", boxSizing: "border-box", fontFamily: "inherit" },
  select: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none" },
  fieldGroup: { marginBottom: 16 },
  row: { display: "flex", gap: 10, alignItems: "center" },
  btn: { padding: "9px 20px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 14, fontWeight: 600 },
  btnPrimary: { background: "#6366f1", color: "#fff" },
  btnDanger: { background: "#7f1d1d", color: "#fca5a5" },
  btnSecondary: { background: "#2d3148", color: "#cbd5e1" },
  error: { color: "#f87171", fontSize: 12, marginTop: 4 },
  success: { color: "#4ade80", fontSize: 12, marginTop: 4 },
  warn: { color: "#fb923c", fontSize: 12, marginTop: 4 },
  emptyState: { padding: "60px 40px", textAlign: "center", color: "#475569", fontSize: 14 },
  statCard: { background: "#0f1117", borderRadius: 8, padding: "14px 18px", border: "1px solid #2d3148", flex: 1 },
  statNum: { fontSize: 28, fontWeight: 700, color: "#818cf8" },
  statLabel: { fontSize: 12, color: "#475569", marginTop: 2 },
};

export default function AdminPanel({ onRefresh }) {
  const [domains, setDomains] = useState([]);
  const [agents, setAgents] = useState([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null); // { type: "agent"|"domain", data }
  const [openDomains, setOpenDomains] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState({ type: "", text: "" });

  // edit form state
  const [form, setForm] = useState({});

  const load = async () => {
    const [d, a] = await Promise.all([
      fetchDomains().catch(() => []),
      fetchAgents().catch(() => []),
    ]);
    setDomains(d);
    setAgents(a);
    const open = {};
    d.forEach(dom => { open[dom.id] = true; });
    setOpenDomains(open);
  };

  useEffect(() => { load(); }, []);

  const selectAgent = (agent) => {
    setSelected({ type: "agent", data: agent });
    setForm({
      name: agent.name,
      system_prompt: agent.system_prompt,
      domain_id: String(agent.domain_id),
    });
    setMsg({ type: "", text: "" });
  };

  const selectDomain = (domain) => {
    setSelected({ type: "domain", data: domain });
    setForm({
      name: domain.name,
      domain_prompt: domain.domain_prompt || "",
    });
    setMsg({ type: "", text: "" });
  };

  const f = (key) => (e) => {
    setForm(prev => ({ ...prev, [key]: e.target.value }));
    setMsg({ type: "", text: "" });
  };

  const agentsForDomain = (domainId) => agents.filter(a => a.domain_id === domainId);

  const filteredDomains = domains.filter(d => {
    const q = search.toLowerCase();
    if (!q) return true;
    if (d.name.toLowerCase().includes(q)) return true;
    return agentsForDomain(d.id).some(a => a.name.toLowerCase().includes(q));
  });

  const domainHasPrompt = (domainId) => {
    const d = domains.find(x => x.id === domainId);
    return !!(d?.domain_prompt?.trim());
  };

  // Stats
  const totalAgents = agents.length;
  const missingPrompt = domains.filter(d => !d.domain_prompt?.trim()).length;
  const agentsMissingDomainPrompt = agents.filter(a => !domainHasPrompt(a.domain_id)).length;

  // ── Save agent ──
  const handleSaveAgent = async () => {
    if (!form.name?.trim()) { setMsg({ type: "error", text: "Name is required" }); return; }
    if (!form.system_prompt?.trim()) { setMsg({ type: "error", text: "System prompt is required" }); return; }
    setSaving(true);
    try {
      const updated = await updateAgent(selected.data.id, {
        name: form.name.trim(),
        system_prompt: form.system_prompt.trim(),
        domain_id: Number(form.domain_id),
      });
      setMsg({ type: "success", text: "Agent updated" });
      setSelected({ type: "agent", data: updated });
      await load();
    } catch (e) {
      setMsg({ type: "error", text: e.response?.data?.detail || "Update failed" });
    } finally { setSaving(false); }
  };

  // ── Delete agent ──
  const handleDeleteAgent = async () => {
    if (!confirm(`Delete agent "${selected.data.name}"? This cannot be undone.`)) return;
    try {
      await deleteAgent(selected.data.id);
      setSelected(null);
      setMsg({ type: "", text: "" });
      await load();
    } catch (e) {
      setMsg({ type: "error", text: e.response?.data?.detail || "Delete failed" });
    }
  };

  // ── Save domain ──
  const handleSaveDomain = async () => {
    if (!form.name?.trim()) { setMsg({ type: "error", text: "Domain name is required" }); return; }
    setSaving(true);
    try {
      const updated = await updateDomain(selected.data.id, {
        name: form.name.trim(),
        domain_prompt: form.domain_prompt?.trim() || null,
      });
      setMsg({ type: "success", text: "Domain updated" });
      setSelected({ type: "domain", data: updated });
      await load();
      if (onRefresh) onRefresh();
    } catch (e) {
      setMsg({ type: "error", text: e.response?.data?.detail || "Update failed" });
    } finally { setSaving(false); }
  };

  return (
    <div style={s.layout}>
      {/* ── Left panel ── */}
      <aside style={s.left}>
        <div style={s.leftHeader}>
          <div style={s.leftTitle}>Admin Panel</div>
          <div style={{ fontSize: 12, color: "#475569" }}>Manage agents &amp; domains</div>
          <input
            style={s.searchInput}
            placeholder="Search agents or domains..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <div style={{ flex: 1 }}>
          {filteredDomains.map(domain => {
            const domAgents = agentsForDomain(domain.id).filter(a =>
              !search || a.name.toLowerCase().includes(search.toLowerCase()) || domain.name.toLowerCase().includes(search.toLowerCase())
            );
            const hasPrompt = !!(domain.domain_prompt?.trim());
            const isOpen = openDomains[domain.id] !== false;
            const isDomainSelected = selected?.type === "domain" && selected.data.id === domain.id;

            return (
              <div key={domain.id} style={s.domainBlock}>
                <div
                  style={s.domainRow(isDomainSelected)}
                  onClick={() => selectDomain(domain)}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{ fontSize: 10, color: "#475569", cursor: "pointer", marginRight: 2 }}
                      onClick={e => { e.stopPropagation(); setOpenDomains(p => ({ ...p, [domain.id]: !isOpen })); }}
                    >
                      {isOpen ? "▼" : "▶"}
                    </span>
                    📁 {domain.name}
                  </span>
                  <span style={s.badge(hasPrompt ? "ok" : "warn")}>
                    {hasPrompt ? "✓ prompt" : "⚠ no prompt"}
                  </span>
                </div>

                {isOpen && domAgents.map(agent => {
                  const isAgentSelected = selected?.type === "agent" && selected.data.id === agent.id;
                  return (
                    <div
                      key={agent.id}
                      style={s.agentRow(isAgentSelected)}
                      onClick={() => selectAgent(agent)}
                    >
                      <span>🤖 {agent.name}</span>
                      {!hasPrompt && <span style={s.badge("warn")}>⚠</span>}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </aside>

      {/* ── Right panel ── */}
      <div style={s.right}>
        {/* Stats row */}
        <div style={{ display: "flex", gap: 14, marginBottom: 24 }}>
          <div style={s.statCard}>
            <div style={s.statNum}>{domains.length}</div>
            <div style={s.statLabel}>Domains</div>
          </div>
          <div style={s.statCard}>
            <div style={s.statNum}>{totalAgents}</div>
            <div style={s.statLabel}>Agents</div>
          </div>
          <div style={{ ...s.statCard, borderColor: missingPrompt > 0 ? "#7c2d12" : "#2d3148" }}>
            <div style={{ ...s.statNum, color: missingPrompt > 0 ? "#fb923c" : "#4ade80" }}>{missingPrompt}</div>
            <div style={s.statLabel}>Domains missing prompt</div>
          </div>
          <div style={{ ...s.statCard, borderColor: agentsMissingDomainPrompt > 0 ? "#7c2d12" : "#2d3148" }}>
            <div style={{ ...s.statNum, color: agentsMissingDomainPrompt > 0 ? "#fb923c" : "#4ade80" }}>{agentsMissingDomainPrompt}</div>
            <div style={s.statLabel}>Agents without domain prompt</div>
          </div>
        </div>

        {!selected && (
          <div style={s.emptyState}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>🛠</div>
            <div>Select a domain or agent from the left panel to edit it.</div>
            {missingPrompt > 0 && (
              <div style={{ ...s.warn, marginTop: 16, fontSize: 13 }}>
                ⚠ {missingPrompt} domain(s) are missing a domain prompt. Agents in those domains won't have context injected at runtime.
              </div>
            )}
          </div>
        )}

        {/* ── Edit Domain ── */}
        {selected?.type === "domain" && (
          <>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#f8fafc", marginBottom: 4 }}>
              Edit Domain
            </div>
            <div style={{ fontSize: 13, color: "#64748b", marginBottom: 20 }}>
              {agentsForDomain(selected.data.id).length} agent(s) in this domain
            </div>

            <div style={s.section}>
              <div style={s.sectionTitle}>Domain Details</div>

              <div style={s.fieldGroup}>
                <label style={s.label}>Domain Name</label>
                <input style={s.input} value={form.name || ""} onChange={f("name")} />
              </div>

              <div style={s.fieldGroup}>
                <label style={s.label}>
                  Domain Prompt
                  {!form.domain_prompt?.trim() && (
                    <span style={{ color: "#fb923c", marginLeft: 8, fontSize: 11, fontWeight: 700 }}>
                      ⚠ REQUIRED — agents in this domain won't have context without this
                    </span>
                  )}
                </label>
                <textarea
                  style={{ ...s.textarea, minHeight: 140, borderColor: !form.domain_prompt?.trim() ? "#7c2d12" : "#2d3148" }}
                  placeholder="Enter reusable domain-level instructions/context for all agents in this domain..."
                  value={form.domain_prompt || ""}
                  onChange={f("domain_prompt")}
                />
                <div style={{ fontSize: 12, color: "#475569", marginTop: 4 }}>
                  This is prepended before every agent prompt at runtime. Keep it concise.
                </div>
              </div>

              {msg.text && <div style={s[msg.type]}>{msg.text}</div>}

              <div style={{ ...s.row, marginTop: 8 }}>
                <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleSaveDomain} disabled={saving}>
                  {saving ? "Saving..." : "Save Domain"}
                </button>
              </div>
            </div>

            {/* Agents in this domain */}
            <div style={s.section}>
              <div style={s.sectionTitle}>Agents in this domain</div>
              {agentsForDomain(selected.data.id).length === 0 ? (
                <div style={{ fontSize: 13, color: "#475569" }}>No agents yet.</div>
              ) : agentsForDomain(selected.data.id).map(agent => (
                <div
                  key={agent.id}
                  style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid #1a1d2e" }}
                >
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "#e2e8f0" }}>🤖 {agent.name}</div>
                    <div style={{ fontSize: 12, color: "#475569", marginTop: 2 }}>
                      {agent.system_prompt.slice(0, 80)}{agent.system_prompt.length > 80 ? "..." : ""}
                    </div>
                  </div>
                  <button
                    style={{ ...s.btn, ...s.btnSecondary, fontSize: 12, padding: "6px 14px" }}
                    onClick={() => selectAgent(agent)}
                  >
                    Edit
                  </button>
                </div>
              ))}
            </div>
          </>
        )}

        {/* ── Edit Agent ── */}
        {selected?.type === "agent" && (
          <>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#f8fafc", marginBottom: 4 }}>
              Edit Agent
            </div>
            <div style={{ fontSize: 13, color: "#64748b", marginBottom: 20 }}>
              ID: {selected.data.id} · Created: {new Date(selected.data.created_at).toLocaleDateString()}
            </div>

            {!domainHasPrompt(selected.data.domain_id) && (
              <div style={{ background: "#451a03", border: "1px solid #7c2d12", borderRadius: 8, padding: "12px 16px", marginBottom: 16, fontSize: 13, color: "#fb923c" }}>
                ⚠ This agent's domain has no domain prompt set. Go to the domain to add one — it's required for proper context injection at runtime.
              </div>
            )}

            <div style={s.section}>
              <div style={s.sectionTitle}>Agent Details</div>

              <div style={s.fieldGroup}>
                <label style={s.label}>Agent Name</label>
                <input style={s.input} value={form.name || ""} onChange={f("name")} />
              </div>

              <div style={s.fieldGroup}>
                <label style={s.label}>Domain</label>
                <select style={s.select} value={form.domain_id || ""} onChange={f("domain_id")}>
                  {domains.map(d => (
                    <option key={d.id} value={d.id}>
                      {d.name}{!d.domain_prompt?.trim() ? " ⚠ no prompt" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div style={s.fieldGroup}>
                <label style={s.label}>System Prompt (Skill)</label>
                <textarea
                  style={{ ...s.textarea, minHeight: 200 }}
                  value={form.system_prompt || ""}
                  onChange={f("system_prompt")}
                />
              </div>

              {msg.text && <div style={s[msg.type]}>{msg.text}</div>}

              <div style={{ ...s.row, marginTop: 8 }}>
                <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleSaveAgent} disabled={saving}>
                  {saving ? "Saving..." : "Save Agent"}
                </button>
                <button style={{ ...s.btn, ...s.btnDanger }} onClick={handleDeleteAgent}>
                  Delete Agent
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
