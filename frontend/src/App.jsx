import React, { useState, useEffect } from "react";
import AgentCreationPage from "./components/AgentCreationPage";
import SidePanel from "./components/SidePanel";
import LLMConfigPage from "./components/LLMConfigPage";
import ToolsManagementPage from "./components/ToolsManagementPage";
import TaskPlaygroundPage from "./components/TaskPlaygroundPage";
import { fetchDomains, fetchAgents, fetchLLMConfigs } from "./api";

export default function App() {
  const [domains, setDomains] = useState([]);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [page, setPage] = useState("agent"); // "agent" | "llm" | "tools" | "tasks"
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

  // Also refresh active LLM config independently when returning from LLM config page
  const refreshAfterLLMConfig = async () => {
    await refresh();
  };  useEffect(() => { refresh(); }, []);

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "Inter, sans-serif", background: "#0f1117" }}>
      {page === "agent" && (
        <SidePanel
          domains={domains}
          agents={agents}
          onSelectAgent={setSelectedAgent}
          selectedAgent={selectedAgent}
          onOpenTools={() => setPage("tools")}
          onOpenTasks={() => setPage("tasks")}
        />
      )}
      <main style={{ flex: 1, overflowY: "auto" }}>
        {page === "agent" ? (
          <AgentCreationPage
            domains={domains}
            onRefresh={refresh}
            prefillAgent={selectedAgent}
            onClearPrefill={() => setSelectedAgent(null)}
            onOpenLLMConfig={() => setPage("llm")}
            activeLLMConfig={activeLLMConfig}
          />
        ) : page === "llm" ? (
          <LLMConfigPage onBack={() => { setPage("agent"); refresh(); }} />
        ) : page === "tools" ? (
          <ToolsManagementPage onBack={() => setPage("agent")} />
        ) : (
          <TaskPlaygroundPage onBack={() => setPage("agent")} />
        )}
      </main>
    </div>
  );
}
