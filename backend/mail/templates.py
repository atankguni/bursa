"""
mail/templates.py
-----------------
A shared look for HTML emails. Email clients ignore <style> blocks and CSS
variables, so everything is inline and table-free; keep bodies simple.
Always send a plain-text version alongside (Email.text).
"""

from html import escape

# Bursa's default (blue) accent and slate palette, as hex for email clients.
_ACCENT = "#2563eb"
_INK = "#0f172a"
_MUTED = "#64748b"
_LINE = "#e2e8f0"
_FONT = "-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"

_BODY = f"margin:0;padding:24px;background:#f4f6fa;font-family:{_FONT};color:{_INK};"
_CARD = (
    "max-width:560px;margin:0 auto;background:#ffffff;"
    f"border:1px solid {_LINE};border-radius:6px;overflow:hidden;"
)
_FOOTER = f"padding:12px 24px;border-top:1px solid {_LINE};font-size:11px;color:{_MUTED};"


def layout(title: str, body_html: str, footer: str = "Sent by Bursa, your IDX monitor.") -> str:
    """Wrap trusted `body_html` in the standard frame; `title` and `footer` are escaped."""
    return f"""<!doctype html>
<html lang="en">
<body style="{_BODY}">
  <div style="{_CARD}">
    <div style="height:4px;background:{_ACCENT};"></div>
    <div style="padding:20px 24px;">
      <h1 style="margin:0 0 12px;font-size:18px;line-height:1.3;">{escape(title)}</h1>
      <div style="font-size:14px;line-height:1.55;">{body_html}</div>
    </div>
    <div style="{_FOOTER}">{escape(footer)}</div>
  </div>
</body>
</html>"""
