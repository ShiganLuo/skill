#!/usr/bin/env bash
# Compute the REAL translation progress by cross-referencing three sources.
# Do NOT trust _translation_progress.md's header counts or [x] markers —
# they lag reality. Canonical: bib ∩ Obsidian files = done.
#
# Usage:
#   bash scripts/translation-status.sh                 # default paths
#   BIB=/path/to.bib NOTES_DIR=/path bash scripts/translation-status.sh
#
# Env overrides:
#   BIB          — Zotero bibliography (default: ~/Work/luosg/Zotero/My Library.bib)
#   NOTES_DIR    — Obsidian literature dir  (default: ~/Work/luosg/work/笔记/Wiki/文献阅读笔记/文献)
#   PROG         — progress file           (default: $NOTES_DIR/../_translation_progress.md)
#   TMPDIR       — scratch space for sort output

set -u

BIB="${BIB:-/home/luosg/Work/luosg/Zotero/My Library.bib}"
NOTES_DIR="${NOTES_DIR:-/home/luosg/Work/luosg/work/笔记/Wiki/文献阅读笔记/文献}"
PROG="${PROG:-${NOTES_DIR%/*}/_translation_progress.md}"
TMPDIR="${TMPDIR:-/tmp}"

if [ ! -f "$BIB" ]; then
    echo "ERROR: bib not found: $BIB" >&2
    exit 2
fi
if [ ! -d "$NOTES_DIR" ]; then
    echo "ERROR: notes dir not found: $NOTES_DIR" >&2
    exit 2
fi

# bib citekeys: @entry{ck,  → ck
grep -E '^@\w+\{' "$BIB" | sed -E 's/^@\w+\{//; s/,$//' | sort -u > "$TMPDIR/ts_zotero.txt"

# Obsidian @ck.md → ck (dedup, skip _Attachments subdirs and non-md files)
ls "$NOTES_DIR"/@*.md 2>/dev/null \
    | xargs -n1 basename 2>/dev/null \
    | sed -E 's/^@//; s/\.md$//' \
    | sort -u > "$TMPDIR/ts_obsidian.txt"

# progress file [x] ck → ck (best-effort header — known to be stale)
if [ -f "$PROG" ]; then
    grep -E '^- \[x\] @' "$PROG" | sed -E 's/^- \[x\] (@[^ ]+).*/\1/' | sed 's/^@//' | sort -u > "$TMPDIR/ts_progress.txt"
else
    : > "$TMPDIR/ts_progress.txt"
fi

total=$(wc -l < "$TMPDIR/ts_zotero.txt")
done=$(comm -12 "$TMPDIR/ts_zotero.txt" "$TMPDIR/ts_obsidian.txt" | wc -l)
remaining=$(comm -23 "$TMPDIR/ts_zotero.txt" "$TMPDIR/ts_obsidian.txt" | wc -l)
orphan=$(comm -13 "$TMPDIR/ts_zotero.txt" "$TMPDIR/ts_obsidian.txt" | wc -l)
progress_marked=$(wc -l < "$TMPDIR/ts_progress.txt")
progress_truth=$(comm -12 "$TMPDIR/ts_progress.txt" "$TMPDIR/ts_obsidian.txt" | wc -l)
progress_stale=$(comm -23 "$TMPDIR/ts_progress.txt" "$TMPDIR/ts_zotero.txt" | wc -l)

cat <<EOF
=== REAL translation progress (bib vs Obsidian files) ===
  bib citekeys (corpus):      $total
  Obsidian @citekey.md files:  $(wc -l < "$TMPDIR/ts_obsidian.txt")
  translated (bib ∩ files):    $done
  remaining (bib \\ files):    $remaining
  orphan notes (files \\ bib): $orphan

=== progress file health ===
  [x] markers in _translation_progress.md:    $progress_marked
  markers that match a real .md:             $progress_truth
  markers pointing to bib-missing citekeys:  $progress_stale
  (Header counts in progress file are stale — do NOT cite them.)
EOF

if [ "$remaining" -gt 0 ]; then
    echo ""
    echo "=== Remaining citekeys (head 30) ==="
    comm -23 "$TMPDIR/ts_zotero.txt" "$TMPDIR/ts_obsidian.txt" | head -30
fi

if [ "$orphan" -gt 0 ]; then
    echo ""
    echo "=== Orphan note citekeys (head 30) — bib lost these ==="
    comm -13 "$TMPDIR/ts_zotero.txt" "$TMPDIR/ts_obsidian.txt" | head -30
fi

# cleanup intermediate files
rm -f "$TMPDIR/ts_zotero.txt" "$TMPDIR/ts_obsidian.txt" "$TMPDIR/ts_progress.txt"