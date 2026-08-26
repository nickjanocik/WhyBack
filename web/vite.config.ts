/// <reference types="vitest/config" />

/** Configures the local Vite frontend, test environment, and bridge proxy. */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5163,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:4173",
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
