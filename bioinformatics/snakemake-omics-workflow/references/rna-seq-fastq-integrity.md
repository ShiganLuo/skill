# RNA-seq FASTQ integrity and STAR failures

## Symptom
- STAR errors with messages like:
  - `quality string length is not equal to sequence length`
  - `SOLUTION: fix your fastq file`

## Root cause pattern
- Trimming tools (commonly cutadapt) can emit zero-length reads when all bases are trimmed away.
- STAR can fail on these records even if the FASTQ file is otherwise parseable.

## Verification
1. Inspect the trimmed FASTQ directly with gzip.
2. Check record-by-record that sequence length equals quality length.
3. Count empty reads (seq or qual length = 0).
4. Compare the failing record header in STAR logs against the FASTQ content.

## Practical fixes
- Set an explicit cutadapt `minimum_length` to avoid writing empty reads.
- If empty reads are expected, filter them before STAR.
- Re-run the trimming step and re-verify the output FASTQ integrity.

## Notes
- A cutadapt report can still say the run succeeded even when some reads were trimmed to length 0.
- STAR may surface this as a generic reads-input/quality mismatch error rather than naming empty reads explicitly.