import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/domains":        { target: "http://localhost:8000", changeOrigin: true },
      "/agents":         { target: "http://localhost:8000", changeOrigin: true },
      "/llm-configs":    { target: "http://localhost:8000", changeOrigin: true },
      "/tools":          { target: "http://localhost:8000", changeOrigin: true },
      "/task-playground":{ target: "http://localhost:8000", changeOrigin: true },
      "/tasks":          { target: "http://localhost:8000", changeOrigin: true },
      "/schedules":      { target: "http://localhost:8000", changeOrigin: true },
      "/health":         { target: "http://localhost:8000", changeOrigin: true },
      "/fs":             { target: "http://localhost:8000", changeOrigin: true },
      "/sandbox":        { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
