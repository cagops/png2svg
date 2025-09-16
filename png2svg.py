#!/usr/bin/env python3

import argparse, base64, colorsys, io, random, re, subprocess, sys
from math import atan2, ceil
from pathlib import Path

import numpy as np
from PIL import Image
import svgwrite

# ————— user‑tunable defaults ————————————————————————————————
DEF_LUMA_TH = 60  # ≤  → “nearly black”
DEF_ALPHA_TH = 5
DEF_OUTLINE_W = 6  # px
DEF_FILL_FACTOR = 0.6  # 0‑1 × min(w,h) → stroke width
DEF_FILL_LINES = 3  # strokes per blob
DEF_FILL_JITTER = 0.3  # 0‑1 relative to stroke width
DEF_PALETTE_K = 20  # hue bins  (genuine hues ≈ 12)
POTRACE_CMD = "potrace"
random.seed(0)
# ————————————————————————————————————————————————————————————————


# ---------- Potrace wrapper (pixel‑accurate) -----------------------------
def potrace_paths(mask_bw: Image.Image):
    if mask_bw.mode != "1":
        mask_bw = mask_bw.convert("1")
    buf = io.BytesIO()
    mask_bw.save(buf, format="PPM")
    proc = subprocess.run(
        [POTRACE_CMD, "--svg", "--flat", "--invert", "--unit", "1", "--output", "-"],
        input=buf.getvalue(),
        stdout=subprocess.PIPE,
        check=True,
    )
    return [
        " ".join(d.split())
        for d in re.findall(
            r'<path[^>]*?\sd="([^"]+)"',
            proc.stdout.decode("utf‑8", "replace"),
            flags=re.DOTALL,
        )
    ]


# ---------- embed PNG ----------------------------------------------------
def data_uri(p: Path):
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


# ---------- bounding boxes (4‑conn. flood) -------------------------------
def blobs(mask: np.ndarray):
    h, w = mask.shape
    vis = np.zeros_like(mask, bool)
    out = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not vis[y, x]:
                minx = maxx = x
                miny = maxy = y
                stack = [(y, x)]
                vis[y, x] = True
                while stack:
                    cy, cx = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if (
                            0 <= ny < h
                            and 0 <= nx < w
                            and mask[ny, nx]
                            and not vis[ny, nx]
                        ):
                            vis[ny, nx] = True
                            stack.append((ny, nx))
                            minx, miny = min(minx, nx), min(miny, ny)
                            maxx, maxy = max(maxx, nx), max(maxy, ny)
                out.append((minx, maxx, miny, maxy))
    return out


# ---------- build SVG ----------------------------------------------------
def build_svg(w, h, href_png, guides1, guides2):
    dwg = svgwrite.Drawing(profile="tiny", size=(w, h))
    dwg.viewbox(0, 0, w, h)
    dwg.add(dwg.image(href=href_png, insert=(0, 0), size=(w, h)))
    flip = f"matrix(1 0 0 -1 0 {h})"
    g = dwg.g(transform=flip)

    for d, sw in guides1:  # dark phase
        g.add(
            dwg.path(
                d=d,
                fill="none",
                stroke="#000",
                stroke_width=sw,
                stroke_linecap="round",
                stroke_linejoin="round",
                stroke_opacity=0.0,
            )
        )
    for d, sw in guides2:  # colour phases
        g.add(
            dwg.path(
                d=d,
                fill="none",
                stroke="#000",
                stroke_width=sw,
                stroke_linecap="butt",
                stroke_opacity=0.0,
            )
        )
    dwg.add(g)
    return dwg


# ---------- main converter -----------------------------------------------
def convert(png: Path, out: Path, a):
    img = Image.open(png).convert("RGBA")
    w, h = img.size
    arr = np.array(img)
    alpha = arr[..., 3] > a.alpha_th
    if not alpha.any():
        print("skip", png.name)
        return

    # stage 1 – dark contour
    luma = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    dark = (luma <= a.luma_th) & alpha
    guides_dark = [
        (d, a.outline_w)
        for d in potrace_paths(Image.fromarray(dark.astype(np.uint8) * 255))
    ]

    # stage 2 – colour markers, hue‑sorted
    rgb = arr[..., :3]
    hsv = np.apply_along_axis(lambda v: colorsys.rgb_to_hsv(*(v / 255)), 2, rgb)
    hue = (hsv[..., 0] * 360).astype(int)
    hue_bin = (hue // (360 // a.palette_k)).clip(0, a.palette_k - 1)
    colour = alpha & ~dark
    guides_colour = []

    for bin_idx in sorted(set(hue_bin[colour])):
        mask_bin = colour & (hue_bin == bin_idx)
        for minx, maxx, miny, maxy in blobs(mask_bin):
            bw, bh = maxx - minx + 1, maxy - miny + 1
            sw = int(min(bw, bh) * a.fill_factor)
            sw = max(sw, 3)
            # orientation decision
            if bw > bh * 1.3:
                orient = "vertical"
            elif bh > bw * 1.3:
                orient = "horizontal"
            else:
                orient = "diag"
            n = max(
                1,
                min(
                    a.fill_lines,
                    ceil((bh if orient != "vertical" else bw) / (sw * 1.3)),
                ),
            )
            for i in range(n):
                jitter = random.uniform(-a.fill_jitter, a.fill_jitter) * sw
                if orient == "horizontal":
                    y = miny + (i + 0.5) * bh / n + jitter
                    d = f"M{minx+0.5:.2f} {h-y:.2f} L{maxx-0.5:.2f} {h-y:.2f}"
                elif orient == "vertical":
                    x = minx + (i + 0.5) * bw / n + jitter
                    d = f"M{x:.2f} {h-(miny+0.5):.2f} L{x:.2f} {h-(maxy-0.5):.2f}"
                else:  # gentle diagonal NW‑SE
                    t = (i + 0.5) / n
                    x1 = minx + 0.5
                    y1 = maxy - t * bh
                    x2 = minx + t * bw
                    y2 = maxy - 0.5
                    d = f"M{x1:.2f} {h-y1:.2f} L{x2:.2f} {h-y2:.2f}"
                guides_colour.append((d, sw))

    build_svg(w, h, data_uri(png), guides_dark, guides_colour).saveas(out)
    print("✓", png.name, "→", out.relative_to(out.parent.parent))


# ---------- CLI ----------------------------------------------------------
def main():
    ap = argparse.ArgumentParser("SVG: dark first, colour hue‑by‑hue")
    ap.add_argument("-i", "--input", required=True)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--luma-th", type=int, default=DEF_LUMA_TH)
    ap.add_argument("--alpha-th", type=int, default=DEF_ALPHA_TH)
    ap.add_argument("--outline-w", type=int, default=DEF_OUTLINE_W)
    ap.add_argument("--fill-factor", type=float, default=DEF_FILL_FACTOR)
    ap.add_argument("--fill-lines", type=int, default=DEF_FILL_LINES)
    ap.add_argument("--fill-jitter", type=float, default=DEF_FILL_JITTER)
    ap.add_argument(
        "--palette-k",
        type=int,
        default=DEF_PALETTE_K,
        help="number of hue buckets (colour order)",
    )
    args = ap.parse_args()

    in_dir, out_dir = Path(args.input), Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in sorted(in_dir.glob("*.png")):
        try:
            convert(p, out_dir / f"{p.stem}.svg", args)
        except Exception as e:
            print("[ERR]", p.name, e, file=sys.stderr)


if __name__ == "__main__":
    main()
