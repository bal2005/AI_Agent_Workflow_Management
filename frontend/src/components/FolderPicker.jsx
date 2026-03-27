import React, { useState, useEffect } from "react";
import axios from "axios";

const api = axios.create({ baseURL: "/" });

const s = {
  overlay:   { position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 2000, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 },
  modal:     { background: "#13151f", border: "1px solid #2d3148", borderRadius: 12, width: "100%", maxWidth: 560, maxHeight: "80vh", display: "flex", flexDirection: "column", overflow: "hidden" },
  head:      { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid #1e2130", flexShrink: 0 },
  title:     { fontSize: 14, fontWeight: 700, color: "#f8fafc" },
  closeBtn:  { background: "none", border: "none", color: "#64748b", fontSize: 18, cursor: "pointer" },
  breadcrumb:{ padding: "8px 20px", fontSize: 11, color: "#475569", background: "#0f1117", borderBottom: "1px solid #1e2130", fontFamily: "monospace", flexShrink: 0 },
  body:      { flex: 1, overflowY: "auto", padding: "8px 0" },
  entry:     (isDir) => ({
    display: "flex", alignItems: "center", gap: 10, padding: "9px 20px",
    cursor: isDir ? "pointer" : "default", fontSize: 13,
    color: isDir ? "#e2e8f0" : "#64748b",
    transition: "background .1s",
  }),
  footer:    { padding: "12px 20px", borderTop: "1px solid #1e2130", display: "flex", gap: 10, alignItems: "center", flexShrink: 0 },
  pathInput: { flex: 1, padding: "7px 11px", borderRadius: 7, border: "1px solid #2d3148", background: "#0f1117", color: "#e2e8f0", fontSize: 12, outline: "none", fontFamily: "monospace" },
  selectBtn: { padding: "8px 18px", borderRadius: 8, background: "#6366f1", border: "none", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer" },
  backBtn:   { padding: "8px 14px", borderRadius: 8, background: "#2d3148", border: "none", color: "#cbd5e1", fontSize: 12, cursor: "pointer" },
  error:     { fontSize: 12, color: "#f87171", padding: "8px 20px" },
};

export default function FolderPicker({ onSelect, onClose }) {
  const [currentPath, setCurrentPath] = useState("/");
  const [entries, setEntries] = useState([]);
  const [parent, setParent] = useState(null);
  const [fullPath, setFullPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newFolderName, setNewFolderName] = useState("");
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [creating, setCreating] = useState(false);

  const browse = async (path) => {
    setLoading(true); setError("");
    try {
      const { data } = await api.get("/fs/browse", { params: { path } });
      setCurrentPath(data.current);
      setEntries(data.entries);
      setParent(data.parent);
      setFullPath(data.full_path);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to browse directory");
    } finally {
      setLoading(false); }
  };

  useEffect(() => { browse("/"); }, []);

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    setCreating(true); setError("");
    const newPath = currentPath.replace(/\/$/, "") + "/" + newFolderName.trim();
    try {
      await api.post("/fs/mkdir", { path: newPath });
      setNewFolderName(""); setShowNewFolder(false);
      await browse(currentPath);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to create folder");
    } finally { setCreating(false); }
  };

  const handleOverlay = (e) => { if (e.target === e.currentTarget) onClose(); };

  return (
    <div style={s.overlay} onClick={handleOverlay}>
      <div style={s.modal}>
        <div style={s.head}>
          <div style={s.title}>📁 Select Folder</div>
          <button style={s.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div style={s.breadcrumb}>/workspace{currentPath === "/" ? "" : currentPath}</div>

        {/* New folder row */}
        {showNewFolder ? (
          <div style={{ display: "flex", gap: 8, padding: "8px 20px", borderBottom: "1px solid #1e2130", flexShrink: 0 }}>
            <input
              autoFocus
              style={{ ...s.pathInput, flex: 1 }}
              placeholder="New folder name..."
              value={newFolderName}
              onChange={e => setNewFolderName(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleCreateFolder(); if (e.key === "Escape") setShowNewFolder(false); }}
            />
            <button style={{ ...s.selectBtn, background: "#166534", fontSize: 12 }} onClick={handleCreateFolder} disabled={creating}>
              {creating ? "..." : "Create"}
            </button>
            <button style={{ ...s.backBtn, fontSize: 12 }} onClick={() => setShowNewFolder(false)}>Cancel</button>
          </div>
        ) : (
          <div style={{ padding: "6px 20px", borderBottom: "1px solid #1e2130", flexShrink: 0 }}>
            <button
              style={{ background: "none", border: "1px solid #2d3148", borderRadius: 6, color: "#4ade80", fontSize: 11, padding: "4px 10px", cursor: "pointer" }}
              onClick={() => setShowNewFolder(true)}
            >
              ＋ New Folder
            </button>
          </div>
        )}

        <div style={s.body}>
          {loading && <div style={{ padding: "12px 20px", fontSize: 12, color: "#475569" }}>Loading...</div>}
          {error && <div style={s.error}>{error}</div>}

          {!loading && parent !== null && (
            <div
              style={{ ...s.entry(true) }}
              onClick={() => browse(parent)}
              onMouseEnter={e => e.currentTarget.style.background = "#1a1d2e"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            >
              <span>⬆</span> ..
            </div>
          )}

          {!loading && entries.map(entry => (
            <div
              key={entry.path}
              style={s.entry(entry.is_dir)}
              onClick={() => entry.is_dir && browse(entry.path)}
              onMouseEnter={e => { if (entry.is_dir) e.currentTarget.style.background = "#1a1d2e"; }}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            >
              <span>{entry.is_dir ? "📁" : "📄"}</span>
              <span style={{ flex: 1 }}>{entry.name}</span>
              {!entry.is_dir && entry.size != null && (
                <span style={{ fontSize: 11, color: "#475569" }}>{(entry.size / 1024).toFixed(1)}KB</span>
              )}
            </div>
          ))}

          {!loading && entries.length === 0 && !error && (
            <div style={{ padding: "12px 20px", fontSize: 12, color: "#475569" }}>Empty folder</div>
          )}
        </div>

        <div style={s.footer}>
          <input
            style={s.pathInput}
            value={fullPath}
            onChange={e => setFullPath(e.target.value)}
            placeholder="Container path..."
          />
          <button style={s.selectBtn} onClick={() => { onSelect(fullPath); onClose(); }}>
            Select
          </button>
        </div>
      </div>
    </div>
  );
}
