---
name: diagramming
description: "Create diagrams: architecture SVGs, hand-drawn Excalidraw, infographics, flowcharts."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [diagrams, architecture, excalidraw, infographic, flowcharts, visualization, SVG, HTML]
---

# Diagramming

Create visual diagrams, charts, and infographics. Three subskills cover different diagram types and output formats.

## Choosing the Right Approach

| Need | Subskill | Output format |
|------|----------|---------------|
| **Architecture / infrastructure diagrams** (cloud, microservices, system design) | `skill_view(name="architecture-diagram")` | Dark-themed standalone HTML with inline SVG |
| **Hand-drawn style diagrams** (flowcharts, sequence diagrams, concept maps) | `skill_view(name="excalidraw")` | `.excalidraw` JSON (opens at excalidraw.com) |
| **Infographics** (visual summaries, data stories, information graphics) | `skill_view(name="baoyu-infographic")` | Generated image via AI (21 layouts × 21 styles) |

## Quick Decision Flow

```
User wants a diagram of...
├── Software system / cloud infra / microservices → architecture-diagram
├── Flowchart / sequence / concept map / whiteboard style → excalidraw
├── Visual summary / infographic / data story → baoyu-infographic
└── Interactive generative art → see p5js skill instead
```

## Format Comparison

| Aspect | architecture-diagram | excalidraw | baoyu-infographic |
|--------|---------------------|------------|-------------------|
| **Style** | Dark, tech, grid-backed | Hand-drawn, whiteboard | 21 styles (handmade, cyberpunk, chalkboard, etc.) |
| **Output** | Self-contained HTML | .excalidraw JSON | PNG image |
| **Editable** | Edit HTML source | Open in excalidraw.com | Re-generate with different params |
| **Best for** | System architecture | General diagrams | Visual summaries of content |
| **No dependencies** | ✅ | ✅ | Requires image generation tool |

## Common Principles

1. **Label everything** — unlabeled boxes and arrows are useless
2. **Consistent visual language** — same colors/styles for same types of components
3. **Appropriate density** — not too sparse (wasted space), not too dense (unreadable)
4. **Legend when needed** — explain color coding, line styles, abbreviations
5. **Hierarchy through visual weight** — primary elements bold, secondary muted
