import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Vite config tuned for Docker: bind to 0.0.0.0 so the port is reachable
// from the host, and enable HMR over the mapped port.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        // Split large vendors into their own chunks for better caching and
        // a smaller initial load (charts only load when a modal opens).
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          query: ['@tanstack/react-query'],
          charts: ['lightweight-charts'],
        },
      },
    },
    chunkSizeWarningLimit: 900,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    watch: {
      // Bind-mounted volumes on macOS/Windows need polling for HMR to fire.
      usePolling: true,
    },
    hmr: {
      // Browser connects back on the host-mapped port.
      clientPort: 5173,
    },
  },
})
