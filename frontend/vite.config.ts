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
        // (Function form: Vite 8's Rolldown no longer takes the object form.)
        manualChunks(id: string) {
          if (!id.includes('/node_modules/')) return undefined
          if (
            /\/node_modules\/(react|react-dom|react-router|react-router-dom|scheduler)\//.test(
              id,
            )
          )
            return 'react'
          if (id.includes('/node_modules/@tanstack/')) return 'query'
          if (/\/node_modules\/(lightweight-charts|fancy-canvas)\//.test(id))
            return 'charts'
          return undefined
        },
      },
    },
    // The largest chunk is the password-strength word lists (@zxcvbn-ts language
    // packs, ~1.2 MB): loaded only on password screens, never on the main pages.
    chunkSizeWarningLimit: 1300,
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
