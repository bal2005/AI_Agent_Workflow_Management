import React, { useState, useEffect } from "react";
import AgentCreationPage from "./components/AgentCreationPage";
import SidePanel from "./components/SidePanel";
import LLMConfigPage from "./components/LLMConfigPage";
import ToolsManagementPage from "./components/ToolsManagementPage";
import TaskPlaygroundPage from "./components/TaskPlaygroundPage";
import Navbar from "./components/Navbar";
import { fetchDomains, fetchAgents, fetchLLMConfigs } from "./api";

export default function App() {
  const [domains, setDomains] = useState([]);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [page, setPage] = useState("agents"); // "agents" | "llm" | "tools" | "task"
  const [activeLLMConfig, setActiveLLMConfig] = useState(null);

  const refresh = async () => {
    const [d, a, configs] = await Promise.all([
      fetchDomains().catch(() => []),
      fetchAgents().catch(() => []),
      fetchLLMConfigs().catch(() => []),
    ]);
    setDomains(d);
    setAgents(a);
    setActiveLLMConfig(configs.find(c => c.is_active) || null);
  };

  useEffect(() => { refresh(); }, []);

  const handleNavigate = (newPage) => {
    setPage(newPage);
    // Clear selection when navigating away from agents page
    if (newPage !== "agents") {
      setSelectedAgent(null);
    }
  };

  const handleBack = () => {
    setPage("agents");
    setSelectedAgent(null);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "Inter, sans-serif", background: "#0f1117" }}>
      {/* Navbar — visible on all pages except agent creation (which has side panel) */}
      {page !== "agents" && (
        <Navbar
          onBack={handleBack}
          currentPage={page}
          onNavigate={handleNavigate}
        />
      )}

      <div style={{ display: "flex", flex: 1, overflowY: "auto" }}>
        {page === "agents" && (
          <SidePanel
            domains={domains}
            agents={agents}
            onSelectAgent={setSelectedAgent}
            selectedAgent={selectedAgent}
            onOpenTools={() => setPage("tools")}
            onOpenTasks={() => setPage("task")}
          />
        )}
        <main style={{ flex: 1, overflowY: "auto" }}>
          {page === "agents" ? (
            <AgentCreationPage
              domains={domains}
              onRefresh={refresh}
              prefillAgent={selectedAgent}
              onClearPrefill={() => setSelectedAgent(null)}
              onOpenLLMConfig={() => setPage("llm")}
              activeLLMConfig={activeLLMConfig}
            />
          ) : page === "llm" ? (
            <LLMConfigPage onBack={handleBack} />
          ) : page === "tools" ? (
            <ToolsManagementPage onBack={handleBack} />
          ) : (
            <TaskPlaygroundPage onBack={handleBack} />
          )}
        </main>
      </div>
    </div>
  );
}
