import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Match the backend CORS defaults and Tauri devUrl.
    host: "127.0.0.1",
    port: 5173,
    strictPort: true
  },
  // Keep terminal logs visible inside Tauri's beforeDevCommand output.
  clearScreen: false
});
