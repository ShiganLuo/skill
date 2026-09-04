# Comparison groups and design reuse

Session takeaway:
- Use `design` as the single source of truth for both simple grouping and comparison grouping.
- Two modes:
  - grouping workflow: `design=GroupA` (or another stable group label)
  - comparison workflow: `design=ctr_CASE` / `design=exp_CASE`
- For comparison workflows, parse `design` into:
  - role: `ctr` or `exp`
  - contrast: the tag after the underscore
- A contrast may have multiple control samples and multiple experiment samples.
- Prefer returning iterable `comparison_groups` objects (contrast + `ctr_sample_ids` + `exp_sample_ids`) instead of only pairwise results.
- Keep `DesignPair` only as a compatibility derivative when a downstream consumer still expects one control per experiment.
- Avoid adding a second persistent grouping field unless it has semantics that `design` cannot express.
- For downstream configs, derive sample groups from `design` rather than duplicating a `group` field.

Minimal validation pattern:
- group-style meta should preserve `design` as a group label
- comparison-style meta should aggregate all samples sharing the same contrast
- downstream consumers should iterate comparison groups without assuming 1:1 matching