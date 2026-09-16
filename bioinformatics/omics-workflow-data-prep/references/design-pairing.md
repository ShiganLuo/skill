# Design Pairing — Token Intersection Matching

Implementation: `workflow/Omics/src/common/MetaUtil.py` → `build_design_pairs()`

## Matching Algorithm

1. Parse each sample's `design` column with regex `^(ctr|ctrl|exp)_(.+)$`
2. Normalise role: `ctrl` → `ctr` (uniform internal key)
3. Group samples by (tag, role): `groups[tag][role] = [SampleInfo, ...]`
4. For each unique exp tag, compute token set by splitting on `_`
5. For each unique ctr tag, compute token set by splitting on `_`
6. Match: `exp_token_set & ctr_token_set` (set intersection) is non-empty → pair them
7. First matching ctr wins; all exp samples under that tag get paired with it

## Examples

### One control serves multiple experiments
```
sample_id       design
Input_WT        ctrl_WT_KO_IP       # ctr tokens: {WT, KO, IP}
H3K4me3_WT      exp_WT              # exp tokens: {WT}        → match
H3K4me3_KO      exp_KO              # exp tokens: {KO}        → match
H3K4me3_IP      exp_IP              # exp tokens: {IP}        → match
```
Result: Input_WT paired with all three experiments.

### Multiple controls, each matched independently
```
Input_WT        ctrl_WT             # {WT}
Input_KO        ctrl_KO             # {KO}
H3K4me3_WT      exp_WT              # {WT} → matches Input_WT
H3K4me3_KO      exp_KO              # {KO} → matches Input_KO
```

### Token isolation (no substring bleed)
```
ctrl_KOWT       # tokens: {KOWT}
exp_KO          # tokens: {KO}     → {KOWT} ∩ {KO} = ∅ → NO match

ctrl_KO10       # tokens: {KO10}
exp_KO1         # tokens: {KO1}    → {KO10} ∩ {KO1} = ∅ → NO match
```

### Backward compatibility (old ctr_x / exp_x format)
```
Input_WT        ctr_WT              # {WT}
H3K4me3_WT      exp_WT              # {WT} → match
```
Works identically to the old exact-tag system.

### Multiple ctr samples with same tag
```
Input_WT_1      ctrl_WT             # first
Input_WT_2      ctrl_WT             # second (warning logged, ignored)
H3K4me3_WT      exp_WT              # → paired with Input_WT_1 only
```

### No matching control
```
Input_ABC       ctrl_ABC
H3K4me3_WT      exp_WT              # {WT} ∩ {ABC} = ∅ → warning, skipped
```

## Regex Accepted Formats

| design value | Matches regex? | role   | tag     |
|---|---|---|---|
| `ctr_WT`     | yes | ctr | WT |
| `ctrl_WT_KO` | yes | ctr | WT_KO |
| `exp_WT`     | yes | exp | WT |
| `input`      | no  | —   | — |
| `ip`         | no  | —   | — |

## Code Reference

File: `workflow/Omics/src/common/MetaUtil.py`
- `DESIGN_PATTERN = re.compile(r"^(ctr|ctrl|exp)_(.+)$")` (line 50)
- `build_design_pairs()` method (line 121)
- Returns `List[DesignPair]` where `DesignPair.organism`, `.ctr_sample_id`, `.exp_sample_id`, `.exp_group`
