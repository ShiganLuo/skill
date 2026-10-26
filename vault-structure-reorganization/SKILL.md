---
name: vault-structure-reorganization
description: "Use when reorganizing vault folders: dedupe, MOC, links."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [obsidian, notes, reorganization, links, knowledge-management]
---

# Vault Structure Reorganization

## When to Use

The task changes a note tree's **shape**: removing duplicate notes,
splitting a mixed-purpose folder into a taxonomy, converting a folder listing
into a MOC index, tagging vendored/third-party content. Not for in-place
formatting fixes (frontmatter, heading levels) — that is `note-taking/obsidian`.

## The correction that defines this class

After I merged duplicates, rebuilt the index, and edited content while leaving
the same nine top-level folders, the user wrote: **"你这目录结构是一点没变啊"**
— the approved plan had promised splitting one catch-all folder into several.

Rule: content edits and a rewritten index are **not** 整理 if the tree looks
the same. If the plan promises "split X into A/, B/", the deliverable is the
new folder structure. Report it as an explicit before → after table
(`11 顶层入口 → 6`, `系统/ 39 篇 → 消失`) so the structural change is
verifiable at a glance.

## Playbook

1. **Recon before moving.** Count `.md` per folder; list attachment dirs
   (`<note>.md_Attachments`, legacy `<note>_Attachments`); sample how images
   and links are written (vault-full path `Wiki/...`, relative
   `X_Attachments/y.png`, bare filename). The reference style determines move
   risk.

2. **Find duplicates by content, not filename.** Two identically-structured
   notes can have unrelated names:
   ```bash
   diff <(sort A.md) <(sort B.md) | grep -c '^<' || true   # 0 => A ⊆ B
   ```
   (`grep -c` exits 1 on zero and breaks `&&` chains — append `|| true`.)
   One session found four duplicate pairs; two were only discoverable by
   content diff, never by name.

3. **Split by retrievability, not subject.** Notes you must *remember*
   (symptom → root-cause walkthroughs, mechanism explanations) vs notes you
   only *look up* (command cheatsheets, vendored tutorials). Tag verified
   third-party content with frontmatter `source: 转载` (+ `type: reference`)
   so 原创/第三方 can be split by query later — only after confirming copied
   provenance (external blog headings, `主要作者 @xxx` doc headers, verbatim
   third-party prose); an external image link alone does not make a note 转载.

4. **Move notes with their attachments, then rewrite paths vault-wide.**
   Build the move list first; then replace every moved
   `VaultRoot/.../old/path` prefix with its new path in **all** `.md` files
   in the vault (longest prefixes first). Vault-full-path image embeds break
   silently otherwise.

5. **Re-resolve every link under strict rules**: path-qualified links must
   exist at exactly that path; basename links must be unique vault-wide
   (duplicate basename → full vault-root path). Strip fenced code before
   scanning or shell `[[ ... ]]` and markdown table links (`[text](url)`)
   yield false broken links. Match the vault's existing link convention —
   inspect real notes first; never introduce a path form the vault doesn't
   already use.

6. **Rollback.** Check for `.git` at the vault root before assuming history
   exists — many personal vaults are not repos. Move superseded files to a
   backup dir **outside** the vault (Obsidian indexes everything inside), and
   write `回滚清单.json` with every `old → new` pair so moves reverse cleanly.

7. **Index note = retrieval paths, not folder alphabet.** Route by the state
   the reader is in (报错 → 排查 / 忘了命令 → 速查 / 想懂机制 → 原理 / 第三方 →
   只查不记), state the review rule that follows, and demote any
   auto-generated folder-index block to an appendix.

## Verification gate (before claiming done)

One scoped script, four checks:

- strict link check (code fences stripped; path exact / basename unique)
- attachment images: vault-full paths exist, relative refs resolve against
  the note's dir, bare filenames resolve vault-wide. `../images/foo.png`
  inside vendored docs are **pre-existing dead links** from the original doc
  site — report as pre-existing, never "fix" by moving files.
- frontmatter closure after batch edits (starts `---` ⇒ closing `---` exists)
- per-folder `.md` counts + `source: 转载` total, reconciled against the
  planned taxonomy

## Pitfalls

- **Shell cwd inside a moved directory.** Once the folder the session `cd`'d
  into is moved/deleted, every later `terminal` call fails
  (`cd: ... No such file or directory`, Exit 126). Pass `workdir=` to
  `terminal` on subsequent calls instead of `cd`.
- **Delete = lose.** `mv` superseded files to the outside backup; `rm -rf`
  may be intercepted by the safety layer anyway (it fails as an empty output +
  timeout, which reads like a hang).
- **Moving a note without its attachment folder** orphans its images;
  moving both without the prefix rewrite breaks the embeds. Do it as one
  operation.
- **Frontmatter-only stubs** count as notes in every later audit — remove or
  fill them or counts never reconcile.
