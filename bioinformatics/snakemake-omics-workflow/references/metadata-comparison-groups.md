# Metadata comparison groups and MetaUtil conventions

Use this when evolving `src/common/MetaUtil.py` beyond simple one-control-one-experiment pairings.

## Core rule

Keep `design` unchanged as the comparison descriptor. It continues to use the existing role+contrast encoding:

- `ctrl_CASE`
- `exp_CASE`

Do **not** repurpose `design` into a plain group label.

## New grouping direction

When workflows need many-to-many comparison traversal, add a separate comparison-group field (or map the existing `group` column into `comparison_group` on `SampleInfo`) while preserving `design`.

The target runtime shape is iterable comparison blocks, not just flat `DesignPair` objects:

- one contrast
- many `ctr` samples
- many `exp` samples

Recommended common type definitions live in `src/common/type.py`:

- `DesignRole`
- `ComparisonGroup`
- optional compatibility `DesignPair`

## MetaUtil implementation pattern

1. Parse `design` into `(role, contrast)`.
2. Group all samples by `contrast`.
3. For each contrast, collect:
   - `ctr_sample_ids`
   - `exp_sample_ids`
   - optional group labels for each side
4. Return iterable comparison groups from `MetadataUtils.run()`.
5. Keep derived one-to-one `design_pairs` only as a compatibility layer for old workflows.

## Why this split matters

- `design` answers: which comparison block and which side?
- `comparison_group` answers: what higher-level label should downstream grouped summaries use?

That separation avoids overloading one field with both pair semantics and plotting/aggregation semantics.

## Workflow adaptation pattern

For legacy workflows that only know one-vs-one pairs:

- consume `comparison_groups`
- if a rule still requires a single control, explicitly choose a fallback strategy and log it
- do **not** silently pretend the metadata is still one-to-one

Current compatibility strategy used in-session:

- for `Mutation` / `PeakCalling`, if one contrast has multiple controls, warn and use the first control as the temporary fallback
- preserve the full `ComparisonGroup` structure so future workflows can iterate the whole block directly

## Group field preference

If the user requests comparison-style grouping, make the grouping field design-like as well (role+contrast semantics), or at minimum store it separately from plain biological `group` naming. Do not collapse it back into sample-id prefix heuristics unless no metadata value is available.
