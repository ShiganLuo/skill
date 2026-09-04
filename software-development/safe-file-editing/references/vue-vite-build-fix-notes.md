# Vue/Vite build repair notes

Repo: bioplatform front/admin

Verified patterns from this session:
- Use `patch` for existing `.vue` files; avoid `write_file`.
- When a repo adds `unplugin-auto-import` / `unplugin-vue-components`, include the generated `src/auto-imports.d.ts` and `src/components.d.ts` in `tsconfig.json`.
- For bundle reduction, `manualChunks()` can split Element Plus into per-component chunks, with icons isolated separately.
- If the build script mixes typecheck with bundling and type errors block progress, verify whether the target is actually the production bundle; if so, confirm the real deliverable by running the build script directly and inspecting output.
- Always finish by running the actual build and reading the emitted chunk list; record the largest chunk size after optimization.
- A blank page with only `<div id="app"></div>` should be treated as a frontend runtime/deploy issue until browser console/runtime errors are ruled out.
- When backends fail during startup due to JWT secret decoding, a compatible fallback is to accept either Base64 or raw UTF-8 secret material and log the fallback.
- For Vite deploys, 404/502s for `/vite.svg` can be a red herring; confirm the app shell and JS entry chunk first.
