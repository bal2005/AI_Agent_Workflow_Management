import React, { useState, useEffect, useRef } from "react";
import { createDomain, createAgent, checkAgentName, runPlayground } from "../api";

const s = {
  page: { padding: "32px 40px", color: "#e2e8f0", maxWidth: 860 },
  title: { fontSize: 26, fontWeight: 700, marginBottom: 28, color: "#f8fafc" },
  section: { background: "#1e2130", borderRadius: 12, padding: "24px 28px", marginBottom: 20, border: "1px solid #2d3148" },
  sectionTitle: { fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: 1, color: "#7c85a2", marginBottom: 16 },
  row: { display: "flex", gap: 10, alignItems: "flex-start" },
  label: { fontSize: 13, color: "#94a3b8", marginBottom: 6, display: "block" },
  input: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none", boxSizing: "border-box" },
  inputError: { borderColor: "#f87171" },
  textarea: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none", resize: "vertical", minHeight: 110, boxSizing: "border-box", fontFamily: "inherit" },
  select: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 14, outline: "none" },
  btn: { padding: "9px 20px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 14, fontWeight: 600, transition: "opacity .15s" },
  btnPrimary: { background: "#6366f1", color: "#fff" },
  btnSecondary: { background: "#2d3148", color: "#cbd5e1" },
  btnSuccess: { background: "#22c55e", color: "#fff" },
  error: { color: "#f87171", fontSize: 12, marginTop: 4 },
  success: { color: "#4ade80", fontSize: 12, marginTop: 4 },
  info: { color: "#60a5fa", fontSize: 12, marginTop: 4 },
  resultBox: { width: "100%", padding: "9px 13px", borderRadius: 8, border: "1px solid #2d3148", background: "#0a0c14", color: "#a3e635", fontSize: 13, minHeight: 120, whiteSpace: "pre-wrap", fontFamily: "monospace", boxSizing: "border-box" },
  fieldGroup: { marginBottom: 16 },
  tabRow: { display: "flex", gap: 0, marginBottom: 12, borderRadius: 8, overflow: "hidden", border: "1px solid #2d3148", width: "fit-content" },
  tab: { padding: "7px 18px", fontSize: 13, fontWeight: 600, cursor: "pointer", border: "none", background: "#0f1117", color: "#64748b", transition: "all .15s" },
  tabActive: { background: "#6366f1", color: "#fff" },
  uploadBox: { border: "2px dashed #2d3148", borderRadius: 8, padding: "20px", textAlign: "center", cursor: "pointer", color: "#64748b", fontSize: 13, background: "#0f1117" },
  uploadBoxActive: { borderColor: "#6366f1", color: "#818cf8" },
  pill: { display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600 },
  pillGreen: { background: "#14532d", color: "#4ade80" },
  pillRed: { background: "#450a0a", color: "#f87171" },
  pillBlue: { background: "#1e3a5f", color: "#60a5fa" },
};

function useDebounce(value, delay) {
  const [d, setD] = useState(value);
  useEffect(() => { const t = setTimeout(() => setD(value), delay); return () => clearTimeout(t); }, [value, delay]);
  return d;
}

export default function AgentCreationPage({ domains, onRefresh, prefillAgent, onClearPrefill, onOpenLLMConfig, activeLLMConfig }) {
  const [newDomain, setNewDomain] = useState("");
  const [domainError, setDomainError] = useState("");
  const [domainSuccess, setDomainSuccess] = useState("");

  const [selectedDomainId, setSelectedDomainId] = useState("");
  const [agentName, setAgentName] = useState("");
  const [promptMode, setPromptMode] = useState("text"); // "text" | "file"
  const [systemPrompt, setSystemPrompt] = useState("");
  const [mdFile, setMdFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef();

  const [formErrors, setFormErrors] = useState({});
  const [nameExists, setNameExists] = useState(null); // null=unchecked, true/false
  const [nameChecking, setNameChecking] = useState(false);

  const [userPrompt, setUserPrompt] = useState("");
  const [playgroundResult, setPlaygroundResult] = useState("");
  const [playgroundEngine, setPlaygroundEngine] = useState(null); // "copilot-sdk" | "direct" | null
  const [playgroundLoading, setPlaygroundLoading] = useState(false);

  const [submitError, setSubmitError] = useState("");
  const [submitSuccess, setSubmitSuccess] = useState("");

  const debouncedName = useDebounce(agentName, 500);

  useEffect(() => {
    if (prefillAgent) {
      setAgentName(prefillAgent.name);
      setSystemPrompt(prefillAgent.system_prompt);
      setSelectedDomainId(String(prefillAgent.domain_id));
      setPromptMode("text");
      setMdFile(null);
      setFormErrors({});
      setNameExists(null);
      setSubmitError(""); setSubmitSuccess("");
    }
  }, [prefillAgent]);

  useEffect(() => {
    if (!debouncedName.trim()) { setNameExists(null); return; }
    if (prefillAgent && debouncedName === prefillAgent.name) { setNameExists(null); return; }
    setNameChecking(true);
    checkAgentName(debouncedName.trim())
      .then(({ exists }) => setNameExists(exists))
      .finally(() => setNameChecking(false));
  }, [debouncedName, prefillAgent]);

  const handleAddDomain = async () => {
    setDomainError(""); setDomainSuccess("");
    if (!newDomain.trim()) { setDomainError("Domain name is required"); return; }
    try {
      await createDomain(newDomain.trim());
      setNewDomain(""); setDomainSuccess("Domain added");
      onRefresh();
    } catch (e) { setDomainError(e.response?.data?.detail || "Failed to add domain"); }
  };

  const handleFileDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith(".md")) setMdFile(file);
    else setFormErrors(f => ({ ...f, mdFile: "Only .md files accepted" }));
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && file.name.endsWith(".md")) { setMdFile(file); setFormErrors(f => ({ ...f, mdFile: "" })); }
    else setFormErrors(f => ({ ...f, mdFile: "Only .md files accepted" }));
  };

  const validate = () => {
    const errors = {};
    if (!selectedDomainId) errors.domain = "Please select a domain";
    if (!agentName.trim()) errors.name = "Agent name is required";
    if (nameExists === true) errors.name = "Agent name already exists";
    if (promptMode === "text" && !systemPrompt.trim()) errors.systemPrompt = "System prompt is required";
    if (promptMode === "file" && !mdFile) errors.mdFile = "Please upload a .md file";
    return errors;
  };

  const handleTest = async () => {
    // Resolve the effective system prompt
    let effectivePrompt = systemPrompt;
    if (promptMode === "file" && mdFile) {
      // Read the md file content client-side for playground preview
      effectivePrompt = await mdFile.text();
    }
    if (!effectivePrompt.trim()) {
      setFormErrors(f => ({ ...f, systemPrompt: "System prompt is required to test" }));
      return;
    }
    if (!userPrompt.trim()) {
      setFormErrors(f => ({ ...f, userPrompt: "User prompt is required" }));
      return;
    }
    setPlaygroundLoading(true); setPlaygroundResult(""); setPlaygroundEngine(null);
    try {
      const data = await runPlayground(effectivePrompt, userPrompt, activeLLMConfig?.id || null);
      setPlaygroundResult(data.result);
      setPlaygroundEngine(data.engine || "direct");
    } catch (e) {
      setPlaygroundResult(`Error: ${e.response?.data?.detail || e.message}`);
      setPlaygroundEngine(null);
    } finally {
      setPlaygroundLoading(false);
    }
  };

  const handleCreate = async () => {
    setSubmitError(""); setSubmitSuccess("");
    const errors = validate();
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const fd = new FormData();
    fd.append("name", agentName.trim());
    fd.append("domain_id", selectedDomainId);
    if (promptMode === "text") fd.append("skill", systemPrompt.trim());
    if (promptMode === "file" && mdFile) fd.append("md_file", mdFile);

    try {
      await createAgent(fd);
      setSubmitSuccess(`Agent "${agentName}" created`);
      setAgentName(""); setSystemPrompt(""); setSelectedDomainId(""); setMdFile(null);
      setUserPrompt(""); setPlaygroundResult(""); setNameExists(null);
      onClearPrefill(); onRefresh();
    } catch (e) { setSubmitError(e.response?.data?.detail || "Failed to create agent"); }
  };

  const nameStatus = () => {
    if (!agentName.trim()) return null;
    if (nameChecking) return <span style={{ ...s.pill, ...s.pillBlue }}>checking...</span>;
    if (nameExists === true) return <span style={{ ...s.pill, ...s.pillRed }}>✗ Name taken</span>;
    if (nameExists === false) return <span style={{ ...s.pill, ...s.pillGreen }}>✓ Available</span>;
    return null;
  };

  return (
    <div style={s.page}>
      <div style={s.title}>Agent Studio</div>

      {/* Add Domain */}
      <div style={s.section}>
        <div style={s.sectionTitle}>Add Domain</div>
        <div style={s.row}>
          <div style={{ flex: 1 }}>
            <input style={{ ...s.input, ...(domainError ? s.inputError : {}) }} placeholder="e.g. Customer Support"
              value={newDomain} onChange={e => { setNewDomain(e.target.value); setDomainError(""); setDomainSuccess(""); }}
              onKeyDown={e => e.key === "Enter" && handleAddDomain()} />
            {domainError && <div style={s.error}>{domainError}</div>}
            {domainSuccess && <div style={s.success}>{domainSuccess}</div>}
          </div>
          <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleAddDomain}>Add Domain</button>
        </div>
      </div>

      {/* Agent Config */}
      <div style={s.section}>
        <div style={s.sectionTitle}>Agent Configuration</div>

        <div style={s.fieldGroup}>
          <label style={s.label}>Domain</label>
          <select style={{ ...s.select, ...(formErrors.domain ? s.inputError : {}) }}
            value={selectedDomainId} onChange={e => { setSelectedDomainId(e.target.value); setFormErrors(f => ({ ...f, domain: "" })); }}>
            <option value="">-- Select a domain --</option>
            {domains.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          {formErrors.domain && <div style={s.error}>{formErrors.domain}</div>}
        </div>

        <div style={s.fieldGroup}>
          <label style={s.label}>Agent Name</label>
          <div style={{ ...s.row, alignItems: "center", gap: 10 }}>
            <input style={{ ...s.input, ...(formErrors.name ? s.inputError : {}) }} placeholder="e.g. Support Bot"
              value={agentName} onChange={e => { setAgentName(e.target.value); setFormErrors(f => ({ ...f, name: "" })); }} />
            <div style={{ minWidth: 110 }}>{nameStatus()}</div>
          </div>
          {formErrors.name && <div style={s.error}>{formErrors.name}</div>}
        </div>

        {/* Skill — text or file */}
        <div style={s.fieldGroup}>
          <div style={{ ...s.row, alignItems: "center", marginBottom: 10 }}>
            <label style={{ ...s.label, marginBottom: 0, flex: 1 }}>Skill</label>
            <div style={s.tabRow}>
              <button style={{ ...s.tab, ...(promptMode === "text" ? s.tabActive : {}) }} onClick={() => setPromptMode("text")}>Text</button>
              <button style={{ ...s.tab, ...(promptMode === "file" ? s.tabActive : {}) }} onClick={() => setPromptMode("file")}>Upload .md</button>
            </div>
          </div>

          {promptMode === "text" ? (
            <>
              <textarea style={{ ...s.textarea, ...(formErrors.systemPrompt ? s.inputError : {}) }}
                placeholder="Describe what this agent can do and how it should behave..."
                value={systemPrompt} onChange={e => { setSystemPrompt(e.target.value); setFormErrors(f => ({ ...f, systemPrompt: "" })); }} />
              {formErrors.systemPrompt && <div style={s.error}>{formErrors.systemPrompt}</div>}
            </>
          ) : (
            <>
              <div
                style={{ ...s.uploadBox, ...(dragOver ? s.uploadBoxActive : {}), ...(formErrors.mdFile ? { borderColor: "#f87171" } : {}) }}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current.click()}
              >
                {mdFile
                  ? <span style={{ color: "#4ade80" }}>📄 {mdFile.name}</span>
                  : <span>Drag & drop a <strong>.md</strong> file here, or click to browse</span>}
              </div>
              <input ref={fileInputRef} type="file" accept=".md" style={{ display: "none" }} onChange={handleFileSelect} />
              {mdFile && (
                <div style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ ...s.pill, ...s.pillGreen }}>✓ {mdFile.name}</span>
                  <button style={{ ...s.btn, ...s.btnSecondary, padding: "3px 10px", fontSize: 12 }} onClick={() => setMdFile(null)}>Remove</button>
                </div>
              )}
              {formErrors.mdFile && <div style={s.error}>{formErrors.mdFile}</div>}
            </>
          )}
        </div>

        <button style={{ ...s.btn, ...s.btnSecondary }} onClick={() => alert("Default Settings — coming soon")}>
          Default Settings
        </button>
      </div>

      {/* Playground */}
      <div style={s.section}>
        <div style={{ ...s.row, alignItems: "center", marginBottom: 16 }}>
          <div style={{ ...s.sectionTitle, marginBottom: 0, flex: 1 }}>User Playground</div>
          {activeLLMConfig ? (
            <span style={{ ...s.pill, ...s.pillGreen, fontSize: 11 }}>⚡ {activeLLMConfig.label}</span>
          ) : (
            <span style={{ ...s.pill, ...s.pillRed, fontSize: 11 }}>⚠ No active LLM</span>
          )}
        </div>

        <div style={s.fieldGroup}>
          <label style={s.label}>User Prompt</label>
          <textarea style={{ ...s.textarea, ...(formErrors.userPrompt ? s.inputError : {}) }}
            placeholder="Type a test message..."
            value={userPrompt} onChange={e => { setUserPrompt(e.target.value); setFormErrors(f => ({ ...f, userPrompt: "" })); }} />
          {formErrors.userPrompt && <div style={s.error}>{formErrors.userPrompt}</div>}
        </div>

        <div style={s.fieldGroup}>
          <div style={{ ...s.row, alignItems: "center", marginBottom: 6 }}>
            <label style={{ ...s.label, marginBottom: 0, flex: 1 }}>Result</label>
            {playgroundEngine === "copilot-sdk" && (
              <span style={{ ...s.pill, background: "#1e1f3a", color: "#818cf8", fontSize: 11 }}>
                🤖 GitHub Copilot SDK
              </span>
            )}
            {playgroundEngine === "direct" && (
              <span style={{ ...s.pill, ...s.pillBlue, fontSize: 11 }}>⚡ Direct inference</span>
            )}
          </div>
          <div style={s.resultBox}>
            {playgroundLoading ? "Running agent..." : playgroundResult || "Output will appear here after testing."}
          </div>
        </div>

        <div style={{ ...s.row, gap: 10 }}>
          <button style={{ ...s.btn, ...s.btnSecondary }} onClick={onOpenLLMConfig}>LLM Config</button>
          <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleTest} disabled={playgroundLoading}>
            {playgroundLoading ? "Testing..." : "Test"}
          </button>
        </div>
      </div>

      {/* Create Agent */}
      <div style={{ ...s.row, justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
        {submitError && <div style={{ ...s.error, alignSelf: "center" }}>{submitError}</div>}
        {submitSuccess && <div style={{ ...s.success, alignSelf: "center" }}>{submitSuccess}</div>}
        <button style={{ ...s.btn, ...s.btnSuccess, fontSize: 15, padding: "11px 28px" }} onClick={handleCreate}>
          Create Agent
        </button>
      </div>
    </div>
  );
}
