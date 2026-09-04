# MetaUtil.py — Design Pair Matching (build_design_pairs)

## How it works

The `build_design_pairs()` method in `src/common/util/MetaUtil.py` auto-generates DESeq2 comparison pairs from the `design` column in meta_input.tsv.

### Design format
Regex: `^(ctr|ctrl|exp)_(.+)$`

Examples:
- `ctr_E14` → role=ctr, contrast="E14"
- `exp_E14_KSR` → role=exp, contrast="E14_KSR"

### Token matching algorithm

The contrast string is split on `_` into a token set. An exp group matches a ctr group when their token sets intersect (share at least one token).

```
exp "E14_KSR" → tokens {"E14", "KSR"}
ctr "E14"     → tokens {"E14"}          → intersection {"E14"} → MATCH
ctr "KSR"     → tokens {"KSR"}          → intersection {"KSR"} → MATCH
```

Each match produces a separate `CompareGroupPair`.

### group column override

If the `group` column exists in meta_input.tsv, it overrides the derived group name from design. E.g.:
- design=`exp_E14_KSR`, group=`TLSC` → group_name="TLSC" (not "E14 KSR")

## Bug: break after first match (FIXED)

The original code had `break` in the inner loop, causing only the first matching ctr to pair.
With `exp_E14_KSR`, ctr "E14" matched first → ctr "KSR" never paired.

**Fix applied**: Changed from `best_ctr_contrast` + `break` to collecting all matches in `matched_ctr_contrasts` list, then iterating over each.

## Debugging tips

1. Check raw.json `Params.DESeq2.group_pairs` — if a comparison is missing, check the design tokens
2. The validation warning "No matching control found for exp group" fires when no ctr shares tokens with an exp
3. "Suspicious match: share only rep-like tokens" fires when the only shared tokens look like `rep1`, `rep2`
