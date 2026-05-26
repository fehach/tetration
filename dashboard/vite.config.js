var _a;
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
var API_TARGET = (_a = process.env.VITE_API_TARGET) !== null && _a !== void 0 ? _a : "http://127.0.0.1:8765";
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: { "@": path.resolve(__dirname, "src") },
    },
    build: {
        // Emit assets directly into the FastAPI static directory.
        outDir: path.resolve(__dirname, "../csw_agent/dashboard/static"),
        emptyOutDir: true,
    },
    server: {
        port: 5173,
        proxy: {
            "/api": {
                target: API_TARGET,
                changeOrigin: true,
            },
        },
    },
});
