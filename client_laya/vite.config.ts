import { defineConfig } from "vite";

// Served by the Python server under /laya/ (same origin as the WebSocket),
// so the remote single-port setup keeps working: http://<host>:5000/laya/
export default defineConfig({
  base: "/laya/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2020",
    rollupOptions: {
      input: {
        main: new URL("./index.html", import.meta.url).pathname,        // 3D table (default /laya/)
        twod: new URL("./index2d.html", import.meta.url).pathname,      // 2D board (/laya/index2d.html)
      },
    },
  },
});
