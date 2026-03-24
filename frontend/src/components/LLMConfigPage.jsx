import React, { useState, useEffect } from "react";
import { fetchLLMConfigs, createLLMConfig, updateLLMConfig, activateLLMConfig, deleteLLMConfig } from "../api";

const PROVIDERS = [
  { id: "ollama",  label: "Ollama",       icon: "🦙", desc: "Local inference, no API key needed",   defaultBase: "http://localhost:11434", defaultModel: "llama3" },
  { id: "openai",  label: "OpenAI",       icon: "🤖", desc: "GPT-4o, GPT-4, GPT-3.5 and more",      defaultBase: "https://api.openai.com/v1", defaultModel: "gpt-4o" },
  { id: "gemini",  label: "Gemini",       icon: "✨", desc: "Google Gemini Pro / Flash",             defaultBase: "https://generativelanguage.googleapis.com/v1beta", defaultModel: "gemini-1.5-pro" },
  { id: "claude",  label: "Claude",       icon: "🧠", desc: "Anthropic Claude 3 Opus / Sonnet",      defaultBase: "https://api.anthropic.com/v1", defaultModel: "claude-3-opus-20240229" },
  { id: "custom",  label: "Custom",       icon: "⚙️", desc: "Any OpenAI-compatible endpoint (BYOK)", defaultBase: "", defaultModel: "" },
];

const s = {
  page: { padding: "32px 40px", color: "#e2e8f0", maxWidth: 900 },
  title: { fontSize: 26, fontWeight: 700, marginBottom: 6, color: "#f8fafc" },
  subtitle: { fontSize: 13, color: "#64748b", marginBottom: 28 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12, marginBottom: 28 },
  card: { borderRadius: 12, border: "2px solid #2d3148", padding: "18px 14px", cursor: "pointer", background: "#1e2130", textAlign: "center", transition: "all .15s" },
  cardActive: { borderColor: "#6366f1", background: "#1e1f3a" },
  cardIcon: { fontSize: 28, marginBottom: 8 },
  cardLabel: { fontSize: 14, fontWeight: 700, color: "#e2e8f0", marginBottom: 4 },
  cardDesc: { fontSize: 11, color: "#64748b", lineHeight: 1.4 },
  form: { background: "#1e2130", borderRadius: 12, padding: "24px 28px", border: "1px solid #2d3148", marginBottom: 24 },
  formTitle: { fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 18 },
  row2: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 },
  row3: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 14 },
  fieldGroup: { marginBottom: 14 },
  label: { fontSize: 13, color: "#94a3b8", marginBottom: 6, display: "block" },
  input: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none", boxSizing: "border-box" },
  inputSmall: { width: "100%", padding: "8px 11px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 13, outline: "none", boxSizing: "border-box" },
  btnRow: { display: "flex", gap: 10, marginTop: 18 },
  btn: { padding: "9px 20px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 14, fontWeight: 600 },
  btnPrimary: { background: "#6366f1", color: "#fff" },
  btnSecondary: { background: "#2d3148", color: "#cbd5e1" },
  btnDanger: { background: "#7f1d1d", color: "#fca5a5" },
  btnActivate: { background: "#14532d", color: "#4ade80" },
  error: { color: "#f87171", fontSize: 12, marginTop: 6 },
  success: { color: "#4ade80", fontSize: 12, marginTop: 6 },
  savedList: { display: "flex", flexDirection: "column", gap: 10 },
  savedCard: { background: "#1e2130", border: "1px solid #2d3148", borderRadius: 10, padding: "14px 18px", display: "flex", alignItems: "center", gap: 14 },
  savedCardActive: { borderColor: "#22c55e" },
  savedInfo: { flex: 1 },
  savedName: { fontSize: 14, fontWeight: 700, color: "#e2e8f0" },
  savedMeta: { fontSize: 12, color: "#64748b", marginTop: 2 },
  pill: { display: "inline-flex", alignItems: "center", padding: "2px 9px", borderRadius: 20, fontSize: 11, fontWeight: 700 },
  pillGreen: { background: "#14532d", color: "#4ade80" },
  pillGray: { background: "#1e293b", color: "#64748b" },
  divider: { borderTop: "1px solid #2d3148", margin: "24px 0" },
  hint: { fontSize: 12, color: "#475569", marginTop: 4 },
};

const emptyForm = { label: "", base_url: "", api_key: "", model_name: "", temperature: "0.7", top_k: "", top_p: "", max_tokens: "" };

export default function LLMConfigPage({ onBack }) {
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchLLMConfigs();
      setConfigs(data);
    } catch (e) {
      console.error("Failed to load LLM configs", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const selectProvider = (p) => {
    setSelectedProvider(p);
    setEditingId(null);
    setForm({ ...emptyForm, label: p.label, base_url: p.defaultBase, model_name: p.defaultModel });
    setFormError(""); setFormSuccess("");
  };

  const handleEdit = (cfg) => {
    const p = PROVIDERS.find(p => p.id === cfg.provider) || PROVIDERS[4];
    setSelectedProvider(p);
    setEditingId(cfg.id);
    setForm({
      label: cfg.label, base_url: cfg.base_url || "", api_key: cfg.api_key || "",
      model_name: cfg.model_name || "", temperature: cfg.temperature ?? "0.7",
      top_k: cfg.top_k ?? "", top_p: cfg.top_p ?? "", max_tokens: cfg.max_tokens ?? "",
    });
    setFormError(""); setFormSuccess("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSave = async () => {
    setFormError(""); setFormSuccess("");
    if (!selectedProvider) { setFormError("Select a provider first"); return; }
    if (!form.label.trim()) { setFormError("Label is required"); return; }
    if (selectedProvider.id !== "ollama" && !form.api_key.trim()) { setFormError("API key is required for this provider"); return; }

    const payload = {
      provider: selectedProvider.id,
      label: form.label.trim(),
      base_url: form.base_url.trim() || null,
      api_key: form.api_key.trim() || null,
      model_name: form.model_name.trim() || null,
      temperature: form.temperature !== "" ? parseFloat(form.temperature) : null,
      top_k: form.top_k !== "" ? parseInt(form.top_k) : null,
      top_p: form.top_p !== "" ? parseFloat(form.top_p) : null,
      max_tokens: form.max_tokens !== "" ? parseInt(form.max_tokens) : null,
    };

    try {
      if (editingId) { await updateLLMConfig(editingId, payload); }
      else { await createLLMConfig(payload); }
      // Load first, then reset form so the list is visible immediately
      await load();
      setFormSuccess(editingId ? "Config updated" : "Config saved");
      setSelectedProvider(null); setForm(emptyForm); setEditingId(null);
    } catch (e) { setFormError(e.response?.data?.detail || "Save failed"); }
  };

  const handleActivate = async (id) => {
    try {
      await activateLLMConfig(id);
      await load();
    } catch (e) { console.error("Activate failed", e); }
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this config?")) return;
    try {
      await deleteLLMConfig(id);
      await load();
    } catch (e) { console.error("Delete failed", e); }
  };

  const f = (key) => (e) => setForm(prev => ({ ...prev, [key]: e.target.value }));

  return (
    <div style={s.page}>
      <div style={{ ...s.row2, gridTemplateColumns: "auto 1fr", alignItems: "center", marginBottom: 0 }}>
        <button style={{ ...s.btn, ...s.btnSecondary, padding: "7px 14px", fontSize: 13 }} onClick={onBack}>← Back</button>
        <div>
          <div style={s.title}>LLM Configuration</div>
          <div style={s.subtitle}>Choose a provider, supply credentials, and set optional parameters. Mark one config as active to use it in the playground.</div>
        </div>
      </div>

      {/* Provider Cards */}
      <div style={{ marginTop: 24, marginBottom: 8, fontSize: 13, fontWeight: 600, color: "#7c85a2", textTransform: "uppercase", letterSpacing: 1 }}>Select Provider</div>
      <div style={s.grid}>
        {PROVIDERS.map(p => (
          <div key={p.id}
            style={{ ...s.card, ...(selectedProvider?.id === p.id ? s.cardActive : {}) }}
            onClick={() => selectProvider(p)}>
            <div style={s.cardIcon}>{p.icon}</div>
            <div style={s.cardLabel}>{p.label}</div>
            <div style={s.cardDesc}>{p.desc}</div>
          </div>
        ))}
      </div>

      {/* Config Form */}
      {selectedProvider && (
        <div style={s.form}>
          <div style={s.formTitle}>{editingId ? "Edit" : "New"} Config — {selectedProvider.label}</div>

          <div style={s.row2}>
            <div>
              <label style={s.label}>Config Label *</label>
              <input style={s.input} placeholder={`My ${selectedProvider.label} Config`} value={form.label} onChange={f("label")} />
            </div>
            <div>
              <label style={s.label}>Model Name</label>
              <input style={s.input} placeholder={selectedProvider.defaultModel} value={form.model_name} onChange={f("model_name")} />
            </div>
          </div>

          <div style={s.fieldGroup}>
            <label style={s.label}>Base URL</label>
            <input style={s.input} placeholder={selectedProvider.defaultBase} value={form.base_url} onChange={f("base_url")} />
            <div style={s.hint}>Leave blank to use the default endpoint for this provider.</div>
          </div>

          {selectedProvider.id !== "ollama" && (
            <div style={s.fieldGroup}>
              <label style={s.label}>API Key *</label>
              <input style={s.input} type="password" placeholder="sk-..." value={form.api_key} onChange={f("api_key")} />
              <div style={s.hint}>Used as Bearer token via BYOK. Stored in your database — use env vars in production.</div>
            </div>
          )}

          <div style={{ marginTop: 8, marginBottom: 10, fontSize: 13, fontWeight: 600, color: "#7c85a2", textTransform: "uppercase", letterSpacing: 1 }}>Optional Parameters</div>
          <div style={s.row3}>
            <div>
              <label style={s.label}>Temperature</label>
              <input style={s.inputSmall} type="number" min="0" max="2" step="0.1" placeholder="0.7" value={form.temperature} onChange={f("temperature")} />
            </div>
            <div>
              <label style={s.label}>Top-K</label>
              <input style={s.inputSmall} type="number" min="1" placeholder="e.g. 40" value={form.top_k} onChange={f("top_k")} />
            </div>
            <div>
              <label style={s.label}>Top-P</label>
              <input style={s.inputSmall} type="number" min="0" max="1" step="0.05" placeholder="e.g. 0.9" value={form.top_p} onChange={f("top_p")} />
            </div>
          </div>
          <div style={{ maxWidth: 200 }}>
            <label style={s.label}>Max Tokens</label>
            <input style={s.inputSmall} type="number" min="1" placeholder="e.g. 2048" value={form.max_tokens} onChange={f("max_tokens")} />
          </div>

          {formError && <div style={s.error}>{formError}</div>}
          {formSuccess && <div style={s.success}>{formSuccess}</div>}

          <div style={s.btnRow}>
            <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleSave}>{editingId ? "Update Config" : "Save Config"}</button>
            <button style={{ ...s.btn, ...s.btnSecondary }} onClick={() => { setSelectedProvider(null); setEditingId(null); setForm(emptyForm); }}>Cancel</button>
          </div>
        </div>
      )}

      {/* Saved Configs */}
      <div style={s.divider} />
      <div style={{ fontSize: 13, fontWeight: 600, color: "#7c85a2", textTransform: "uppercase", letterSpacing: 1, marginBottom: 14 }}>
        Saved Configs
      </div>
      {loading ? (
        <div style={{ color: "#475569", fontSize: 13 }}>Loading...</div>
      ) : configs.length === 0 ? (
        <div style={{ color: "#475569", fontSize: 13 }}>No configs saved yet. Select a provider above to create one.</div>
      ) : (
        <div style={s.savedList}>
          {configs.map(cfg => {
            const p = PROVIDERS.find(p => p.id === cfg.provider);
            return (
              <div key={cfg.id} style={{ ...s.savedCard, ...(cfg.is_active ? s.savedCardActive : {}) }}>
                <span style={{ fontSize: 22 }}>{p?.icon || "⚙️"}</span>
                <div style={s.savedInfo}>
                  <div style={s.savedName}>{cfg.label}</div>
                  <div style={s.savedMeta}>{cfg.provider} · {cfg.model_name || "default model"} · temp {cfg.temperature ?? "—"}</div>
                </div>
                <span style={{ ...s.pill, ...(cfg.is_active ? s.pillGreen : s.pillGray) }}>
                  {cfg.is_active ? "● Active" : "Inactive"}
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  {!cfg.is_active && (
                    <button style={{ ...s.btn, ...s.btnActivate, padding: "6px 14px", fontSize: 12 }} onClick={() => handleActivate(cfg.id)}>Set Active</button>
                  )}
                  <button style={{ ...s.btn, ...s.btnSecondary, padding: "6px 14px", fontSize: 12 }} onClick={() => handleEdit(cfg)}>Edit</button>
                  <button style={{ ...s.btn, ...s.btnDanger, padding: "6px 14px", fontSize: 12 }} onClick={() => handleDelete(cfg.id)}>Delete</button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
