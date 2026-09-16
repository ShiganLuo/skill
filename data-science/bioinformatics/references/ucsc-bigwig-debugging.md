# UCSC bigwig Debugging — "Region Not Displayed" Triage

When a user reports a region is "missing / blank / not displayed" in UCSC
Genome Browser bigwig tracks, walk this checklist before assuming any
file, format, or rendering bug.

## Phase 0: Verify the view-box actually covers the region

**This is the #1 trap.** The user's URL contains `position=chr:START-END`,
and the browser only renders that exact range. If the user's complaint is
about a position OUTSIDE that range, there is nothing to debug — the
browser is behaving correctly.

**Action:** Parse the URL `position=` parameter on the very first turn.
State the actual numeric range back to the user. Only proceed to data
investigation if the region is INSIDE the view box.

```text
User URL: position=chrM:14588-15428
User claim: "chrM:15428-16299 not displayed"
View box:  chrM:14588-15428 (840 bp)
Region:    chrM:15428-16299 (871 bp) — OUTSIDE view box by construction
Diagnosis: View-box boundary, not a rendering bug.
Fix:       Ask user to set position=chrM:15428-16299 (or wider).
```

**Why this trap fires so easily:**
- User pastes a URL with a narrow view while complaining about a wider region.
- "Completely blank" sounds like a serious bug, but the browser simply
  never drew that area.
- Auto-scale / clipping / low values produce *partial* artifacts (thin
  lines, near-zero traces), not full emptiness — so if the user says
  "nothing there at all" and the view box covers the region, then we have
  a real issue; otherwise the view-box mismatch is almost always the answer.

**Real session lesson (2026-09-16):** User reported four bigwigs "cannot
display" chrM:15428-16299 on UCSC mm39. URL contained
`position=chrM:14588-15428`. The view box ended at 15428, so 15428-16299
was never rendered. After four wrong diagnoses (auto-scale, file format,
UCSC bug, URL expiry) the user clarified "view only drew 1-15428." Should
have parsed the URL parameter on turn 1.

## Phase 1: Quick file sanity (pyBigWig)

After confirming the view box, if data still looks wrong, dump the actual
values from the file:

```python
import pyBigWig
bw = pyBigWig.open("file.bigwig")
print(bw.header())              # version, nLevels, minVal, maxVal
print(bw.chroms()["chrM"])      # expected length (mm39 chrM = 16299)
vals = bw.values("chrM", 15427, 16299)   # 0-based, end-exclusive
print(min(vals), max(vals), sum(1 for v in vals if v == 0))
```

If `min(vals) > 0` and the values match what the user expects, the file
is fine — the issue is on the UCSC side.

## Phase 2: Common UCSC rendering causes

| Symptom | Likely cause | Fix |
|---|---|---|
| Region visible as thin line near bottom | Auto-scale dominated by global max (e.g. mt-rRNA peak at 4258 dwarfs D-loop at 42) | Click track gear ⚙ → Vertical viewing range → "Auto-scale to current view", or add `viewLimits=0:50` to track line |
| Track completely empty in covered region | Custom track URL expired (8-hour limit), or HTTP range request failing | Re-upload, or switch to a track hub (permanent) |
| Track empty only on chrM / mtDNA | Stale browser cache, or mm10 BAM uploaded to mm39 (coords happen to align for chrM but other issues elsewhere) | Clear cache, verify reference strain (mm10 chrM = NC_005089.1 = mm39 chrM, both 16299 bp, so coords align) |
| Rendered as wraparound | UCSC treats chrM as circular; D-loop (15,423-16,299) wraps to position 1 | This is cosmetic, not a data issue |

## Phase 3: Custom track vs track hub

**Custom track (paste URL):**
- 8-hour expiration
- No version control
- Easy to lose
- Suited for one-off debugging

**Track hub (recommended for any real analysis):**
- `genomes.txt` + `trackDb.txt` + bigwig files on a static HTTPS host
- Permanent, shareable, version-controlled
- Required for publication figures

If the user is using custom track and sees intermittent rendering, the
fix is always to migrate to a hub.

## Pitfalls

- **Don't trust the user's "region X is invisible" claim until you've
  parsed the URL `position=` parameter.** The mismatch is the bug 90% of
  the time.
- **Don't assume auto-scale explanation when the user says "completely
  blank."** Auto-scale produces thin lines, not emptiness.
- **mm10 chrM = mm39 chrM** (both are NC_005089.1, C57BL/6J, 16299 bp).
  Cross-assembly coord mismatches do NOT apply to chrM between these two.
  Other mouse strains (BALB/cJ, NZB) DO differ — confirm reference strain
  in BAM header `@SQ` lines if user used a non-reference strain.
- **chrM has high copy number in cells**, so bamCoverage tracks show
  ~100-1000x the signal of nuclear chromosomes. Global auto-scale often
  gets dominated by mt-rRNA region (chrM:5,000-10,000) which can hit
  4000+ while D-loop stays under 50.
