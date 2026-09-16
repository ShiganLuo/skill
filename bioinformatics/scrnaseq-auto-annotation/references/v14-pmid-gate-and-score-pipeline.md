---
topic: "Step 0 PMID requirement + specificity-weighted scoring + disambiguation gate"
audience: any future session that touches Step 0 query, the per-cluster score pipeline, or the LLM disambiguation path
created: 2026-09-14
updated: 2026-09-14 (v15: PMID pre-check for program_confident, rank_weight 0.05)
session_origin: "ovaries_scTE v12->v14 refactor; user demanded markers+PMIDs from LLM, then 'who told you to hardcode' correction"
---

# Step 0 PMID Requirement + Score Pipeline (v14/v15 design)

## Why this file exists

The skill `scrnaseq-auto-annotation` SKILL.md already documents the v12/v13
PMID gate, the specificity-weighted score, and the disambiguation LLM
flow. This reference adds the three things from the v14 session that the
SKILL.md was too long to absorb:

1. Step 0 LLM must return PMID per marker (not just markers).
2. Program score is the PRIMARY decision; LLM is invoked only when the
   score is ambiguous or zero.
3. Disambiguation LLM must also return a PMID, which the program
   verifies -- the LLM cannot get away with hallucinating a label.

## 1. Step 0 prompt: PMID per marker

Before v14 the Step 0 prompt only asked for marker gene names. The LLM
freely produced plausible-looking marker sets that were partly
hallucinated. The user pointed out: "AI should一开始 就查询好所有细胞类型
和marker,而且需要确保都有文献支撑" -- i.e. force the LLM to back each
marker with a real PMID.

### v15 addition: sample verification after Step 0

After `_query_tissue_cell_types` returns, `_verify_tissue_markers` samples
3 markers per cell type and searches PubMed. Results go into
`ctx["marker_verification"]` for the audit report. This catches obvious
hallucinations (fabricated gene symbols) without the cost of verifying
every marker. Unverified markers are NOT dropped -- they are flagged.

### Required output shape

```json
{
  "cell_types": {
    "Macrophage": {
      "markers": ["CD68", "CD163", "CSF1R", "MRC1"],
      "pmids": {
        "CD68": "12626569",
        "CD163": "11886422",
        "CSF1R": "17082649",
        "MRC1": "14991082"
      }
    }
  }
}
```

### Sanitization (post-parse, in `_query_tissue_cell_types`)

- PMID must be 8-digit numeric string. Anything else -> mark `"unverified"`.
- Missing PMID -> mark `"unverified"` (LLM said "I don't know").
- The `cell_types` dict returned to caller still contains all marker names
  (including `unverified` ones) so the scoring algorithm can try to match
  them. The audit report shows `unverified` count per cell type so a
  human reviewer sees which markers the LLM could not ground.
- v15 fix: `ct_pmids` dict stores per-cell-type pmids to avoid scope leak.

### Why "unverified" instead of "dropped"

Dropping the marker entirely would let the LLM escape by simply omitting
hallucinated markers from the response. Keeping it as `unverified` and
flagging it in the audit forces the LLM to admit uncertainty OR provide
real PMIDs. The downstream scoring still tries to match it, so a real
marker the LLM forgot the PMID for is not penalized beyond the audit
visibility.

## 2. Score pipeline (program-first, LLM-fallback)

### Threshold values (tunable, current defaults)

| Constant | Value | Meaning |
|---|---|---|
| `HIGH_SCORE_THRESHOLD` | 1.5 | score >= this AND margin >= `MARGIN_THRESHOLD` -> program resolves, no LLM |
| `LOW_SCORE_THRESHOLD` | 0.5 | score < this -> forced LLM call |
| `MARGIN_THRESHOLD` | 0.3 | if best_score and second_score are too close, ask LLM to break the tie even at high absolute score |
| `PMID_REFS_FOR_HIGH` | 2 | >= this many PubMed refs -> confidence can be "high" |

### Rank weight (v15 change)

Coefficient changed from 0.1 to 0.05 for flatter decay:
`rank_weight = 1.0 / (1.0 + rank * 0.05)`

Rank 0=1.0, rank 10=0.67, rank 30=0.40. Rationale: top-2 DEGs were too
dominant; if they happen to be shared markers, score was suppressed even
when 6 unique markers follow at rank 3-8.

### Three regimes

| Regime | Condition | Action |
|---|---|---|
| Confident program | `score >= HIGH` AND `margin >= MARGIN` | Program picks top-scored type, no LLM call. **v15: PMID pre-check runs first** (3 markers, 0 refs -> "medium"). Full PMID gate also runs after. |
| Ambiguous | `LOW <= score < HIGH` OR `margin < MARGIN` (but `score >= LOW`) | LLM disambiguates with top-3 scored candidates in the prompt. **v15: also sees full canonical marker list per type.** Must return PMID. |
| No match | `score == 0.0` (no marker in cluster's top DEG matches any tissue type) | LLM freely proposes a new cell type or "Unknown". Must return PMID if proposing a real type. |

### The program's job when LLM is called

The LLM prompt shows the top-3 scored candidates with their scores and
(v15) the full canonical marker list for all tissue types. The LLM's job
is to **explain** the choice, not to ignore the program's ranking. If LLM
picks the 3rd candidate, the audit shows the score gap and the LLM's
reasoning.

## 3. Disambiguation LLM must return PMID

### Why

Same principle as Step 0: if the LLM proposes a cell type freely, it can
hallucinate the label. Forcing it to cite a PMID per choice exposes the
hallucination immediately. The program runs the PMID search; if 0 PMIDs
match, the gate fires and forces `confidence=low` (or "medium" if the
cluster was program-resolved, since program-resolved clusters have
internal evidence even without external literature).

### Prompt shape

```json
{"cell_type": "<...>", "key_markers": [...], "reasoning": "<1-2 sentences
citing evidence, with PMID if you cite a paper>",
 "confidence": "high|medium|low", "pmid": "<PubMed ID or empty string>"}
```

### v15: disambiguation prompt now includes full canonical markers

`_build_disambiguation_prompt` now appends a "Canonical markers per type"
section showing every cell_type and its full marker list from
`tissue_cell_types`. Previously only top-3 candidates' matched markers
were shown.

### PMID gate treatment (asymmetric, v15 updated)

| Source | Refs found | Action |
|---|---|---|
| Program-resolved | 0 | **v15: PMID pre-check fires BEFORE this point** -> already `confidence="medium"` |
| Program-resolved | >= `PMID_REFS_FOR_HIGH` (2) | `confidence="high"` (no change) |
| Program-resolved | 1 | `confidence="medium"` (insufficient refs for high) |
| LLM-resolved | 0 | `confidence="low"`, suffix reasoning with `[PMID gate: no PubMed references...]` |
| LLM-resolved | 1 | `confidence="medium"` (downgrade from LLM's high) |
| LLM-resolved | >= 2 | `confidence` preserved |

The asymmetry reflects the fact that program-resolved clusters matched
canonical markers in the tissue reference (internal evidence), while
LLM-resolved clusters might be hallucinating a type that the
scoring algorithm didn't see.

## 4. Concrete code references in scRNAseq.py

- `_query_tissue_cell_types(...)` -- Step 0 prompt + PMID sanitization
- `_verify_tissue_markers(...)` -- v15: sample verification after Step 0
- `_score_cluster_against_tissue_types(top_genes, tissue_cell_types, n_top=30)` -- specificity-weighted score
- `_run_one_annotation_pass(...)` -- main loop with the 3 regimes + PMID pre-check
- `_llm_disambiguate_cluster(...)` -- narrow LLM call for ambiguous clusters
- `_build_disambiguation_prompt(...)` -- focused prompt with top-3 candidates, full marker list, and PMID requirement
- `_search_pubmed_for_markers(...)` -- PMID gate search

## 5. Anti-patterns to avoid

- **Don't add new score thresholds without empirical justification.** The 1.5 / 0.5 / 0.3 values were picked from one dataset and one marker-algorithm. If the next tissue shows scores are systematically lower, the right answer is to look at the marker set, not to lower the threshold.
- **Don't make the LLM call mandatory for every cluster.** v14's whole point is that the program can resolve most clusters without burning LLM quota. The "constraint to expose AI errors" is the PMID gate, not a per-cluster LLM call.
- **Don't `cell_type_raw` / `merge_to_cluster` in `annotation_corrections`.** v12 removed both. The schema is `{cluster_id: {new_cell_type, reasoning}}` only. See `correct_annotations_semantics.md`.
