---
name: audio-music
description: "Music and audio: songwriting craft, AI music generation, audio analysis and visualization."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [music, audio, songwriting, ai-music, spectrogram, analysis, visualization, suno, heartmula]
---

# Audio & Music

Create, analyze, and visualize music and audio. Two subskills cover the creative and analytical sides of audio work.

## Choosing the Right Approach

| Need | Subskill | What you get |
|------|----------|--------------|
| **Write songs / generate music** (lyrics, Suno prompts, HeartMuLa, parody) | `skill_view(name="songwriting-and-ai-music")` | Songwriting craft, AI music generation, open-source music tools |
| **Analyze / visualize audio** (spectrograms, mel, chroma, MFCC) | `skill_view(name="songsee")` | Audio feature visualization via CLI |

## Quick Decision Flow

```
User wants to...
├── Write song lyrics / compose → songwriting-and-ai-music
├── Generate music with AI (Suno, HeartMuLa) → songwriting-and-ai-music
├── Create a parody / adapt existing song → songwriting-and-ai-music
├── See a spectrogram / analyze audio features → songsee
├── Compare audio files visually → songsee
└── Generate audio from text descriptions → see audiocraft-audio-generation skill
```

## Related Skills

- **`audiocraft-audio-generation`** — MusicGen text-to-music, AudioGen text-to-sound (ML model-based)
- **`ascii-video`** — ASCII art music visualizers (video output from audio input)
- **`comfyui`** — Audio generation via ComfyUI workflows
