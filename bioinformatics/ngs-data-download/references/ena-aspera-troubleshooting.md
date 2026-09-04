# ENA Aspera Troubleshooting (2026-08-11)

## Problem

ENA Aspera (ascp) downloads fail with "failed to authenticate" using all available key files.

## Root Cause (diagnosed this session)

ascp verbose log (`-L-`) reveals the failure is at the **SSH protocol level**, not authentication:

```
LOG [libssh2] 0.391770 Failure Event: -5 - Unable to exchange encryption keys
ERR [asssh] SSH connection startup failed, err = -5
ERR [ascp] SSH connection startup encountered invalid protocol
ERR failed to authenticate
```

ascp 3.9.1 (2022, bundled with Aspera CLI 3.9.6) cannot complete the SSH key exchange
with ENA's current server (fasp.sra.ebi.ac.uk:33001). ENA upgraded their SSH server;
the old ascp client's libssh2 is too old to negotiate.

This is NOT a key file problem — all keys fail at the same SSH handshake stage.

## Environment

- Aspera CLI 3.9.6 at `/home/luosg/opt/aspera/`
- ascp binary: `/home/luosg/opt/aspera/bin/ascp` (version 3.9.1.168954)
- Key files available:
  - `/home/luosg/opt/aspera/etc/asperaweb_id_dsa.openssh` (DSA, old)
  - `/home/luosg/opt/aspera/etc/aspera_tokenauth_id_rsa` (RSA, token auth)
- aspera-cli gem 4.20.0 in conda env `DNA` (Ruby 3.4.2)
- ascli bypass keys: embedded in gem at `lib/aspera/data/` (files 1=dsa, 2=rsa)

## Test Results

### Test 1: ascp with DSA key (fasp.sra.ebi.ac.uk)

```
ascp -T -l 300m -P 33001 -i asperaweb_id_dsa.openssh \
  era-fasp@fasp.sra.ebi.ac.uk:vol1/fastq/ERR164/ERR164407/ERR164407.fastq.gz /tmp/
```
Result: **FAILED** — SSH key exchange failure (err=-5)

### Test 2: ascp with RSA token key

Same command with `aspera_tokenauth_id_rsa`.
Result: **FAILED** — same SSH handshake error

### Test 3: ascp with fasp.ebi.ac.uk (alternative host)

```
ascp -T -l 300m -P 33001 -i asperaweb_id_dsa.openssh \
  fasp-ebi@fasp.ebi.ac.uk:databases/ena/wgs/public/wya/WYAA01.dat.gz /tmp/
```
Result: **FAILED** — same SSH handshake error

### Test 4: ascli bypass keys (extracted from gem)

Extracted DSA/RSA bypass keys from `aspera-cli-4.20.0/lib/aspera/data/`:
```ruby
require 'aspera/data_repository'
dsa_pem = Aspera::DataRepository.instance.item(:dsa)  # file "1"
rsa_pem = Aspera::DataRepository.instance.item(:rsa)  # file "2"
```
Tested both with ascp directly.
Result: **FAILED** — same SSH handshake error (confirming root cause is protocol, not keys)

### Test 5: NCBI prefetch with fasp

```
prefetch -t fasp ERR164407 -O /tmp/
```
Result: **FAILED** — "cannot download 'ERR164407' using requested transport"

### Test 6: NCBI prefetch with http

```
prefetch -t http ERR164407 -O /tmp/
```
Result: **SUCCESS** — 355MB SRA file in ~40s (~9 MB/s)

### Test 7: aria2c HTTP (ENA fastq.gz)

```
aria2c -x 8 -s 8 -k 1M "http://ftp.sra.ebi.ac.uk/vol1/fastq/ERR164/ERR164407/ERR164407.fastq.gz"
```
Result: **SUCCESS** — 72MB file in ~9s (~7.7 MB/s)

## ascli Dependency Fix Chain (for non-ENA Aspera use)

ascli 4.20.0 in conda env `DNA` (Ruby 3.4.2) has a broken dependency chain.
Fix in this exact order:

### Step 1: Install webrick
```bash
gem install webrick
```
Ruby 3.4 removed webrick from default gems. ascli requires it for `web_server_simple.rb`.

### Step 2: Symlink conda cross-compiler to system gcc
```bash
ln -s /usr/bin/gcc /home/luosg/miniconda3/envs/DNA/bin/x86_64-conda-linux-gnu-cc
```
conda Ruby's `mkmf.rb` hardcodes `x86_64-conda-linux-gnu-cc` as the compiler.
If conda compilers aren't installed, native gem extensions (bigdecimal) fail to build.

### Step 3: Install bigdecimal
```bash
gem install bigdecimal --version 3.1.8
```
Ruby 3.4 removed bigdecimal from default gems. Without it:
`coercible -> symmetric_encryption -> aspera-cli` require chain breaks.

### Step 4: Set GEM_PATH
```bash
export GEM_PATH="/home/luosg/miniconda3/envs/DNA/share/rubygems"
```
Ruby's default GEM_PATH may not include the conda gem directory.

### Step 5: Symlink ascp to SDK folder
```bash
mkdir -p ~/.aspera/sdk
ln -sf /home/luosg/opt/aspera/bin/ascp ~/.aspera/sdk/ascp
ln -sf /home/luosg/opt/aspera/bin/ascp4 ~/.aspera/sdk/ascp4
```
ascli looks for ascp in `~/.aspera/sdk/`. Without this, it reports
"no Aspera transfer module or SDK found".

### Step 6: Configure ENA preset
```bash
ascli conf preset update era \
  --url=ssh://fasp.sra.ebi.ac.uk:33001 \
  --username=era-fasp \
  --ssh-keys=/home/luosg/opt/aspera/etc/asperaweb_id_dsa.openssh \
  --ts=@json:'{"target_rate_kbps":300000}'
```
Note: `--ssh-keys=@ruby:Fasp::Installation.instance.bypass_keys.first` fails with
`uninitialized constant Fasp` — use a file path instead.

After all 6 steps, `ascli --version` returns `4.20.0` and ascli can invoke ascp.
**However**, downloads from ENA still fail because of the SSH protocol incompatibility
(see root cause above). This fix is only useful for non-ENA Aspera servers.

### Blocked: IBM SDK download

`ascli conf ascp install` hangs because `ibm.biz/sdk_location` is unreachable from
China. A newer ascp binary (that supports modern SSH) cannot be downloaded this way.

## Conclusion

ENA Aspera is broken due to SSH protocol incompatibility. No key file or ascli
configuration can fix it without a newer ascp binary, which cannot be downloaded
from China.

**Working alternatives:**
- aria2c multi-thread HTTP: ~7.7 MB/s (ENA fastq.gz)
- prefetch -t http: ~9 MB/s (NCBI SRA .sra files)

## ENA Official Documentation References

- File download guide: https://ena-docs.readthedocs.io/en/latest/retrieval/file-download.html
- Programmatic access: https://ena-docs.readthedocs.io/en/latest/retrieval/programmatic-access.html
- ENA Portal API for file reports: `https://www.ebi.ac.uk/ena/portal/api/filereport`
- ENA helpdesk: https://www.ebi.ac.uk/ena/browser/support
- EMBL KB article: https://embl.service-now.com/kb?id=kb_article_view&sys_kb_id=4cc60cf8c398a610bf313dfc0501314c
