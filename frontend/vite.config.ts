import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  // the web app's Sentry DSN lives in backend/.env with the other keys (or the build's environment, in Docker)
  define: {
    "import.meta.env.VITE_SENTRY_DSN": JSON.stringify(
      process.env.VITE_SENTRY_DSN ?? loadEnv(mode, fileURLToPath(new URL("../backend", import.meta.url)), "VITE_SENTRY_").VITE_SENTRY_DSN ?? ""),
  },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true, ws: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // Libraries in their own files: they rarely change, so after a redeploy browsers keep them cached and only
        // re-download the app's own code (which used to share one 537 KB file with react-dom and motion).
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          const lib = (...names: string[]) => names.some((n) => id.includes(`/node_modules/${n}/`));
          if (lib("react", "react-dom", "react-router", "react-router-dom", "scheduler")) return "react";
          if (lib("motion", "motion-dom", "motion-utils", "framer-motion")) return "motion";
          if (/\/node_modules\/(recharts|d3-[^/]+|victory-vendor|es-toolkit|decimal\.js-light)\//.test(id)) return "charts";
          if (/\/node_modules\/(react-markdown|remark-[^/]+|rehype-[^/]+|katex|micromark[^/]*|mdast-[^/]+|hast-[^/]+|unist-[^/]+|unified|vfile[^/]*)\//.test(id)) return "markdown";
          if (id.includes("/node_modules/@sentry")) return "sentry";  // loads after the first page has drawn
          if (lib("lucide-react")) return "icons";  // one file, not one tiny file per icon shared between pages
          if (lib("@tanstack/query-core", "@tanstack/react-query", "zustand", "sonner", "tailwind-merge", "clsx")) return "vendor";
          return undefined;
        },
      },
    },
  },
}));
