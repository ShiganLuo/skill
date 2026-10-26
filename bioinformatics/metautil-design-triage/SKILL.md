---
name: metautil-design-triage
description: Use when Omics DESeq2 contrasts or group_pairs look wrong.
tags: [bioinformatics, snakemake, omics, rnaseq]
triggers:
  - user reports missing DESeq2 contrasts or group_pairs in Omics output
  - user says exp_X_Y should pair with multiple controls in the meta design
  - MetaUtil build_design_pairs output looks wrong
---

# MetaUtil Design-Pairing Triage (Omics workflows)

Diagnose missing or wrong comparison contrasts produced by
`workflow/Omics/src/common/util/MetaUtil.py` (`build_design_pairs`).

## Pairing semantics (know these before diagnosing)

- Design format: `ctr_TAG`/`ctrl_TAG` = control, `exp_TAG` = experiment;
  TAG splits on `_` into tokens; a control matches an experiment when token
  sets intersect.
- One exp tag matches only the FIRST intersecting control tag (loop `break`s
  after the first match). `exp_E14_KSR` (tokens {E14,KSR}) pairs with
  `ctr_E14` only — `ctr_KSR` is never consulted. Users often expect one
  contrast per control; to get that, split the tag: `exp_E14` and `exp_KSR`.
- `run()` short-circuits pairing entirely when the design column is absent or
  all-NaN — logs `meta design is all none, skip build_design_pairs`, returns
  empty group_pairs with NO error.

## Debugging procedure (in order)

1. Grep the run log for `meta design is all none, skip build_design_pairs`.
   If present, the meta used at run time had no usable design values.
2. Compare the meta file's mtime against the failing run's log timestamps.
   A meta edited AFTER the run means the log describes the OLD file — the
   code may be fine and a re-run sufficient. Verify pairing semantics by
   executing `MetadataUtils(outdir=<scratch>, meta=<current meta>).run()`
   directly and printing group_pairs; do not conclude "MetaUtil is broken"
   from stale-log evidence alone.
3. Check cached `output/<wf>/raw.json` → `Params/DESeq2/group_pairs`: it
   holds the LAST run's pairs and may be a group-column fallback
   (e.g. `E14_vs_TLSC`) rather than design-based contrasts, until the next
   run regenerates it.
4. If pairs are incomplete (not absent): list the exp/ctr tags with their
   token sets and check the first-match-break rule above; the fix is in the
   meta (split tags), not in code.

## Pitfalls

- Don't trust the current meta contents when reading old logs — always check
  mtimes first; meta files get edited between runs and the log silently
  describes the previous version.
- Don't patch MetaUtil for the multi-control case; the first-match-break
  behavior is intentional, and the supported workaround is splitting exp
  tags in the meta file.
- `MetadataUtils.__init__` requires `meta=` or `fastq_dir=` (a bare outdir
  raises ValueError); pass `meta='/dev/null'` when injecting samples_dict
  manually for a pairing-semantics test.