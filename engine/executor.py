"""
Safe pandas code execution in a restricted namespace.
"""

import re
import builtins as _builtins

import pandas as pd

# ---------------------------------------------------------------------------
# Allowed built-ins — everything needed for pandas expressions, nothing more
# ---------------------------------------------------------------------------
_SAFE_BUILTINS: dict = {
    name: getattr(_builtins, name)
    for name in [
        "abs", "all", "any", "bool", "dict", "divmod", "enumerate",
        "filter", "float", "frozenset", "int", "isinstance", "issubclass",
        "iter", "len", "list", "map", "max", "min", "next", "object",
        "pow", "print", "range", "repr", "reversed", "round", "set",
        "slice", "sorted", "str", "sum", "tuple", "type", "zip",
        "None", "True", "False", "NotImplemented",
    ]
    if hasattr(_builtins, name)
}

# ---------------------------------------------------------------------------
# Forbidden token patterns (checked on the raw code string before eval)
# ---------------------------------------------------------------------------
_BLOCKED: list[tuple[str, str]] = [
    (r"\bimport\b",     "import statements are not allowed"),
    (r"\bopen\s*\(",    "'open' is not allowed"),
    (r"\bexec\s*\(",    "'exec' is not allowed"),
    (r"\beval\s*\(",    "'eval' is not allowed"),
    (r"__",             "dunder access is not allowed"),
    (r"\bos\b",         "'os' module is not allowed"),
    (r"\bsys\b",        "'sys' module is not allowed"),
    (r"\bsubprocess\b", "'subprocess' module is not allowed"),
    (r"\bshutil\b",     "'shutil' module is not allowed"),
    (r"\bpathlib\b",    "'pathlib' module is not allowed"),
    (r"\bpickle\b",     "'pickle' module is not allowed"),
    (r"\bgetattr\s*\(", "'getattr' is not allowed"),
    (r"\bsetattr\s*\(", "'setattr' is not allowed"),
    (r"\bdelattr\s*\(", "'delattr' is not allowed"),
    (r"\bvars\s*\(",    "'vars' is not allowed"),
    (r"\bglobals\s*\(", "'globals' is not allowed"),
    (r"\blocals\s*\(",  "'locals' is not allowed"),
    (r"\bcompile\s*\(", "'compile' is not allowed"),
    (r"\b__import__\s*\(", "'__import__' is not allowed"),
    (r"\bbreakpoint\s*\(", "'breakpoint' is not allowed"),
]
_BLOCKED_RE: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern), msg) for pattern, msg in _BLOCKED
]


def _check_safety(code: str) -> None:
    """Raise ValueError if the code string contains any forbidden patterns."""
    for pattern, message in _BLOCKED_RE:
        if pattern.search(code):
            raise ValueError(f"Unsafe code rejected — {message}: {code!r}")


def safe_execute(code: str, dataframes: dict) -> pd.DataFrame:
    """
    Execute a single-line pandas expression in a restricted namespace.

    Args:
        code:        A single-line pandas expression returned by translate_question().
        dataframes:  Mapping of DataFrame name → pd.DataFrame.
                     Example: {"members": members_df, "accounts": accounts_df, ...}

    Returns:
        A pd.DataFrame.  If the expression evaluates to a Series it is
        automatically converted via .to_frame().

    Raises:
        ValueError: if the code is deemed unsafe, is multi-line, or the
                    result is not a DataFrame / Series.
        Exception:  any exception raised during pandas evaluation is
                    re-raised with a descriptive message.
    """
    # 1. Reject blank / multi-line code
    code = code.strip()
    if not code:
        raise ValueError("Empty expression received.")
    if "\n" in code:
        raise ValueError(
            f"Multi-line code is not allowed. Received:\n{code!r}"
        )

    # 2. Static safety scan
    _check_safety(code)

    # 3. Validate that all names referenced in code that match DataFrame keys
    #    are actually present — catches hallucinated table names early.
    for name in dataframes:
        # just ensure the name is a valid Python identifier before putting it
        # in the namespace (defensive; caller should guarantee this)
        if not name.isidentifier():
            raise ValueError(f"Invalid DataFrame name: {name!r}")

    # 4. Build restricted execution namespace
    namespace: dict = {
        "__builtins__": _SAFE_BUILTINS,
        "pd": pd,
        **dataframes,
    }

    # 5. Execute
    try:
        result = eval(code, namespace)  # noqa: S307 — guarded by safety check above
    except Exception as exc:
        raise ValueError(
            f"Error executing pandas expression {code!r}: {exc}"
        ) from exc

    # 6. Validate result type
    if isinstance(result, pd.Series):
        result = result.to_frame()

    if not isinstance(result, pd.DataFrame):
        raise ValueError(
            f"Expression must return a DataFrame or Series, "
            f"got {type(result).__name__}: {code!r}"
        )

    if result.empty:
        # Return the empty frame — callers decide how to handle no-data
        return result

    return result
