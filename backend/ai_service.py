"""
ai_service.py
-------------
Deterministic rules-based Python bug analyzer.
No external APIs, no paid services — standard library only.

analyze_with_ai(code, error_message) -> dict
  error_message should be the exception type + message as a single string,
  e.g. "ZeroDivisionError: division by zero"
"""

import re


# ---------------------------------------------------------------------------
# Error catalogue
# Each entry is a dict with:
#   "match"       – callable(error_message) -> bool
#   "explanation" – plain-English root-cause sentence
#   "suggestion"  – concrete fix advice
# ---------------------------------------------------------------------------

_CATALOGUE = [
    # ── ZeroDivisionError ───────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("ZeroDivisionError"),
        "explanation": (
            "The program attempted to divide a number by zero, "
            "which is mathematically undefined."
        ),
        "suggestion": (
            "Add a guard before the division: check that the divisor "
            "is not zero before performing the operation, e.g. "
            "`if divisor != 0: result = value / divisor`."
        ),
    },
    # ── NameError ───────────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("NameError"),
        "explanation": (
            "The code referenced a variable or function name that "
            "has not been defined at the point where it is used."
        ),
        "suggestion": (
            "Check the spelling of the name and make sure it is "
            "assigned or imported before this line. Common causes: "
            "a typo, using a variable outside the scope it was created in, "
            "or forgetting to import a module."
        ),
    },
    # ── UnboundLocalError ───────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("UnboundLocalError"),
        "explanation": (
            "A local variable is referenced before it has been assigned "
            "a value inside the function. Python treats any variable that "
            "is assigned anywhere in a function as local to that function."
        ),
        "suggestion": (
            "Either assign an initial value to the variable at the top of "
            "the function, or declare it as `global` / `nonlocal` if you "
            "intend to use an outer-scope variable."
        ),
    },
    # ── TypeError (not callable) ────────────────────────────────────────────
    {
        "match": lambda msg: (
            msg.startswith("TypeError") and "not callable" in msg
        ),
        "explanation": (
            "The code tried to call something as a function, "
            "but that object is not callable (e.g. an integer, "
            "string, or list was used with parentheses like a function)."
        ),
        "suggestion": (
            "Check the variable being called with `()`. "
            "It may have been accidentally overwritten with a non-function "
            "value, or you may have used parentheses where you meant "
            "square brackets for indexing."
        ),
    },
    # ── TypeError (argument count) ──────────────────────────────────────────
    {
        "match": lambda msg: (
            msg.startswith("TypeError")
            and re.search(r"takes \d+ positional argument", msg)
        ),
        "explanation": (
            "The function was called with the wrong number of arguments."
        ),
        "suggestion": (
            "Count the parameters in the function definition and make sure "
            "the call passes exactly that many arguments. Remember that "
            "instance methods receive `self` automatically."
        ),
    },
    # ── TypeError (generic) ─────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("TypeError"),
        "explanation": (
            "An operation was applied to an object of the wrong type "
            "(e.g. adding a string to an integer)."
        ),
        "suggestion": (
            "Check the types of the values involved. "
            "Use `type(value)` or `isinstance()` to inspect them, "
            "and convert explicitly where needed (e.g. `int()`, `str()`)."
        ),
    },
    # ── IndexError ──────────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("IndexError"),
        "explanation": (
            "The code accessed a list or sequence with an index "
            "that is outside its valid range."
        ),
        "suggestion": (
            "Make sure the index is less than `len(sequence)`. "
            "A common fix is to check bounds before accessing: "
            "`if index < len(my_list): ...`, "
            "or use a loop that iterates over the sequence directly."
        ),
    },
    # ── KeyError ────────────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("KeyError"),
        "explanation": (
            "The code tried to access a dictionary key that does not exist."
        ),
        "suggestion": (
            "Use `dict.get(key)` to return None instead of raising an error, "
            "or check first with `if key in my_dict:`. "
            "Print the dictionary's keys to verify the exact key name."
        ),
    },
    # ── AttributeError ──────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("AttributeError"),
        "explanation": (
            "The code accessed an attribute or method that does not exist "
            "on the given object."
        ),
        "suggestion": (
            "Use `dir(object)` to list available attributes and methods. "
            "Check for typos in the attribute name, and confirm the object "
            "is the type you expect (it may be None or a different type)."
        ),
    },
    # ── ValueError ──────────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("ValueError"),
        "explanation": (
            "A function received an argument of the correct type "
            "but with an inappropriate value (e.g. converting "
            "a non-numeric string with `int()`)."
        ),
        "suggestion": (
            "Validate the value before passing it to the function. "
            "For type conversions, wrap in a try/except ValueError "
            "block to handle bad input gracefully."
        ),
    },
    # ── FileNotFoundError ───────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("FileNotFoundError"),
        "explanation": (
            "The program tried to open or access a file "
            "that does not exist at the given path."
        ),
        "suggestion": (
            "Check that the file path is correct and that the file exists. "
            "Use `os.path.exists(path)` to check before opening, "
            "and remember that relative paths are resolved from the "
            "working directory where the script is run."
        ),
    },
    # ── ModuleNotFoundError / ImportError ───────────────────────────────────
    {
        "match": lambda msg: (
            msg.startswith("ModuleNotFoundError")
            or msg.startswith("ImportError")
        ),
        "explanation": (
            "Python could not find the module being imported. "
            "Either the module is not installed or the name is misspelled."
        ),
        "suggestion": (
            "Install the missing package with "
            "`pip install <package-name>`. "
            "If the module is part of your own project, "
            "check the file name and that it is in the Python path."
        ),
    },
    # ── RecursionError ──────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("RecursionError"),
        "explanation": (
            "The program entered infinite (or very deep) recursion. "
            "A recursive function called itself so many times that "
            "Python's call-stack limit was exceeded."
        ),
        "suggestion": (
            "Make sure every recursive function has a base case that "
            "stops the recursion. Trace through the logic to confirm "
            "the base case is actually reachable with the values being passed."
        ),
    },
    # ── StopIteration ───────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("StopIteration"),
        "explanation": (
            "`next()` was called on an iterator that had no more items."
        ),
        "suggestion": (
            "Use a for-loop instead of calling `next()` manually, "
            "or pass a default value: `next(iterator, default)`."
        ),
    },
    # ── OverflowError ───────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("OverflowError"),
        "explanation": (
            "A numerical result was too large to be represented "
            "(common with floating-point operations)."
        ),
        "suggestion": (
            "Check for unexpectedly large input values or runaway loops. "
            "Python integers have arbitrary precision, but floats do not — "
            "consider using the `decimal` module for high-precision work."
        ),
    },
    # ── MemoryError ─────────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("MemoryError"),
        "explanation": (
            "The program ran out of available memory, "
            "usually by creating an unexpectedly large data structure."
        ),
        "suggestion": (
            "Look for loops or list comprehensions that produce "
            "very large collections. Process data in chunks "
            "or use generators (`yield`) instead of building "
            "everything in memory at once."
        ),
    },
    # ── PermissionError ─────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("PermissionError"),
        "explanation": (
            "The program tried to read, write, or execute a file "
            "or resource it does not have permission to access."
        ),
        "suggestion": (
            "Check the file or directory permissions. "
            "On Unix systems, `chmod` can adjust them. "
            "On Windows, check the file properties or run with "
            "appropriate privileges."
        ),
    },
    # ── TimeoutError ────────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("TimeoutError"),
        "explanation": (
            "An operation took longer than the allowed time limit."
        ),
        "suggestion": (
            "Check for slow network calls, blocking I/O, or infinite loops. "
            "Consider increasing the timeout or making the operation "
            "asynchronous."
        ),
    },
    # ── AssertionError ──────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("AssertionError"),
        "explanation": (
            "An `assert` statement failed, meaning a condition "
            "the programmer expected to be true was not."
        ),
        "suggestion": (
            "Print the values involved in the assertion to understand "
            "why it failed, then fix the logic that was supposed to "
            "guarantee the condition."
        ),
    },
    # ── NotImplementedError ─────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("NotImplementedError"),
        "explanation": (
            "A method or function that is supposed to be overridden "
            "in a subclass was called without being implemented."
        ),
        "suggestion": (
            "Implement the method in the subclass, "
            "or do not call it on the base class directly."
        ),
    },
    # ── SyntaxError (fallback — ast layer usually catches these first) ───────
    {
        "match": lambda msg: msg.startswith("SyntaxError"),
        "explanation": (
            "Python could not parse the code because of a syntax problem."
        ),
        "suggestion": (
            "Review the line number reported in the error. "
            "Look for missing colons, unmatched brackets, "
            "or incorrect indentation."
        ),
    },
    # ── IndentationError ────────────────────────────────────────────────────
    {
        "match": lambda msg: msg.startswith("IndentationError"),
        "explanation": (
            "The indentation of a line does not match the expected level. "
            "Python uses indentation to define code blocks."
        ),
        "suggestion": (
            "Use a consistent indentation style (4 spaces is standard). "
            "Do not mix tabs and spaces in the same file."
        ),
    },
]

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def analyze_with_ai(code: str, error_message: str) -> dict:
    """
    Match error_message against the known-error catalogue and return
    a structured explanation and suggestion.

    Parameters
    ----------
    code : str
        The Python source code that was submitted (kept for future use,
        e.g. targeted fixed_code generation).
    error_message : str
        The exception type and message as a string, e.g.
        "ZeroDivisionError: division by zero"

    Returns
    -------
    dict with keys:
        explanation : str
        suggestion  : str
        fixed_code  : str (only present when a safe fix can be generated)
    """
    stripped = error_message.strip()

    for entry in _CATALOGUE:
        try:
            if entry["match"](stripped):
                return {
                    "explanation": entry["explanation"],
                    "suggestion": entry["suggestion"],
                }
        except Exception:
            # A broken match predicate must never crash the whole service.
            continue

    # ── Generic fallback ────────────────────────────────────────────────────
    # Extract just the exception class name for a slightly more helpful message.
    exc_type = stripped.split(":")[0].strip() if ":" in stripped else stripped
    return {
        "explanation": (
            f"An error of type `{exc_type}` occurred. "
            "This is not yet in the known-error catalogue."
        ),
        "suggestion": (
            "Read the full traceback carefully — it shows the exact line "
            "and call stack where the error originated. "
            "Search for the error type and message online for targeted help."
        ),
    }
