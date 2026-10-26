---
name: git-history-rewriting
description: "Remove files/dirs from all git history with filter-repo."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Git, History, filter-repo, BFG, Security, Cleanup]
    related_skills: [github-repo-management, github-auth]
---

# Git History Rewriting

Remove files, directories, secrets, or patterns from **all** git history using `git-filter-repo` (preferred) or BFG Repo-Cleaner.

## When to Use

- User asks to remove a file/directory from git history
- Need to purge secrets, credentials, or large blobs from all commits
- Cleaning up accidentally committed build artifacts, caches, or data files

## Prerequisites

```bash
pip install git-filter-repo
git filter-repo --version
```

## 1. Remove a Path from History

```bash
# Remove a directory from all commits
git filter-repo --path modules/old_module --invert-paths --force

# Remove a specific file
git filter-repo --path src/secret.env --invert-paths --force

# Remove by glob pattern
git filter-repo --path-glob '*.bak' --invert-paths --force

# Remove multiple paths
git filter-repo --path dir1/ --path dir2/file.txt --invert-paths --force
```

## 2. Strip Large Files

```bash
git filter-repo --strip-blobs-bigger-than 10M
git filter-repo --path data/ --invert-paths --strip-blobs-bigger-than 5M
```

## 3. Replace Text (e.g. secrets)

```bash
echo 'AKIA12345==>REDACTED_SECRET' > /tmp/expressions.txt
git filter-repo --replace-text /tmp/expressions.txt
```

## Post-Operation Checklist

After **every** filter-repo run:

```bash
# 1. Re-add remotes (filter-repo removes them by design)
git remote add origin git@github.com:OWNER/REPO.git

# 2. Verify the path is gone
git log --all --oneline -- path/removed    # should return empty

# 3. Confirm clean state
git status

# 4. Force-push (history diverged)
git push --force origin main
```

## Pitfalls

### P1: `already_ran` blocks non-interactive runs
`.git/filter-repo/already_ran` causes interactive Y/N prompt → `EOFError` in agents.
```bash
rm -f .git/filter-repo/already_ran
```

### P2: `origin` remote removed by design
filter-repo strips all remotes. Always re-add after.

### P3: Force-push required
`git push --force` needed. Coordinate with collaborators.

### P4: Shallow clones
filter-repo requires full history:
```bash
git fetch --unshallow
```

## BFG Repo-Cleaner (Alternative)

```bash
java -jar bfg.jar --delete-files secret.env repo.git
java -jar bfg.jar --strip-blobs-bigger-than 10M repo.git
cd repo.git && git reflog expire --expire=now --all && git gc --prune=now --aggressive
```
BFG requires bare clone; filter-repo works on both.