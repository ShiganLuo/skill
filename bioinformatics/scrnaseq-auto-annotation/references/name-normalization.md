# Cross-Tissue Cell Type Name Normalization

## Layer 1: prompt discipline (preventive)

In the Step 0 prompt, instruct the LLM to use standard nomenclature.
In the Step 2 prompt, tell the LLM to use EXACT names from the
tissue_cell_types list.

## Layer 2: post-hoc `_normalize_cell_type_name` (corrective)

After LLM returns cell type names, normalize against tissue_cell_types:
1. Exact match (case-sensitive)
2. Case-insensitive match
3. Strip common suffixes (-like, _like, _cells) and re-match
4. Substring match (either direction)

Returns (normalized_name, was_changed). Applied in
`_run_one_annotation_pass` after all clusters are annotated.

## Granularity rules

Step 0 prompt: "For any cell type that has biologically distinct subtypes
identifiable by DIFFERENT canonical markers, list each subtype separately."

Step 2 prompt: "Granularity check: the list above is the MINIMUM
granularity. If the cluster's marker genes unambiguously match a
well-established subtype not in the list, you MAY use that subtype's
standard published name."

## Interaction with normalization

Normalization only fires when the LLM uses a VARIATION of a canonical
name (Granulosa-like → Granulosa cells). If the LLM uses a genuinely
new name that doesn't match any canonical name, normalization leaves it
unchanged — the orchestrator then decides if it's valid.
