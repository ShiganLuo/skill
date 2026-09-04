# Pitfalls: Document Naming, Technical Writing, No-Root Deploy, sed Insert

## `sed` Insert Pitfall

Using `sed -i 'Na\\...'` for multi-line inserts often corrupts syntax (misplaced braces, wrong indentation). Prefer Python script or `write_file` for inserting blocks into structured files (TypeScript, Vue SFC). `sed` is fine for single-line replacements only.

**Real incident**: Used `sed -i` to insert a route object into `router/index.ts`. Result: `Expected identifier but found "{"` — the array syntax was broken (missing comma between objects). Fix: use Python to do precise replacement.

## Document Naming: Project-Specific, Not Generic

User explicitly corrected: "项目不是博客" (the project is not a blog). When creating technical documentation:
- Use `docs/tech/` NOT `docs/blog/` — even if the docs contain blog-style articles
- The directory name should reflect the PROJECT's purpose, not the document format
- A bioinformatics platform's docs go in `docs/tech/`, a blog project's go in `docs/blog/`

## Technical Writing: Don't State the Obvious

When writing technical docs comparing approaches, don't include detailed comparisons when the result is obvious. User said: "不需要单独比较,结果很明显" (don't compare separately, the result is obvious).

Rule: If one approach is clearly better for the use case, just explain WHY you chose it. Don't write a comparison table showing SSE vs WebSocket when SSE is the obvious choice for LLM streaming. The comparison wastes the reader's time.

## No-Root Deployment (University/Shared Servers)

When the user has no sudo AND no Docker, everything runs in user space:
- Install JDK in `~/jdk/` via tar.gz download
- Build JAR locally, scp to server, run with `java -jar`
- Use `nohup` or systemd user service (`~/.config/systemd/user/`)
- For frontend: serve with Node.js (e.g., `serve` package) or nginx in user space
- MySQL/Redis: must be available remotely (shared or managed service)

Never suggest `apt install`, `docker run`, or any root-requiring commands in this scenario.
