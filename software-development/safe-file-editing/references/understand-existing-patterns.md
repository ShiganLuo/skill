# Understand Existing Code Before Modifying

## The Rule

**ALWAYS investigate the existing codebase's patterns BEFORE proposing changes.**

The user's exact words: "你要理解原本项目的对于图片的处理逻辑"
(You need to understand the original project's image handling logic)

## What Happened

Session was asked to fix editor image upload. Agent:
1. Assumed images were stored as full URLs
2. Created `imageUrl.ts` utility with `resolveImageUrl`, `toRelativePath`
3. Added `VITE_MINIO_URL` env var to all .env files
4. Modified 6+ files to use `resolveImageUrl()` for display
5. Added `filePath` field to backend `ImageResponse` DTO

Reality: The project ALREADY stored relative paths in the database.
All the new utilities were unnecessary. The only real fix needed was
WangEditor's `customUpload` response parsing.

## Checklist Before Modifying Image/URL Handling

1. **Check the database first**: `SELECT * FROM table LIMIT 5` — what format is actually stored?
2. **Check the backend response**: What does the API actually return? (imageUrl vs filePath)
3. **Check existing display code**: How do other components render the same data type?
4. **Check env vars**: Are there existing base URL configs?
5. Only add new utilities if there's a GENUINE gap

## General Principle

When the user says "fix X", don't refactor Y and Z along the way.
- Fix the reported issue
- Don't "improve" adjacent code unless asked
- Don't add abstractions for problems that don't exist yet
