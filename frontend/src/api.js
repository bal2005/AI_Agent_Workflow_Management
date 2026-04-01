import axios from "axios";

// Use relative URLs so all requests go through the Vite dev proxy → no CORS issues
const api = axios.create({ baseURL: "/" });

export const fetchDomains = () => api.get("/domains/").then(r => r.data);
export const createDomain = (name, domain_prompt = null) =>
  api.post("/domains/", { name, domain_prompt }).then(r => r.data);
export const updateDomain = (id, payload) => api.patch(`/domains/${id}`, payload).then(r => r.data);

export const fetchAgents = () => api.get("/agents/").then(r => r.data);
export const checkAgentName = (name) => api.get("/agents/check-name", { params: { name } }).then(r => r.data);
export const updateAgent = (id, payload) => api.patch(`/agents/${id}`, payload).then(r => r.data);
export const deleteAgent = (id) => api.delete(`/agents/${id}`);

export const createAgent = (formData) =>
  api.post("/agents/", formData, { headers: { "Content-Type": "multipart/form-data" } });

export const runPlayground = (system_prompt, user_prompt, llm_config_id = null, domain_prompt = null, web_permissions = null) =>
  api.post("/agents/playground", { system_prompt, user_prompt, llm_config_id, domain_prompt, web_permissions }).then(r => r.data);

// LLM Configs
export const fetchLLMConfigs = () => api.get("/llm-configs/").then(r => r.data);
export const createLLMConfig = (payload) => api.post("/llm-configs/", payload).then(r => r.data);
export const updateLLMConfig = (id, payload) => api.patch(`/llm-configs/${id}`, payload).then(r => r.data);
export const activateLLMConfig = (id) => api.post(`/llm-configs/${id}/activate`).then(r => r.data);
export const deleteLLMConfig = (id) => api.delete(`/llm-configs/${id}`);

// Tools Management
export const fetchTools = () => api.get("/tools/").then(r => r.data);
export const fetchAgentsByDomain = (domainId) => api.get(`/tools/domains/${domainId}/agents`).then(r => r.data);
export const fetchAgentToolAccess = (agentId) => api.get(`/tools/agents/${agentId}/access`).then(r => r.data);
export const saveAgentToolAccess = (agentId, entries) =>
  api.put(`/tools/agents/${agentId}/access`, { entries }).then(r => r.data);

// Task Playground
export const runTaskPlayground = (payload) =>
  api.post("/task-playground/run", payload).then(r => r.data);

// Tasks CRUD
export const fetchTasks = () => api.get("/tasks/").then(r => r.data);
export const createTask = (payload) => api.post("/tasks/", payload).then(r => r.data);
export const updateTask = (id, payload) => api.patch(`/tasks/${id}`, payload).then(r => r.data);
export const deleteTask = (id) => api.delete(`/tasks/${id}`);
export const dryRunTask = (payload) => api.post("/tasks/dry-run", payload).then(r => r.data);
export const dryRunSavedTask = (id) => api.post(`/tasks/${id}/dry-run`).then(r => r.data);
export const runTask = (id) => api.post(`/tasks/${id}/run`).then(r => r.data);
export const fetchTaskRuns = (id, limit = 50) => api.get(`/tasks/${id}/runs`, { params: { limit } }).then(r => r.data);
export const fetchTaskSchedules = (id) => api.get(`/tasks/${id}/schedules`).then(r => r.data);

// Schedules
export const fetchSchedules = () => api.get("/schedules/").then(r => r.data);
export const createSchedule = (payload) => api.post("/schedules/", payload).then(r => r.data);
export const updateSchedule = (id, payload) => api.patch(`/schedules/${id}`, payload).then(r => r.data);
export const deleteSchedule = (id) => api.delete(`/schedules/${id}`);
export const runScheduleNow = (id) => api.post(`/schedules/${id}/run-now`).then(r => r.data);
export const fetchScheduleRuns = (id, limit = 20) => api.get(`/schedules/${id}/runs`, { params: { limit } }).then(r => r.data);
export const fetchRun = (runId) => api.get(`/schedules/runs/${runId}`).then(r => r.data);
export const fetchAllRuns = (params = {}) => api.get("/schedules/all-runs", { params }).then(r => r.data);

// Dashboard
export const fetchDashboardSummary = () => api.get("/dashboard/summary").then(r => r.data);
