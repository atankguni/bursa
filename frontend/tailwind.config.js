/** @type {import('tailwindcss').Config} */
export default {
  // Theme is driven by a `.dark` class on <html> (see ThemeProvider).
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Semantic tokens backed by CSS variables (light/dark aware).
        app: 'rgb(var(--c-app) / <alpha-value>)',
        panel: 'rgb(var(--c-panel) / <alpha-value>)',
        panelalt: 'rgb(var(--c-panelalt) / <alpha-value>)',
        active: 'rgb(var(--c-active) / <alpha-value>)',
        line: 'rgb(var(--c-line) / <alpha-value>)',
        ink: 'rgb(var(--c-ink) / <alpha-value>)',
        muted: 'rgb(var(--c-muted) / <alpha-value>)',
        subtle: 'rgb(var(--c-subtle) / <alpha-value>)',
        bull: 'rgb(var(--c-bull) / <alpha-value>)',
        bear: 'rgb(var(--c-bear) / <alpha-value>)',
      },
    },
  },
  plugins: [],
}
