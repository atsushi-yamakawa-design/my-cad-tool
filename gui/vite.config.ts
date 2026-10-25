import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// ビルド結果は Python パッケージの中に置き、`uv run alucad gui` がそのまま配信する
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/alucad/gui/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 2000,
  },
  // 開発時（npm run dev）は API を Python サーバーへ中継する
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
