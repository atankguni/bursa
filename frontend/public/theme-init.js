// Apply saved settings before first paint to avoid a flash. A file (not inline
// in index.html) so the Content-Security-Policy can forbid inline scripts.
;(function () {
  try {
    var s = {}
    try {
      s = JSON.parse(localStorage.getItem('bursa-settings') || '{}') || {}
    } catch (e) {}
    var theme = s.theme || localStorage.getItem('bursa-theme') || 'system'
    var dark =
      theme === 'dark' ||
      (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    var el = document.documentElement
    el.classList.toggle('dark', dark)
    el.setAttribute('data-density', s.density || 'medium')
    if (s.reduceMotion) el.setAttribute('data-reduce-motion', '')
    if (s.highContrast) el.setAttribute('data-high-contrast', '')
    el.setAttribute('data-accent', s.accent || 'blue')
  } catch (e) {}
})()
