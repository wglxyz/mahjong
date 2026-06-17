import { defineConfig } from "vite";

// Served by the Python server under /laya/ (same origin as the WebSocket),
// so the remote single-port setup keeps working: http://<host>:5000/laya/
export default defineConfig({
  base: "/laya/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2020",
  },
});
