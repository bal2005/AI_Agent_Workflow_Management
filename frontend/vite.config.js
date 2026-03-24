import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/domains": "http://localhost:8000",
      "/agents": "http://localhost:8000",
      "/llm-configs": "http://localhost:8000",
      "/tools": "http://localhost:8000",
      "/task-playground": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
