/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Bursa palette
        bull: '#16a34a',   // green  -> up
        bear: '#dc2626',   // red    -> down
        panel: '#0f172a',  // slate-900
        panelalt: '#1e293b',
      },
    },
  },
  plugins: [],
}
