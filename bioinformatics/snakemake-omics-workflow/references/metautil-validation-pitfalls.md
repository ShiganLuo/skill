# MetaUtil Validation Pitfalls

## Pandas NaN is truthy — `if r` does NOT filter NaN

```python
import math
bool(float('nan'))  # True!
```

When iterating pandas `.values`, NaN passes `if r` checks:

```python
# WRONG — NaN passes through
origin_r1_list = [r for r in df[col].values if r]

# RIGHT — use pd.notna()
origin_r1_list = [r for r in df[col].values if pd.notna(r)]
```

## str(NaN) = "nan" — cascading failures

Empty TSV cells become `float NaN`. `str(NaN)` produces literal `"nan"`, which fails downstream:

```python
val = df_sample['contaminated_organism'].values[0]  # NaN (float)
str(val)  # "nan"
resolve_genome("nan")  # ValueError!
```

**Cascading failure**: The except block catches ValueError and sets ALL fields to "UNKNOWN", losing valid host organism data:

```python
try:
    self.samples_dict[sid].organism = resolve_genome(host)           # OK
    self.samples_dict[sid].contaminated = resolve_genome(contam)     # FAILS: "nan"
except ValueError:
    self.samples_dict[sid].organism = "UNKNOWN"  # host organism LOST!
```

**Fix**: Pre-validate before calling functions:

```python
contaminated_raw = df_sample[col].values[0] if col in df.columns else None
if contaminated_raw is not None and not pd.isna(contaminated_raw) and str(contaminated_raw).strip():
    self.samples_dict[sid].contaminated = resolve_genome(str(contaminated_raw))
else:
    self.samples_dict[sid].contaminated = None
```

## Pandas .values[0] type is unpredictable

`df[col].values[0]` can return `str`, `int`, `float`, `NaN`, or `object`. Always explicitly convert:

```python
# WRONG
resolve_genome(df_sample[organism_col].values[0])

# RIGHT
resolve_genome(str(df_sample[organism_col].values[0]))
```

For type hints, accept broader types:
```python
def resolve_genome(organism: Union[str, int, float, None]) -> str:
    if isinstance(organism, (int, float)) or not organism:
        return "UNKNOWN"
```

## sample_id whitespace validation

Spaces in sample_id cause silent failures in file paths and Snakemake wildcards. Always strip and validate:

```python
sample_id = str(row['sample_id']).strip()
if ' ' in sample_id or '\t' in sample_id:
    raise ValueError(f"sample_id '{sample_id}' contains whitespace")
```

Apply in ALL prepare_*_meta functions.

## Try/except scope: isolate independent operations

Don't wrap independent operations in the same try/except. If B fails, A's results get rolled back:

```python
# WRONG — B failure loses A's result
try:
    organism = resolve_genome(host)       # A: succeeds
    contaminated = resolve_genome(contam) # B: fails
except ValueError:
    organism = "UNKNOWN"  # A's result lost!
```
