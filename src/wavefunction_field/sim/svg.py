# SPDX-License-Identifier: Apache-2.0
"""Minimal dependency-free SVG line and scatter plots."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

PALETTE = ["#2f6f4f", "#b5651d", "#3b6ea8", "#8e3b8e", "#777777"]


def _scale(v: float, lo: float, hi: float, a: float, b: float) -> float:
    return a if hi == lo else a + (v - lo) * (b - a) / (hi - lo)


def chart(
    title: str,
    series: Sequence[tuple[str, Sequence[tuple[float, float]]]],
    xlabel: str,
    ylabel: str,
    *,
    scatter: bool = False,
    w: int = 720,
    h: int = 420,
) -> str:
    pts = [p for _, s in series for p in s]
    if not pts:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><text x="10" y="20">no data</text></svg>'
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(0.0, min(p[1] for p in pts)), max(p[1] for p in pts)
    L, R, T, B = 70, w - 160, 40, h - 50
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif" font-size="12">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="{L}" y="22" font-size="15">{escape(title)}</text>',
        f'<line x1="{L}" y1="{B}" x2="{R}" y2="{B}" stroke="#333"/><line x1="{L}" y1="{T}" x2="{L}" y2="{B}" stroke="#333"/>',
        f'<text x="{(L + R) // 2}" y="{h - 12}" text-anchor="middle">{escape(xlabel)}</text>',
        f'<text x="16" y="{(T + B) // 2}" transform="rotate(-90 16 {(T + B) // 2})" text-anchor="middle">{escape(ylabel)}</text>',
    ]
    for i in range(5):
        yv = y0 + (y1 - y0) * i / 4
        yy = _scale(yv, y0, y1, B, T)
        out.append(f'<text x="{L - 6}" y="{yy:.1f}" text-anchor="end">{yv:.3g}</text>')
        xv = x0 + (x1 - x0) * i / 4
        xx = _scale(xv, x0, x1, L, R)
        out.append(
            f'<text x="{xx:.1f}" y="{B + 16}" text-anchor="middle">{xv:.4g}</text>'
        )
    for idx, (name, s) in enumerate(series):
        color = PALETTE[idx % len(PALETTE)]
        coords = [(_scale(x, x0, x1, L, R), _scale(y, y0, y1, B, T)) for x, y in s]
        if scatter:
            out += [
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="1.6" fill="{color}" fill-opacity="0.35"/>'
                for cx, cy in coords
            ]
        elif coords:
            path = " ".join(f"{cx:.1f},{cy:.1f}" for cx, cy in coords)
            out.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="1.6" points="{path}"/>'
            )
        out.append(
            f'<rect x="{R + 14}" y="{T + 18 * idx}" width="12" height="12" fill="{color}"/>'
        )
        out.append(f'<text x="{R + 32}" y="{T + 10 + 18 * idx}">{escape(name)}</text>')
    out.append("</svg>")
    return "\n".join(out)
