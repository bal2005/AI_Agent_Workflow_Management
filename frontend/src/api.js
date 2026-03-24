import axios from "axios";

// Use relative URLs so all requests go through the Vite dev proxy → no CORS issues
const api = axios.create({ baseURL: "/" });

export const fetchDomains = () => api.get("/domains/").then(r => r.data);
export const createDomain = (name) => api.post("/domains/", { name });

export const fetchAgents = () => api.get("/agents/").then(r => r.data);
export const checkAgentName = (name) => api.get("/agents/check-name", { params: { name } }).then(r => r.data);

export const createAgent = (formData) =>
  api.post("/agents/", formData, { headers: { "Content-Type": "multipart/form-data" } });

export const runPlayground = (system_prompt, user_prompt, llm_config_id = null) =>
  api.post("/agents/playground", { system_prompt, user_prompt, llm_config_id }).then(r => r.data);

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
