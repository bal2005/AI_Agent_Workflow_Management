import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams } from "react-router-dom";
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
import SandboxMonitorPage from "./components/SandboxMonitorPage";
import Navbar from "./components/Navbar";
import { fetchDomains, fetchAgents, fetchLLMConfigs } from "./api";

function Shell({ children, currentPage, domains, agents, selectedAgent, onSelectAgent }) {
  const navigate = useNavigate();
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", fontFamily: "Inter, sans-serif", background: "#0f1117" }}>
      <Navbar currentPage={currentPage} onNavigate={(p) => navigate(`/${p}`)} />
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {currentPage === "agents" && (
          <SidePanel domains={domains} agents={agents} onSelectAgent={onSelectAgent} selectedAgent={selectedAgent} />
        )}
        <main style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
          {children}
        </main>
      </div>
    </div>
  );
}

function TaskDetailsRoute() {
  const { taskId } = useParams();
  return <TaskDetailsPage taskId={parseInt(taskId)} onBack={() => window.location.href = "/task-create"} />;
}

export default function App() {
  const [domains, setDomains]             = useState([]);
  const [agents, setAgents]               = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
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

  const shell = (page, children) => (
    <Shell currentPage={page} domains={domains} agents={agents}
      selectedAgent={selectedAgent} onSelectAgent={setSelectedAgent}>
      {children}
    </Shell>
  );

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"                  element={<LandingPage />} />
        <Route path="/agents"            element={shell("agents", <AgentCreationPage domains={domains} onRefresh={refresh} prefillAgent={selectedAgent} onClearPrefill={() => setSelectedAgent(null)} onOpenLLMConfig={() => window.location.href = "/llm"} activeLLMConfig={activeLLMConfig} />)} />
        <Route path="/llm"               element={shell("llm",          <LLMConfigPage />)} />
        <Route path="/tools"             element={shell("tools",         <ToolsManagementPage />)} />
        <Route path="/task"              element={shell("task",          <TaskPlaygroundPage />)} />
        <Route path="/task-create"       element={shell("task-create",   <TaskCreationPage onViewTask={(id) => window.location.href = `/task-details/${id}`} />)} />
        <Route path="/task-details/:taskId" element={shell("task-create", <TaskDetailsRoute />)} />
        <Route path="/scheduler"         element={shell("scheduler",     <SchedulerPage onOpenRunHistory={() => window.location.href = "/run-history"} />)} />
        <Route path="/run-history"       element={shell("run-history",   <RunHistoryPage />)} />
        <Route path="/admin"             element={shell("admin",         <AdminPanel onRefresh={refresh} />)} />
        <Route path="/sandbox"           element={shell("sandbox",       <SandboxMonitorPage />)} />
        <Route path="*"                  element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
