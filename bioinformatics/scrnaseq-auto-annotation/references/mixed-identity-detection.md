# Mixed-Identity Detection

## Plan A — prompt-level holistic evaluation

In the Step 2 prompt, instruct the LLM:
"If the dominant markers point to one cell type but there is a SECONDARY,
consistently co-expressed marker set characteristic of a DIFFERENT cell
type, this often indicates a transitional or intermediate population.
Annotate based on the DOMINANT signature, set confidence=medium, and
mention the secondary signature explicitly in reasoning."

## Plan C — programmatic cross-type signal check

`_check_marker_cross_type_signal` checks whether top DEGs span multiple
tissue cell types:
- For each cell type in tissue_cell_types, count how many of the top 20
  DEGs match its canonical markers
- If ≥2 cell types each contribute ≥2 markers → `is_mixed=True`
- The predicted type must NOT be the dominant one (or share only marginally)

When `is_mixed=True`, the annotation's confidence is downgraded from
"high" to "medium" automatically.

## Why both layers

- Plan A catches cases the LLM already knows about (common knowledge)
- Plan C catches cases the LLM might miss (programmatic, consistent)
- Together they reduce false-high-confidence annotations on ambiguous clusters
