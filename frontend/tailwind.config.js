/** @type {import('tailwindcss').Config} */
export default {
  // Theme is driven by a `.dark` class on <html> (see SettingsProvider).
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
        'line-strong': 'rgb(var(--c-line-strong) / <alpha-value>)',
        ink: 'rgb(var(--c-ink) / <alpha-value>)',
        muted: 'rgb(var(--c-muted) / <alpha-value>)',
        subtle: 'rgb(var(--c-subtle) / <alpha-value>)',
        bull: 'rgb(var(--c-bull) / <alpha-value>)',
        bear: 'rgb(var(--c-bear) / <alpha-value>)',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)',
        pop: '0 10px 30px -12px rgb(15 23 42 / 0.35)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(2px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 140ms ease-out',
      },
    },
  },
  plugins: [],
}
