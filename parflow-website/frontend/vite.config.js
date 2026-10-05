import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
export default defineConfig(({mode}) => ({
  plugins: [vue()],
  resolve: {alias: {"@": fileURLToPath(new URL("./src", import.meta.url))}},
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || loadEnv(mode, process.cwd()).VITE_API_TARGET || "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  build: { chunkSizeWarningLimit: 800 },
}));
