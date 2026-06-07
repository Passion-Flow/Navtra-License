import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Private delivery: no public CDN; API base injected at runtime via window.__APP_CONFIG__.
// Dev proxy target is overridable (VITE_API_PROXY) so the same config works locally
// (localhost:13001) and inside docker (http://forge-api:8080).
const apiProxy = process.env.VITE_API_PROXY || "http://localhost:13001";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    host: true,
    port: 13000,
    proxy: {
      "/admin-api": { target: apiProxy, changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
