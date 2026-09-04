# IGV Track Module — Two Modes

The `modules/track/` module supports two distinct input modes for IGV.js HTML generation:

## `igv_track_single` — Single BigWig per sample (ChIP-seq, ATAC-seq)

- Input: one `.bigwig` per sample (e.g. `Pop5IP.bigwig`, `Pop5Input.bigwig`)
- Each track's strand is `"unknown"` (no plus/minus distinction)
- **Auto-grouping**: when ALL tracks have strand=unknown, `track.py` strips common ChIP-seq suffixes (IP, Input, IP_rep1, Input_rep1) to group related samples:
  - `Pop5IP` + `Pop5Input` → group "Pop5"
  - `Rpp14IP` + `Rpp14Input` → group "Rpp14"
- Template hides `[unknown]` strand badges for cleaner UI

## `igv_track_iclip` — Paired BigWig per sample (iCLIP/CLIP-seq)

- Input: two files per sample — `.plus.bw` and `.minus.bw`
- Strand is detected from filename (`plus`/`minus` tokens via `_parse_track_identity`)
- Each sample gets its own group with plus/minus tracks color-coded (blue/red)
- Template shows `[plus]` / `[minus]` strand badges

## Implementation

- `_strip_condition_suffix(name)` — regex strips IP/Input/rep suffixes to get base group name
- `_build_grouped_track_manifest()` — after initial grouping, checks if ALL tracks have strand=unknown; if so, regroups by suffix stripping
- Template JS: `${trackMeta.strand !== 'unknown' ? \` [${trackMeta.strand}]\` : ''}` — conditional strand badge

## Adding new condition suffixes

If new suffixes appear (e.g. "Treat", "Control", "ChIP", "WCE"), add them to the regex in `_strip_condition_suffix()`:

```python
m = re.match(r"^(.+?)(?:_?(?:IP|Input|Treat|Control|ChIP|WCE|IP[_-]?rep\d+|Input[_-]?rep\d+))$", name, re.IGNORECASE)
```
