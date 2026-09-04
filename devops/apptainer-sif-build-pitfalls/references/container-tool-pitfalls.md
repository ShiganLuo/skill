# Container Tool Compatibility Pitfalls

## bedtools coverage -F is a fraction, not a flag

Inside SIF containers, `bedtools coverage -F 1024` fails with:
`ERROR: -F must be in the range (0.0, 1.0]`

`-F` is bedtools' minimum overlap fraction (0.0-1.0), NOT samtools-style integer flags.
Fix: `samtools view -b -F 1024 -o tmp.bam input.bam` then `bedtools coverage -a regions -b tmp.bam -counts`.

## set -euo pipefail fails in sh-based containers

Apptainer `%post` uses `/bin/sh` by default, not bash. `set -o pipefail` causes:
`set: Illegal option -o pipefail`

Fix: use `set -eu` (no pipefail). If pipefail is needed, add `#!/bin/bash` as first line of %post
or use `%post --shell /bin/bash`.
