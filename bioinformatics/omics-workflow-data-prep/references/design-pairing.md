# Design Pairing - Token Intersection Matching

Implementation: `workflow/Omics/src/common/util/MetaUtil.py` -> `build_design_pairs()`

## API

```python
def build_design_pairs(self) -> Tuple[List[DesignPair], List[CompareGroupPair]]:
```

Returns a **2-tuple** `(sample_pairs, group_pairs)`:
- `sample_pairs: List[DesignPair]` - one-to-one ctr→exp sample pairs (first ctr per tag)
- `group_pairs: List[CompareGroupPair]` - aggregated group-level pairs with all sample IDs

### CompareGroupPair

```python
@dataclass
class CompareGroupPair:
    ctr_group_name: str    # from SampleInfo.group, or derived fallback
    exp_group_name: str
    ctr_sample_ids: List[str]  # ALL ctr samples in this group
    exp_sample_ids: List[str]  # ALL exp samples in this group
```

### DesignPair

```python
@dataclass
class DesignPair:
    organism: str
    ctr_sample_id: str
    exp_sample_id: str
    exp_group: Optional[str]
```

## Group Name Resolution

`CompareGroupPair.ctr_group_name` / `exp_group_name` come from `SampleInfo.group`:

1. **If meta.tsv has a `group` column**: uses that value directly (highest priority).
2. **If no `group` column**: auto-derives from the `design` column by stripping the `ctr`/`ctrl`/`exp` prefix and replacing `_` with spaces.
   - `ctr_GSE123_normal_rep1` → group = `GSE123 normal rep1`
   - `exp_GSE456_treated` → group = `GSE456 treated`
3. **Fallback** (group is None): uses `{contrast}_ctr` or `{contrast}_exp`.

**Critical**: In `run.py`, group_pairs are inserted via `setdefault("{ctr_group_name}_vs_{exp_group_name}", ...)`. If all group names are `None` (e.g., no group column and design parsing fails), all pairs collapse into a single `None_vs_None` key.

## Matching Algorithm

1. Parse each sample's `design` column with regex `^(ctr|ctrl|exp)_(.+)$`
2. Normalise role: `ctrl` → `ctr` (uniform internal key)
3. Group samples by (contrast, role): `group_dict[contrast][role] = [SampleInfo, ...]`
4. For each unique exp contrast, compute token set by splitting on `_`
5. For each unique ctr contrast, compute token set by splitting on `_`
6. Match: `exp_token_set & ctr_token_set` (set intersection) is non-empty → pair them
7. First matching ctr wins; all exp samples under that contrast get paired with it
8. Build `CompareGroupPair` from the matched ctr/exp groups (includes ALL samples, not just first)

## repN Token Warning

`REP_PATTERN = re.compile(r"^rep\d+$", re.IGNORECASE)`

When a match's shared tokens are **only** rep-like (`rep1`, `REP2`, etc.), a warning is logged:

```
Suspicious match: exp 'GSE222_conditionB_rep1' and ctr 'GSE111_conditionA_rep1'
share only rep-like tokens {'rep1'}.
Consider providing a 'group' column or adjusting design format.
```

The match is **not skipped** - it still proceeds, but the user is warned. This catches the common mistake of including `repN` in the design column, which causes false cross-study pairings.

## Result Validation Warnings

At the end of `build_design_pairs`:
- If exp samples exist but no group_pairs were generated → warning
- If any pair has `ctr_group_name == exp_group_name` → warning (will collapse via setdefault)

## Examples

### Standard matching
```
Input_WT        ctrl_WT_KO_IP       # ctr tokens: {WT, KO, IP}
H3K4me3_WT      exp_WT              # exp tokens: {WT}        → match
H3K4me3_KO      exp_KO              # exp tokens: {KO}        → match
```

### Token isolation (no substring bleed)
```
ctrl_KOWT       # tokens: {KOWT}
exp_KO          # tokens: {KO}     → {KOWT} ∩ {KO} = ∅ → NO match
```

### Multiple ctr samples with same tag
Only the first ctr sample is used for DesignPair (sample_pairs), but ALL ctr samples are included in CompareGroupPair (group_pairs).

### Backward compatibility
`ctr_WT` works identically to `ctrl_WT`.

## Code Reference

File: `workflow/Omics/src/common/util/MetaUtil.py`
- `DESIGN_PATTERN = re.compile(r"^(ctr|ctrl|exp)_(.+)$")` (line 20)
- `REP_PATTERN = re.compile(r"^rep\d+$", re.IGNORECASE)` (line 21)
- `build_design_pairs()` method (line 92)
- `prepare_fastq_meta()` - sets `SampleInfo.group` (line ~232, group auto-derivation)
