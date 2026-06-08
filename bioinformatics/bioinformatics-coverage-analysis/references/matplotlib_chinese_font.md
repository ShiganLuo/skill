# Matplotlib Chinese Font Configuration

## Problem

Matplotlib cannot render Chinese characters by default — they appear as empty
boxes (□□□) or tofu. This is common in Chinese bioinformatics QC data where
column headers and category labels are in Chinese (e.g., 项目/产品名称, 样本类型,
石蜡包埋组织, Mapping rate(%)).

## Solution

```python
from matplotlib import font_manager
import matplotlib.pyplot as plt

def configure_chinese_font() -> str:
    """Configure a CJK-capable font for matplotlib and return selected font name."""
    candidates = [
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Micro Hei",
        "Microsoft YaHei",
        "SimHei",
        "PingFang SC",
        "Heiti SC",
    ]
    available_fonts = {f.name for f in font_manager.fontManager.ttflist}
    selected = ""
    for font_name in candidates:
        if font_name in available_fonts:
            selected = font_name
            break

    if selected:
        plt.rcParams["font.sans-serif"] = [selected, "DejaVu Sans", "Arial Unicode MS"]
    else:
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS"]

    plt.rcParams["axes.unicode_minus"] = False  # Fix minus sign rendering
    return selected
```

## Critical Pitfall: Must Call, Not Just Define

**The function MUST be called inside every plotting function that needs Chinese text.**
Simply defining it at module level or calling it once at startup does NOT work reliably
because:

1. `matplotlib.use('Agg')` or other backend switches can reset rcParams
2. `seaborn.set_style()` overrides `rcParams["font.sans-serif"]`
3. Each `plt.subplots()` or figure creation may re-read rcParams
4. Jupyter notebooks reset state between cells

Pattern — call at the top of each plot function:

```python
def my_plot_function(data, title, ...):
    selected_font = configure_chinese_font()  # <-- CALL HERE
    # ... rest of plotting code
```

## Troubleshooting

If Chinese still shows as boxes after configuration:

1. **No CJK font installed:**
   ```bash
   # CentOS/RHEL
   yum install -y google-noto-sans-cjk-sc-fonts
   # or
   yum install -y wqy-microhei-fonts

   # Ubuntu/Debian
   apt install -y fonts-noto-cjk
   ```

2. **Matplotlib font cache is stale:**
   ```bash
   rm -rf ~/.cache/matplotlib
   ```

3. **Manual font path registration (last resort):**
   ```python
   from matplotlib import font_manager
   font_path = "/path/to/NotoSansCJK-Regular.ttc"
   font_manager.fontManager.addfont(font_path)
   plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC"]
   ```

## Integration Pattern

When building analysis modules that auto-generate plots (like `prepare_data()`),
import and call the font config in the plotting module, not the data module:

```python
# plot_comparison.py
from matplotlib import font_manager
import matplotlib.pyplot as plt

def configure_chinese_font() -> str:
    # ... as above ...

def plot_comparison(result, ...):
    configure_chinese_font()  # called here
    # ... plotting code ...

def plot_violin(result, ...):
    configure_chinese_font()  # and here
    # ... plotting code ...
```

## Font Priority Order

The candidate list is ordered by preference:
1. Noto Sans CJK SC — best quality, wide coverage
2. Source Han Sans SC — Adobe's version of Noto
3. WenQuanYi Micro Hei — common on Linux
4. Microsoft YaHei — Windows
5. SimHei — older Windows Chinese font
6. PingFang SC / Heiti SC — macOS
