# Path Matching Utilities for Bioinformatics Workflows

Two-phase matching pattern for sample/task ID to file path resolution.

## Pattern: Regex + Substring Fallback

When matching IDs (sample_id, task_id) to file paths, use a two-phase approach:

1. **Phase 1 - Regex full component match**: ID must be a complete path component
2. **Phase 2 - Substring fallback**: If no exact match, try substring containment

This avoids false positives (e.g., `12345` matching `123456`) while still catching paths where ID appears as part of a directory name.

### Regex Pattern for Full Path Component

```python
import re

pattern = re.compile(r'(?:^|/)' + re.escape(id) + r'(?:/|$)')
```

- `(?:^|/)`: ID preceded by start-of-string or `/`
- `re.escape(id)`: Literal match (escape special chars)
- `(?:/|$)`: ID followed by `/` or end-of-string

Matches:
- `/data/12345/task_abc/` ✓ (complete directory)
- `/data/sample_12345/task_abc/` ✗ (ID is substring of directory name)

### Implementation Template

```python
import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

def id_to_path_match(
    ids: List[str],
    paths: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Match IDs to paths using two-phase strategy:
    1. Regex full component match (exact directory)
    2. Substring fallback (containment)
    
    Returns: (matched_paths, unmatched_ids)
    """
    matched_paths = []
    unmatched_ids = []
    
    for id_ in ids:
        id_ = str(id_)
        
        # Phase 1: Regex full component match
        pattern = re.compile(r'(?:^|/)' + re.escape(id_) + r'(?:/|$)')
        matched = [p for p in paths if pattern.search(p)]
        
        if matched:
            logger.info(f"[Regex match] Found {len(matched)} exact match(es) for {id_}")
            matched_paths.extend(matched)
            continue
        
        # Phase 2: Substring fallback
        logger.info(f"[Substring fallback] No exact match for {id_}, trying substring")
        matched = [p for p in paths if id_ in p]
        
        if not matched:
            unmatched_ids.append(id_)
            logger.warning(f"No match found for {id_} (both regex and substring)")
            continue
        
        logger.info(f"[Substring match] Found {len(matched)} substring match(es) for {id_}")
        matched_paths.extend(matched)
    
    return matched_paths, unmatched_ids
```

### Multi-ID Matching (Sample + Task)

For matching multiple IDs together (e.g., sample_id AND task_id):

```python
def multi_id_match(
    id_pairs: List[Tuple[str, str]],
    paths: List[str]
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Match pairs of IDs to paths. Both must match (AND logic)."""
    matched_paths = []
    unmatched_pairs = []
    
    for id1, id2 in id_pairs:
        id1, id2 = str(id1), str(id2)
        
        # Phase 1: Regex for both
        pat1 = re.compile(r'(?:^|/)' + re.escape(id1) + r'(?:/|$)')
        pat2 = re.compile(r'(?:^|/)' + re.escape(id2) + r'(?:/|$)')
        matched = [p for p in paths if pat1.search(p) and pat2.search(p)]
        
        if matched:
            logger.info(f"[Regex match] Found {len(matched)} for {id1} + {id2}")
            matched_paths.extend(matched)
            continue
        
        # Phase 2: Substring for both
        logger.info(f"[Substring fallback] No exact match for {id1} + {id2}")
        matched = [p for p in paths if id1 in p and id2 in p]
        
        if not matched:
            unmatched_pairs.append((id1, id2))
            logger.warning(f"No match for {id1} + {id2}")
            continue
        
        logger.info(f"[Substring match] Found {len(matched)} for {id1} + {id2}")
        matched_paths.extend(matched)
    
    return matched_paths, unmatched_pairs
```

## Key Points

1. **Mutually exclusive phases**: Each ID uses either regex OR substring, never both
2. **Logging by phase**: Use `[Regex match]`, `[Substring fallback]`, `[Substring match]` prefixes
3. **Escape special chars**: Always `re.escape(id)` to handle regex metacharacters
4. **Performance**: Pre-compile patterns when matching many paths against same ID
5. **Multiple matches**: Log all matches when >1 found (user decides which to keep)

## Pitfalls

- Don't use word boundaries (`\b`) for path matching — they fail with underscores in directory names
- Don't mix regex and substring in same pass — keep phases separate for clear logging
- Path separators: assumes Unix `/` — adapt for Windows if needed
