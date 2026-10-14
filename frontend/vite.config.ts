import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite config tuned for Docker: bind to 0.0.0.0 so the port is reachable
// from the host, and enable HMR over the mapped port.
export default defineConfig({
  plugins: [react()],
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
