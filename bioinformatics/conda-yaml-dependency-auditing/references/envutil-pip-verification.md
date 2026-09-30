# EnvUtil pip Package Verification

Added to EnvUtil.py (2026-09-30): `_verify_pip_packages()` method.

## What it does

After `apptainer build` completes, reads the source YAML to extract pip dependencies,
maps pip package names to Python import names, then runs `import <pkg>` for each
inside the container. Raises `RuntimeError` if any package cannot be imported.

## Key components

### `_PIP_IMPORT_MAP` (class variable)
Maps pip package names to their Python import names when they differ:
```python
{
    "pillow": "PIL",
    "scikit-learn": "sklearn",
    "scikit-image": "skimage",
    "opencv-python": "cv2",
    "pyyaml": "yaml",
    "python-dateutil": "dateutil",
    "beautifulsoup4": "bs4",
    "attrs": "attr",
    "protobuf": "google.protobuf",
}
```

### `_pip_to_import_name(pkg_spec)`
Strips version specifiers (`>=`, `<=`, `==`, `~=`, `!=`, `>`, `<`, `=`) and looks up
the import name. Falls back to replacing dashes with underscores.

### `_verify_pip_packages(sif_path, yaml_path)`
- Skips if `yaml_path` is None (verification silently skipped)
- Skips meta-packages (`python*`, `pip*`) and comments
- First tries all imports in one `apptainer exec` call
- If that fails, tests each package individually to identify which ones failed
- Raises `RuntimeError` with the list of failed packages

## Both callers must pass yaml_path

1. `process_yaml()` → `build_sif(yaml_path=str(yaml))` ✓
2. `process_def_file()` → extracts YAML from parsed .def metadata → `build_sif(yaml_path=yaml_for_verify)` ✓

If `yaml_path` is None, pip verification is silently skipped.

## Regex pitfall (fixed)

`skip_re = re.compile(r"^(python|pip)\b", re.I)` — the `\b` is a word boundary.
Old bug used `\\\\b` (four backslashes) which became literal `\b`, not word boundary.
Fixed to `\\b` (two backslashes = correct word boundary in raw string).

## What it catches

- Silent `pip install` failures where `apptainer build` returns 0
- Missing build dependencies (gcc, bedtools) that cause wheel build failures
- Network issues during pip install that silently skip packages

## What it does NOT catch

- Packages installed but with wrong versions
- Packages that import but have broken C extensions
- Runtime dependency issues (e.g., missing shared libraries)