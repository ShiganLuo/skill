# Vue3 Favicon Unification Procedure

## Problem

Multi-project Vue3 setups (front + back + backend) end up with different favicon files and references. Each project scaffolded independently gets its own favicon in different locations with different formats.

## Procedure

### 1. Create SVG favicon

Place in BOTH `public/` directories. Use the project's `--primary` CSS variable color. Example for a blog with primary `#5D87FF`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#5D87FF"/>
      <stop offset="100%" style="stop-color:#4A6FE0"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="14" fill="url(#bg)"/>
  <!-- App-specific icon here -->
</svg>
```

Why SVG: scales to all sizes, crisp on retina, tiny file, no need for multiple sizes.

### 2. Update both index.html files

Replace any existing favicon link with:
```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
```

Remove old references — do NOT leave stale `favicon.ico` or `favicon.png` links alongside.

### 3. Handle missing public/ directory

Back-end projects (especially admin panels scaffolded from templates) may not have `public/`. Vite requires it for static assets.

```bash
mkdir -p <back-end>/public
cp <front-end>/public/favicon.svg <back-end>/public/favicon.svg
```

### 4. Verify

```bash
# Files identical
diff -q front/public/favicon.svg back/public/favicon.svg

# Valid SVG
xmllint --noout front/public/favicon.svg

# Both referenced
grep 'favicon.svg' front/index.html back/index.html

# Old refs gone
! grep -q 'favicon.ico\|favicon.png' front/index.html back/index.html
```

## Dynamic Favicon Override

Both projects likely have `setFavicon()` in `app-init.ts` that loads favicon URL from API and replaces the static one at runtime. The SVG serves as the fallback for:
- First visit before API response
- API failure
- Static rendering / crawlers

### 5. Generate ICO fallback for RSS/XML pages

RSS pages are XML, NOT HTML — browsers do NOT parse `<link rel="icon">`. They fall back to `/favicon.ico` at the domain root. Without an ICO, RSS pages show the default browser icon (or Vue's scaffold icon).

Generate ICO from SVG using Python (cairosvg + Pillow):

```bash
pip3 install cairosvg Pillow

python3 -c "
import cairosvg
from PIL import Image

# SVG → PNG at 16 and 32
cairosvg.svg2png(url='public/favicon.svg', write_to='/tmp/f16.png', output_width=16, output_height=16)
cairosvg.svg2png(url='public/favicon.svg', write_to='/tmp/f32.png', output_width=32, output_height=32)

# PNGs → ICO with both sizes
img16, img32 = Image.open('/tmp/f16.png'), Image.open('/tmp/f32.png')
img32.save('public/favicon.ico', format='ICO', sizes=[(16,16),(32,32)], append_images=[img16])
"
```

Copy to both projects:
```bash
cp front/public/favicon.ico back/public/favicon.ico
```

Verify: `file public/favicon.ico` should show "2 icons, 16x16 ... 32x32".

### 6. Verify complete setup

```bash
# SVG identical across projects
diff -q front/public/favicon.svg back/public/favicon.svg

# ICO identical and has both sizes
diff -q front/public/favicon.ico back/public/favicon.ico
file front/public/favicon.ico | grep "2 icons"

# index.html references SVG (not ICO)
grep 'favicon.svg' front/index.html back/index.html

# Old asset-path refs gone
! grep -q 'favicon.ico\|favicon.png' front/index.html back/index.html
```

## Common Pitfalls

- Using `src/assets/` path in `index.html` — works in dev but breaks in production builds. Always use `/favicon.svg` (root-relative, served from `public/`).
- **SVG-only without ICO** — RSS/XML feeds, some crawlers, and older browsers don't support SVG favicons. Always maintain both `favicon.svg` (for HTML `<link>`) AND `favicon.ico` (fallback at `/favicon.ico`).
- Different favicons for front vs back — confusing for users with multiple tabs open.
- **RSS page shows Vue icon** — means `public/favicon.ico` is still the scaffold default. Regenerate from your SVG (step 5 above).
