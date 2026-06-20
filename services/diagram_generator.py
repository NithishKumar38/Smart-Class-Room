"""
services/diagram_generator.py
==============================
Diagram rendering service for the AI Classroom Co-Pilot.

Implements a 4-level fallback pipeline to guarantee a visual is ALWAYS shown:
  1. Render Mermaid diagram from Gemini output
  2. Auto-sanitise & retry Mermaid code once
  3. Generate a dynamic SVG flowchart (svgwrite)
  4. Render a Streamlit-native text flowchart (always works, no dependencies)

Author: AI Classroom Co-Pilot Team
"""

import logging
import re
import math
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mermaid Code Validator / Sanitiser
# ---------------------------------------------------------------------------

def _sanitize_mermaid(code: str) -> str:
    """
    Strip HTML script tags from Mermaid code.
    """
    code = re.sub(r"<script.*?>.*?</script>", "", code, flags=re.DOTALL | re.IGNORECASE)
    code = re.sub(r"<[^>]+>", "", code)
    return code.strip()


def _fix_mermaid_code(code: str) -> str:
    """
    Attempt to auto-fix common Mermaid syntax errors that cause parse failures:

    - Ensures the diagram starts with a valid graph declaration
    - Wraps bare node labels in double quotes
    - Removes semicolons
    - Replaces curly-brace node syntax with bracket syntax
    - Strips markdown fences if present
    """
    if not code:
        return ""

    # Strip markdown fences
    code = re.sub(r"^```(?:mermaid)?\s*", "", code.strip(), flags=re.IGNORECASE)
    code = re.sub(r"```\s*$", "", code.strip())
    code = code.strip()

    # Remove semicolons
    code = code.replace(";", "")

    # If no graph declaration at all, add one
    if not re.match(r"^\s*(graph|flowchart|sequenceDiagram|classDiagram|erDiagram|gantt)", code, re.IGNORECASE):
        code = "graph TD\n" + code

    lines = code.splitlines()
    fixed_lines = []
    for line in lines:
        # Fix node labels containing special chars — wrap with double quotes if not already
        # Pattern: NodeID[label] or NodeID(label) where label has problematic chars
        def _quote_label(m):
            nid = m.group(1)
            bracket_open = m.group(2)
            label = m.group(3)
            bracket_close = m.group(4)
            # If label already has surrounding quotes, leave it
            if label.startswith('"') and label.endswith('"'):
                return f'{nid}{bracket_open}{label}{bracket_close}'
            # Escape any existing quotes in label
            label = label.replace('"', "'")
            return f'{nid}{bracket_open}"{label}"{bracket_close}'

        # Fix [...] style nodes
        line = re.sub(r'(\w+)(\[)([^\[\]]+)(\])', _quote_label, line)
        # Fix (...) style nodes — convert to [...]
        line = re.sub(r'(\w+)(\()([^\(\)]+)(\))', lambda m: f'{m.group(1)}["{m.group(3).replace(chr(34), chr(39))}"]', line)
        # Fix {...} style nodes — convert to [...]
        line = re.sub(r'(\w+)(\{)([^\{\}]+)(\})', lambda m: f'{m.group(1)}["{m.group(3).replace(chr(34), chr(39))}"]', line)

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


# ---------------------------------------------------------------------------
# Mermaid HTML Renderer
# ---------------------------------------------------------------------------

def render_mermaid_html(mermaid_code: str) -> str:
    """
    Generate a self-contained HTML string that renders a Mermaid diagram.

    Uses Mermaid.js 10 loaded from CDN. On Mermaid parse error, the HTML
    will show a blank area — callers should catch this via the JS error
    callback and fall back to SVG.

    Args:
        mermaid_code: Valid Mermaid diagram DSL string.

    Returns:
        HTML string with embedded Mermaid diagram and JS error detection.
    """
    if not mermaid_code or not mermaid_code.strip():
        return _empty_diagram_html("No diagram code was generated.")

    safe_code = _sanitize_mermaid(mermaid_code)

    # Escape for JS string embedding
    js_escaped = safe_code.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: transparent;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 8px;
      font-family: 'Segoe UI', Arial, sans-serif;
    }}
    #diagram-container {{
      width: 100%;
      max-width: 100%;
    }}
    .mermaid {{
      max-width: 100%;
    }}
    svg {{
      max-width: 100% !important;
      border-radius: 12px;
    }}
    #error-box {{
      display: none;
      padding: 16px;
      background: rgba(232,64,64,0.12);
      border: 1px solid rgba(232,64,64,0.4);
      border-radius: 10px;
      color: #e84040;
      font-size: 0.85rem;
      text-align: center;
      width: 100%;
    }}
  </style>
</head>
<body>
  <div id="diagram-container">
    <div class="mermaid" id="mermaid-div">
{safe_code}
    </div>
    <div id="error-box">⚠️ Diagram rendering failed. Showing text summary instead.</div>
  </div>
  <script>
    mermaid.initialize({{
      startOnLoad: false,
      theme: 'base',
      themeVariables: {{
        primaryColor: '#1e3a5f',
        primaryTextColor: '#e8f4fd',
        primaryBorderColor: '#4A90D9',
        lineColor: '#F5A623',
        secondaryColor: '#0d2137',
        tertiaryColor: '#0a1628',
        fontFamily: 'Segoe UI, Arial, sans-serif',
        fontSize: '13px',
        background: '#0a1628',
        mainBkg: '#1e3a5f',
        nodeBorder: '#4A90D9',
        clusterBkg: '#0d2137',
        titleColor: '#e8f4fd',
        edgeLabelBackground: '#0d2137',
      }},
      flowchart: {{ curve: 'basis', padding: 20 }},
      securityLevel: 'loose',
    }});

    mermaid.run({{
      nodes: [document.getElementById('mermaid-div')],
    }}).catch(function(err) {{
      document.getElementById('mermaid-div').style.display = 'none';
      document.getElementById('error-box').style.display = 'block';
      console.error('Mermaid error:', err);
    }});
  </script>
</body>
</html>
"""
    return html


def _empty_diagram_html(message: str = "") -> str:
    """Return a placeholder HTML when no diagram is available."""
    msg = message or "No diagram available for this topic."
    return f"""
<div style="
  padding: 20px;
  text-align: center;
  color: #7fb3d3;
  font-family: 'Segoe UI', sans-serif;
  background: rgba(74,144,217,0.06);
  border-radius: 10px;
  border: 1px dashed rgba(74,144,217,0.3);
">
  📊 {msg}
</div>
"""


# ---------------------------------------------------------------------------
# SVG Fallback Generator (Flowchart — top-down)
# ---------------------------------------------------------------------------

def generate_svg_diagram(topic: str, key_points: list) -> str:
    """
    Generate a vertical top-down flowchart SVG as Mermaid fallback.

    Creates boxes connected by arrows: topic → step1 → step2 → ... (max 6 steps).

    Args:
        topic:       Main topic label for the top node.
        key_points:  List of step/concept strings (max 6).

    Returns:
        SVG XML string (always non-empty).
    """
    try:
        import svgwrite

        nodes = [topic[:28]] + [p[:28] for p in key_points[:5]]
        n = len(nodes)

        box_w, box_h = 220, 44
        gap = 30            # vertical gap between boxes
        padding = 40
        total_h = padding + n * (box_h + gap) + padding
        total_w = box_w + 2 * padding + 60

        dwg = svgwrite.Drawing(size=(f"{total_w}px", f"{total_h}px"))

        # Dark background
        dwg.add(dwg.rect(insert=(0, 0), size=(total_w, total_h),
                         fill="#0d2137", rx=12, ry=12))

        cx = total_w // 2

        colors = [
            "#4A90D9",  # topic — blue
            "#50C878", "#50C878", "#50C878",  # steps — green
            "#F5A623", "#F5A623",             # results — amber
        ]

        box_tops = []
        for i, label in enumerate(nodes):
            y = padding + i * (box_h + gap)
            box_tops.append(y)
            color = colors[i] if i < len(colors) else "#4A90D9"

            dwg.add(dwg.rect(
                insert=(cx - box_w // 2, y),
                size=(box_w, box_h),
                fill=color,
                rx=8, ry=8,
                opacity=0.9,
            ))
            dwg.add(dwg.text(
                label,
                insert=(cx, y + box_h // 2 + 5),
                text_anchor="middle",
                fill="white",
                font_size="13px",
                font_weight="bold",
                font_family="Segoe UI, Arial",
            ))

        # Arrows between boxes
        for i in range(n - 1):
            y_start = box_tops[i] + box_h
            y_end = box_tops[i + 1]
            mid_y = (y_start + y_end) // 2

            dwg.add(dwg.line(
                start=(cx, y_start),
                end=(cx, y_end - 8),
                stroke="#F5A623",
                stroke_width=2.5,
            ))
            # Arrowhead
            dwg.add(dwg.polygon(
                points=[(cx - 7, y_end - 8), (cx + 7, y_end - 8), (cx, y_end)],
                fill="#F5A623",
            ))

        return dwg.tostring()

    except ImportError:
        logger.warning("svgwrite not installed, using minimal SVG.")
        return _minimal_svg(topic, key_points)
    except Exception as e:
        logger.error("SVG generation failed: %s", e)
        return _minimal_svg(topic, key_points)


def _minimal_svg(topic: str, key_points: list) -> str:
    """Pure-Python SVG fallback — no external dependencies."""
    nodes = [topic[:28]] + [p[:28] for p in key_points[:5]]
    n = len(nodes)
    box_w, box_h, gap, pad = 240, 44, 30, 40
    total_h = pad + n * (box_h + gap) + pad
    total_w = box_w + 100

    colors = ["#4A90D9", "#50C878", "#50C878", "#50C878", "#F5A623", "#F5A623"]
    cx = total_w // 2

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}">',
        f'<rect width="{total_w}" height="{total_h}" fill="#0d2137" rx="12"/>',
    ]

    box_tops = []
    for i, label in enumerate(nodes):
        y = pad + i * (box_h + gap)
        box_tops.append(y)
        color = colors[i] if i < len(colors) else "#4A90D9"
        svg_parts.append(
            f'<rect x="{cx - box_w // 2}" y="{y}" width="{box_w}" height="{box_h}" '
            f'fill="{color}" rx="8" opacity="0.9"/>'
        )
        svg_parts.append(
            f'<text x="{cx}" y="{y + box_h // 2 + 5}" text-anchor="middle" '
            f'fill="white" font-size="13" font-weight="bold" font-family="Arial">'
            f'{label}</text>'
        )

    for i in range(n - 1):
        y_start = box_tops[i] + box_h
        y_end = box_tops[i + 1]
        svg_parts.append(
            f'<line x1="{cx}" y1="{y_start}" x2="{cx}" y2="{y_end - 8}" '
            f'stroke="#F5A623" stroke-width="2.5"/>'
        )
        svg_parts.append(
            f'<polygon points="{cx-7},{y_end-8} {cx+7},{y_end-8} {cx},{y_end}" fill="#F5A623"/>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


# ---------------------------------------------------------------------------
# Mermaid Code Extractor
# ---------------------------------------------------------------------------

def extract_mermaid(text: str) -> Optional[str]:
    """
    Extract Mermaid code from raw LLM response text.

    Looks for [MERMAID_START] ... [MERMAID_END] markers first,
    then falls back to standard ```mermaid``` code fences.

    Args:
        text: Raw LLM response string.

    Returns:
        Mermaid code string or None.
    """
    if not text:
        return None

    # Primary: custom tags from our prompt
    match = re.search(
        r"\[MERMAID_START\](.*?)\[MERMAID_END\]",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        code = match.group(1).strip()
        return code if code else None

    # Fallback: standard mermaid fences
    match = re.search(
        r"```mermaid\s*(.*?)\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    return None


# ---------------------------------------------------------------------------
# Master Diagram Renderer — 4-Level Fallback Pipeline
# ---------------------------------------------------------------------------

def render_diagram_with_fallback(
    mermaid_code: Optional[str],
    topic: str,
    key_points: list,
) -> dict:
    """
    Attempt to render a diagram using a 4-level fallback pipeline:

      Level 1: Raw Mermaid code from Gemini
      Level 2: Auto-fixed / sanitised Mermaid code
      Level 3: SVG flowchart generated from topic + key_points
      Level 4: (handled by caller) Streamlit native text flowchart

    Returns a dict:
      {
        "type":   "mermaid" | "mermaid_fixed" | "svg" | "streamlit",
        "html":   str | None,   # HTML for mermaid levels
        "svg":    str | None,   # SVG string for svg level
        "level":  int,          # 1-4
      }
    """
    # ── Level 1: Original Mermaid ──────────────────────────────────────────
    if mermaid_code and mermaid_code.strip():
        logger.info("Diagram: trying Level 1 — original Mermaid")
        return {
            "type": "mermaid",
            "html": render_mermaid_html(mermaid_code),
            "svg": None,
            "level": 1,
        }

    # ── Level 2: Auto-fixed Mermaid ───────────────────────────────────────
    if mermaid_code:
        fixed = _fix_mermaid_code(mermaid_code)
        if fixed and fixed.strip():
            logger.info("Diagram: trying Level 2 — auto-fixed Mermaid")
            return {
                "type": "mermaid_fixed",
                "html": render_mermaid_html(fixed),
                "svg": None,
                "level": 2,
            }

    # ── Level 3: SVG Diagram ──────────────────────────────────────────────
    logger.info("Diagram: falling back to Level 3 — SVG")
    svg = generate_svg_diagram(topic, key_points)
    if svg:
        return {
            "type": "svg",
            "html": None,
            "svg": svg,
            "level": 3,
        }

    # ── Level 4: Streamlit text flowchart (handled in UI layer) ───────────
    logger.info("Diagram: falling back to Level 4 — Streamlit native")
    return {
        "type": "streamlit",
        "html": None,
        "svg": None,
        "level": 4,
    }
