import { resolve } from "node:path";

import { defineConfig } from "vite";

export default defineConfig({
  build: {
    emptyOutDir: true,
    outDir: resolve(__dirname, "static/dist"),
    rollupOptions: {
      input: {
        betting: resolve(__dirname, "frontend/src/betting/main.ts"),
        display: resolve(__dirname, "frontend/src/display/main.ts"),
      },
      output: {
        assetFileNames: "assets/[name]-[hash][extname]",
        chunkFileNames: "chunks/[name]-[hash].js",
        entryFileNames: "[name].js",
      },
    },
    sourcemap: true,
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
  test: {
    include: ["frontend/**/*.test.ts"],
  },
});
