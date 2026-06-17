import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    hmr: {
      clientPort: 5173,
      host: "localhost",
    },
  },
  resolve: {
    dedupe: ["react", "react-dom"],
  },
});
