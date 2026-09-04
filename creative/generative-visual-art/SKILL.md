---
name: generative-visual-art
description: "Code-based visual art production: p5.js, Manim, ASCII video, Pretext text art."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [generative-art, creative-coding, p5js, manim, ascii-video, pretext, animation, visualization]
---

# Generative Visual Art

Production pipelines for code-based visual art. Each subskill is a complete, self-contained production system with its own creative standards, references, and implementation patterns. All share the same philosophy: first-render excellence, cohesive aesthetics, dense layered output.

## Choosing the Right Tool

| Need | Subskill | Stack |
|------|----------|-------|
| **Interactive generative art** (particles, noise, shaders, canvas) | `skill_view(name="p5js")` | p5.js in browser HTML |
| **Math/algorithm explainers** (3Blue1Brown style) | `skill_view(name="manim-video")` | Manim CE Python → MP4 |
| **ASCII art video** (text-based video, audio visualizers) | `skill_view(name="ascii-video")` | Python + NumPy + ffmpeg |
| **Text-as-geometry demos** (text flowing around shapes, kinetic type) | `skill_view(name="pretext")` | @chenglou/pretext in browser |

## Quick Decision Flow

```
User wants visual art that is...
├── Interactive / browser-based / generative → p5js
├── Educational / mathematical / algorithmic → manim-video
├── Text/ASCII character-based video → ascii-video
├── Text flowing around obstacles / kinetic typography → pretext
├── Image generation (Stable Diffusion, Flux) → see comfyui skill
└── Static ASCII art (banners, cowsay) → see ascii-art skill
```

## Shared Creative Standards

All subskills enforce these principles:

1. **Articulate the creative concept before coding** — mood, color world, motion vocabulary, what makes THIS unique
2. **First-render excellence** — output must be visually striking without revision rounds
3. **Cohesive aesthetic** — all elements serve a unified visual language (shared color temperature, consistent motion vocabulary)
4. **Dense, layered, considered** — every frame should reward viewing; never flat backgrounds
5. **Go beyond the catalog** — the references are vocabulary, not a menu; combine, modify, invent
6. **Include one unexpected detail** — at least one visual moment the user didn't ask for but will appreciate

## Format Comparison

| Aspect | p5js | manim-video | ascii-video | pretext |
|--------|------|-------------|-------------|---------|
| **Output** | HTML/GIF/MP4/PNG | MP4 | MP4/GIF | HTML |
| **Language** | JavaScript | Python | Python | JavaScript |
| **GPU required** | No | No | No | No |
| **Interaction** | Mouse/keyboard/touch | None (rendered) | None (rendered) | Mouse/touch |
| **Render time** | Real-time (60fps) | 5-120s/scene | 100-200ms/frame | Real-time (60fps) |
| **Resolution** | Up to 3840×2160 | Up to 1920×1080@60fps | Up to 1920×1080 | Browser viewport |
| **References** | 10 ref files + templates | 14 ref files + scripts | 8 ref files | 1 ref + templates |
