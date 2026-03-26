import React, { useState, useEffect } from "react";
import LandingPage from "./components/LandingPage";
import AgentCreationPage from "./components/AgentCreationPage";
import SidePanel from "./components/SidePanel";
import LLMConfigPage from "./components/LLMConfigPage";
import ToolsManagementPage from "./components/ToolsManagementPage";
import TaskPlaygroundPage from "./components/TaskPlaygroundPage";
import TaskCreationPage from "./components/TaskCreationPage";
import TaskDetailsPage from "./components/TaskDetailsPage";
import SchedulerPage from "./components/SchedulerPage";
import RunHistoryPage from "./components/RunHistoryPage";
import AdminPanel from "./components/AdminPanel";
import Navbar from "./components/Navbar";
import { fetchDomains, fetchAgents, fetchLLMConfigs } from "./api";

export default function App() {
  const [domains, setDomains] = useState([]);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [page, setPage] = useState("landing");
  const [activeLLMConfig, setActiveLLMConfig] = useState(null);
  const [selectedTaskId, setSelectedTaskId] = useState(null);

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
    if (newPage !== "agents") setSelectedAgent(null);
  };

  const renderPage = () => {
    switch (page) {
      case "landing":
        return <LandingPage onNavigate={handleNavigate} />;
      case "agents":
        return (
          <AgentCreationPage
            domains={domains}
            onRefresh={refresh}
            prefillAgent={selectedAgent}
            onClearPrefill={() => setSelectedAgent(null)}
            onOpenLLMConfig={() => setPage("llm")}
            activeLLMConfig={activeLLMConfig}
          />
        );
      case "llm":
        return <LLMConfigPage />;
      case "tools":
        return <ToolsManagementPage />;
      case "task-create":
        return <TaskCreationPage onViewTask={(id) => { setSelectedTaskId(id); setPage("task-details"); }} />;
      case "task-details":
        return <TaskDetailsPage taskId={selectedTaskId} onBack={() => setPage("task-create")} />;
      case "scheduler":
        return <SchedulerPage onOpenRunHistory={() => setPage("run-history")} />;
      case "run-history":
        return <RunHistoryPage />;
      case "admin":
        return <AdminPanel onRefresh={refresh} />;
      case "task":
        return <TaskPlaygroundPage />;
      default:
        return <LandingPage onNavigate={handleNavigate} />;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", fontFamily: "Inter, sans-serif", background: "#0f1117" }}>
      {/* Navbar on all pages except landing */}
      {page !== "landing" && (
        <Navbar currentPage={page} onNavigate={handleNavigate} />
      )}

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Side panel only on agents page */}
        {page === "agents" && (
          <SidePanel
            domains={domains}
            agents={agents}
            onSelectAgent={setSelectedAgent}
            selectedAgent={selectedAgent}
          />
        )}
        <main style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
          {renderPage()}
        </main>
      </div>
    </div>
  );
}
