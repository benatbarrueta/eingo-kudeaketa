import { defineConfig, loadEnv, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "../backend", ["EINGO_LOCAL_WRITES", "ADMIN_TOKEN"]);
  const token = env.ADMIN_TOKEN;
  const localWrites = env.EINGO_LOCAL_WRITES === "true" && Boolean(token);

  const proxy: ProxyOptions = {
    target: "http://127.0.0.1:8000",
    configure(server) {
      if (!localWrites) return;
      server.on("proxyReq", (outgoing, incoming) => {
        const host = incoming.headers.host;
        if (
          incoming.method === "POST" &&
          /^\/api\/(?:events(?:\/\d+\/(?:edit|delete))?|sheets\/import-document|document\/sync)$/.test(incoming.url ?? "") &&
          incoming.socket.remoteAddress === "127.0.0.1" &&
          host?.startsWith("127.0.0.1:") &&
          incoming.headers.origin === "http://" + host
        ) {
          outgoing.setHeader("Authorization", "Bearer " + token);
        }
      });
    },
  };

  return {
    plugins: [react()],
    define: { "import.meta.env.VITE_LOCAL_WRITES": JSON.stringify(localWrites) },
    server: { host: "127.0.0.1", proxy: { "/api": proxy } },
    preview: { host: "127.0.0.1", proxy: { "/api": "http://127.0.0.1:8000" } },
  };
});
