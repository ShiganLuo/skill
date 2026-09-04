# NumPy Docstring Template

User preference: all Python functions use English NumPy-style docstrings.

## Standard Format

```python
def function_name(
    param1: str,
    param2: int = 10,
    param3: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Short summary line ending with period.

    Extended description if needed. Can span multiple lines
    and include background context.

    Parameters
    ----------
    param1 : str
        Description of param1.
    param2 : int, optional
        Description of param2. Default is 10.
    param3 : list of str, optional
        Description of param3. Default is None,
        which means ["default_value"].

    Returns
    -------
    pd.DataFrame
        Description of return value with column names if applicable.

    Raises
    ------
    ValueError
        When param1 is empty or param2 is negative.

    Notes
    -----
    Any additional implementation notes, algorithmic details,
    or caveats.

    Examples
    --------
    >>> result = function_name("input", param2=5)
    >>> result.shape
    (100, 3)
    """
```

## Key Rules

1. **Summary line**: One sentence, starts with verb, ends with period
2. **Blank line** after summary, then extended description (optional)
3. **Sections use underline-style headers** (`Parameters\n----------`)
4. **Type in parameter list**: `name : type` (with spaces around colon)
5. **Optional params**: mark as `optional` in the type field
6. **Default values**: mention in description, not in type field
7. **Returns section**: type on first line, description indented below
8. **Raises section**: exception type + when it's raised

## Minimal Version (simple functions)

```python
def simple_func(x: int, y: int) -> int:
    """Add two integers.

    Parameters
    ----------
    x : int
        First number.
    y : int
        Second number.

    Returns
    -------
    int
        Sum of x and y.
    """
    return x + y
```

## For Class Methods

```python
class MyClass:
    """Class summary line.

    Parameters
    ----------
    config : dict
        Configuration dictionary.
    """

    def method(self, arg: str) -> None:
        """Method summary line.

        Parameters
        ----------
        arg : str
            Argument description.
        """
```

## R Scripts (roxygen2 Style)

For R functions, use roxygen2 comments:

```r
#' Short summary line.
#'
#' Extended description if needed.
#'
#' @param param1 Character. Description of param1.
#' @param param2 Numeric. Default 10. Description of param2.
#' @return Data.frame with columns x, y, z.
#' @examples
#' result <- function_name("input", param2 = 5)
function_name <- function(param1, param2 = 10) {
  ...
}
```

## Placement Rule

**CRITICAL**: The docstring must be the FIRST statement after `def`. When using
`Optional[T] = None` with body initialization, the order is:

```python
def func(x: Optional[List[str]] = None) -> None:
    """Docstring FIRST."""          # ← docstring
    if x is None:                   # ← then init
        x = ["default"]
    # ... rest of function
```

WRONG (docstring becomes a dangling expression, not a docstring):
```python
def func(x: Optional[List[str]] = None) -> None:
    if x is None:
        x = ["default"]
    """Docstring AFTER init — NOT a docstring!"""
```
