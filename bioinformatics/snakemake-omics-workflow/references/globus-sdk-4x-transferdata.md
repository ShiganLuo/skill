# globus_sdk 4.x TransferData API Change

## Problem

`globus_sdk` 4.x changed `TransferData.__init__()` signature. The `transfer_client` argument was removed from the constructor.

### Old (globus_sdk 3.x)

```python
tdata = globus_sdk.TransferData(
    tc, source_ep, dest_ep,       # 3 positional args
    label=f"SRA Download {srr_id}",
    sync_level="checksum"
)
```

### New (globus_sdk 4.x, verified against 4.8.1)

```python
tdata = globus_sdk.TransferData(
    source_ep, dest_ep,            # 2 positional args only
    label=f"SRA Download {srr_id}",
    sync_level="checksum"
)
```

## Key details

- `TransferData.__init__` signature: `(self, source_endpoint, destination_endpoint, *, label=..., sync_level=..., ...)`
- `tc` (TransferClient) is NOT passed to constructor; only used later for `tc.submit_transfer(tdata)`.
- `TransferData` inherits from `dict` (via `GlobusPayload -> dict`). The object itself IS the payload.
- `sync_level="checksum"` is internally converted to int `3`.
- `tdata.add_item(source_path, dest_path)` adds transfer items to `tdata["DATA"]`.
- `tc.submit_transfer(tdata)` accepts the dict-like `tdata` directly — no `.data` or `.submit_transfer_payload` attribute needed.

## Error signature

```
TypeError: TransferData.__init__() takes 3 positional arguments but 4 positional arguments (and 2 keyword-only arguments) were given
```

This means you are passing `tc` as a first positional arg — remove it.

## Verification approach

1. Check SDK version: `python -c "import globus_sdk; print(globus_sdk.__version__)"`
2. Inspect signature: `inspect.signature(globus_sdk.TransferData.__init__)`
3. Construct with fake UUIDs to confirm no TypeError.
4. AST-check the source file to confirm the call has exactly 2 positional args.

## Affected file

`workflow/Omics/src/download/sra_download.py`, function `globus_download_single_srr`, ~line 201.
