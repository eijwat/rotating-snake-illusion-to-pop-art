"""
Rotating Snake Pop Art Generator

Usage:
  python3 pop_art_illusion.py
  python3 pop_art_illusion.py --input myimage.jpg
  python3 pop_art_illusion.py --cols 4 --rows 3
  python3 pop_art_illusion.py --border 20 --bg black
  python3 pop_art_illusion.py --border 10 --bg "#ff00ff"
  python3 pop_art_illusion.py --seed 42   # use to reproduce a specific result
"""

import numpy as np
from PIL import Image
import random
import colorsys
import argparse
import os
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description='Rotating Snake Pop Art Generator')
    parser.add_argument('--input',  default='RS.jpg',
                        help='Source image path (default: RS.jpg)')
    parser.add_argument('--output', default=None,
                        help='Output path (default: timestamped filename in current directory)')
    parser.add_argument('--cols',   type=int, default=3,
                        help='Number of columns (default: 3)')
    parser.add_argument('--rows',   type=int, default=2,
                        help='Number of rows (default: 2)')
    parser.add_argument('--border', type=int, default=0,
                        help='Gap between cells in pixels (default: 0 = seamless)')
    parser.add_argument('--bg',     default='white',
                        help='Gap/background color: white / black / #RRGGBB (default: white)')
    parser.add_argument('--size',   type=int, default=400,
                        help='Cell size in pixels (default: 400)')
    parser.add_argument('--seed',   type=int, default=None,
                        help='Random seed (omit for a new result every run)')
    return parser.parse_args()


def parse_color(s):
    s = s.strip().lower()
    if s == 'white': return (255, 255, 255)
    if s == 'black': return (0, 0, 0)
    if s.startswith('#'):
        h = s.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    raise ValueError(f"Invalid color: '{s}'  (use white / black / #RRGGBB)")


def analyze_colors(img_array):
    """Detect the four key colors in the source image."""
    pixels     = img_array.reshape(-1, 3).astype(np.float32)
    brightness = pixels.mean(axis=1)
    white_mask = brightness > 200
    black_mask = brightness < 50
    mid_pixels = pixels[~white_mask & ~black_mask]

    if len(mid_pixels) > 0:
        blue_m = (mid_pixels[:, 2] > mid_pixels[:, 0]) & (mid_pixels[:, 2] > mid_pixels[:, 1])
        blue_c = mid_pixels[blue_m].mean(axis=0)   if blue_m.any()   else np.array([0, 100, 200])
        yell_c = mid_pixels[~blue_m].mean(axis=0)  if (~blue_m).any() else np.array([200, 230, 0])
    else:
        blue_c = np.array([0, 100, 200])
        yell_c = np.array([200, 230, 0])

    return {
        'white':  pixels[white_mask].mean(axis=0).astype(np.uint8) if white_mask.any() else np.array([255,255,255], dtype=np.uint8),
        'black':  pixels[black_mask].mean(axis=0).astype(np.uint8) if black_mask.any()  else np.array([20, 20, 20],  dtype=np.uint8),
        'blue':   blue_c.astype(np.uint8),
        'yellow': yell_c.astype(np.uint8),
    }


def random_palette():
    """Generate a vivid pop-art palette by sampling well-separated hues in HSV space."""
    def hsv(h, s, v):
        r, g, b = colorsys.hsv_to_rgb(h/360, s, v)
        return np.array([int(r*255), int(g*255), int(b*255)], dtype=np.uint8)
    hues   = random.sample(range(0, 360, 15), 4)
    white  = hsv(hues[0], random.uniform(0.05, 0.25), random.uniform(0.90, 1.0))
    color1 = hsv(hues[1], random.uniform(0.7,  1.0),  random.uniform(0.8,  1.0))
    color2 = hsv(hues[2], random.uniform(0.7,  1.0),  random.uniform(0.8,  1.0))
    black  = np.array([10, 10, 10], dtype=np.uint8)
    return {'white': white, 'black': black, 'blue': color1, 'yellow': color2}


def recolor_image(img_array, original_colors, new_palette):
    """Remap each pixel to its nearest original color, then substitute with the new palette."""
    h, w    = img_array.shape[:2]
    pixels  = img_array.reshape(-1, 3).astype(np.int32)
    orig    = np.array([original_colors[k].astype(np.int32) for k in ('white','black','blue','yellow')])
    new     = np.array([new_palette[k].astype(np.uint8)     for k in ('white','black','blue','yellow')])
    dists   = np.sum((pixels[:, np.newaxis, :] - orig[np.newaxis, :, :]) ** 2, axis=2)
    nearest = np.argmin(dists, axis=1)
    return new[nearest].reshape(h, w, 3).astype(np.uint8)


def main():
    args = parse_args()

    # Set random seed (generate one if not specified, for reproducibility)
    seed = args.seed if args.seed is not None else random.randint(0, 2**31)
    random.seed(seed)
    np.random.seed(seed)
    print(f"Random seed: {seed}  (to reproduce, use --seed {seed})")

    COLS       = args.cols
    ROWS       = args.rows
    CELL_SIZE  = args.size
    BORDER     = args.border
    BACKGROUND = parse_color(args.bg)
    N_CELLS    = COLS * ROWS

    # Output path: timestamped filename in current directory if not specified
    timestamp   = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = args.output if args.output else f'pop_art_{timestamp}.png'

    print(f"Settings: grid={COLS}x{ROWS}, cell={CELL_SIZE}px, border={BORDER}px, bg={BACKGROUND}")

    print("\nLoading source image...")
    orig_img   = Image.open(args.input).convert('RGB')
    orig_img   = orig_img.resize((CELL_SIZE, CELL_SIZE), Image.LANCZOS)
    orig_array = np.array(orig_img)

    print("Analyzing source colors...")
    original_colors = analyze_colors(orig_array)
    for k, v in original_colors.items():
        print(f"  {k}: {v}")

    # Generate all cell variants with independent random palettes.
    # Grid follows a checkerboard pattern: (row+col) even → RS, odd → RS-M (mirrored).
    print(f"\nGenerating {N_CELLS} color variants (all independent)...")

    n_rs  = sum(1 for r in range(ROWS) for c in range(COLS) if (r + c) % 2 == 0)
    n_rsm = sum(1 for r in range(ROWS) for c in range(COLS) if (r + c) % 2 == 1)

    rs_variants = []
    for i in range(n_rs):
        p = random_palette()
        rs_variants.append(recolor_image(orig_array, original_colors, p))
        print(f"  RS   {i+1}: white={p['white']}, c1={p['blue']}, c2={p['yellow']}")

    rsm_variants = []
    for i in range(n_rsm):
        p = random_palette()
        rsm_variants.append(np.fliplr(recolor_image(orig_array, original_colors, p)))
        print(f"  RS-M {i+1}: white={p['white']}, c1={p['blue']}, c2={p['yellow']}")

    # Shuffle placement order randomly
    random.shuffle(rs_variants)
    random.shuffle(rsm_variants)

    print("\nComposing grid...")
    rs_iter  = iter(rs_variants)
    rsm_iter = iter(rsm_variants)

    grid = [[None] * COLS for _ in range(ROWS)]
    for r in range(ROWS):
        for c in range(COLS):
            grid[r][c] = next(rs_iter) if (r + c) % 2 == 0 else next(rsm_iter)

    # Assemble canvas
    total_w = CELL_SIZE * COLS + BORDER * (COLS + 1)
    total_h = CELL_SIZE * ROWS + BORDER * (ROWS + 1)
    canvas  = np.full((total_h, total_w, 3), BACKGROUND, dtype=np.uint8)

    for r in range(ROWS):
        for c in range(COLS):
            y0 = BORDER + r * (CELL_SIZE + BORDER)
            x0 = BORDER + c * (CELL_SIZE + BORDER)
            canvas[y0:y0+CELL_SIZE, x0:x0+CELL_SIZE] = grid[r][c]

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(canvas).save(output_path, quality=95)
    print(f"\nDone! Saved to: {output_path}  ({total_w}x{total_h}px)")


if __name__ == '__main__':
    main()
