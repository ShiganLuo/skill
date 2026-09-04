# Repo history artifact purge (verified pattern)

Use when a repo has already tracked generated output (`dist/`, `node_modules/`, `target/`) and the user wants both current-tree cleanup and historical removal before pushing.

Verified sequence:
1. Save a patch of source changes excluding generated trees.
2. Expand `.gitignore` to cover all generated outputs.
3. Measure tracked scope with `git ls-files` / `git ls-tree` filtered for artifact paths.
4. Create an orphan branch.
5. `git reset` to unstage inherited index.
6. `git clean -fdX` to delete ignored generated trees from the working tree.
7. `git add .` and verify staged files contain no `dist/`, `node_modules/`, or `target/` paths.
8. Commit the clean tree.
9. Rename branch back to `main` if needed.
10. Verify `git ls-tree -r --name-only HEAD` has zero generated-artifact matches.
11. Force-push (`--force-with-lease`) to rewrite remote history.

Why this is useful:
- Fast when the repo history is trivial or the user explicitly accepts a full rewrite.
- Avoids fighting thousands of tracked generated files individually.
- Produces a clean root snapshot with only source and config files.

Cautions:
- This rewrites history; do it only when the user explicitly asked to remove artifacts from git history / remote history.
- Save source changes first; `git clean -fdX` deletes ignored untracked files.
- Re-verify after the commit, not just before.
