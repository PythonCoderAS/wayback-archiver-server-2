import { sentryVitePlugin } from "@sentry/vite-plugin";
import react from "@vitejs/plugin-react-swc";
import { env } from "process";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    sentryVitePlugin({
      org: "pythoncoderas",
      project: "wayback-archiver-server-2-frontend",
      authToken: env.SENTRY_AUTH_TOKEN,
    }),
  ],

  base: "/app/",

  build: {
    sourcemap: true,
  },
});
