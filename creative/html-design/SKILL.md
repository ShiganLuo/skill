---
name: html-design
description: "Design HTML artifacts: prototypes, decks, landing pages, design systems, token specs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [design, html, prototype, ux, ui, creative, design-system, tokens, css, mockup]
---

# HTML Design

Create HTML design artifacts — from quick throwaway mockups to polished prototypes, from brand-matched pages to formal design-token specs. Four subskills cover the full design spectrum.

## Choosing the Right Approach

| Need | Subskill | What you get |
|------|----------|--------------|
| **Design process & taste** for a from-scratch artifact | `skill_view(name="claude-design")` | How to scope a brief, gather context, produce variants, avoid AI-design slop |
| **Match a known brand's look** (Stripe, Linear, Vercel, etc.) | `skill_view(name="popular-web-designs")` | 54 ready-to-paste design systems with exact CSS values |
| **Author a formal DESIGN.md token spec** | `skill_view(name="design-md")` | Google's DESIGN.md spec format — machine-readable tokens + rationale |
| **Quick throwaway mockups** to compare directions | `skill_view(name="sketch")` | 2-3 interactive HTML variants side-by-side |

These compose: use `popular-web-designs` for visual vocabulary, `claude-design` for process, `sketch` for rapid exploration, and `design-md` when the deliverable is a token file.

## Quick Decision Flow

```
User wants a...
├── Polished one-off artifact (landing, deck, prototype) → claude-design
├── Page that looks like [brand] → popular-web-designs (+ claude-design for process)
├── Quick "show me 2-3 directions" → sketch
├── Formal design-system spec file → design-md
└── Diagram (not a web page) → see diagramming skill instead
```

## Common Principles (All Approaches)

1. **Start from context, not vibes** — read brand docs, repo files, screenshots before inventing UI
2. **Self-contained HTML** — inline CSS/JS, no build step, openable directly in a browser
3. **Realistic content** — actual sentences, actual names, never lorem ipsum
4. **Verify visually** — open in browser, check for rendering issues before shipping
5. **Avoid AI design slop** — no aggressive gradients, glassmorphism by default, emoji decoration, generic SaaS cards, or fake dashboards with arbitrary numbers

## Related Skills

- **`architecture-diagram`** — dark-themed SVG architecture/infra diagrams (not web pages)
- **`excalidraw`** — hand-drawn diagram JSON files
- **`p5js`** — interactive generative art (not design artifacts)
