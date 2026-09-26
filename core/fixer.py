"""
core/fixer.py
-------------
Deterministic, rule-based fix proposer for BugFix Agent.

This module is NOT an LLM or an AI model.  It applies a small catalogue
of hand-crafted rewrite rules to produce safe, minimal code fixes for a
known set of common Python errors.

Rules implemented:
    1. ZeroDivisionError — literal zero divisor  (x / 0  →  x / 1)
    2. NameError         — missing variable that can be safely inferred
                           from a nearby literal assignment in the same code
    3. SyntaxError       — single unmatched opening parenthesis at end of code

For every other case the function returns success=False and asks the
developer to review the code manually.

Public interface:
    propose_fix(code: str, error_message: str) -> dict
"""

import ast
import re


# ── Public interface ──────────────────────────────────────────────────────────

def propose_fix(code: str, error_message: str) -> dict:
    """
    Attempt to propose a safe, minimal fix for the reported error.

    Parameters
    ----------
    code : str
        The Python source code that produced the error.
    error_message : str
        The exception type and message as a string, e.g.
        ``"ZeroDivisionError: division by zero"``.

    Returns
    -------
    dict with keys:
        success     : bool  – True when a concrete fix was produced
        message     : str   – Short description of the outcome
        fixed_code  : str   – Present only when success is True
        explanation : str   – Why this change addresses the error
    """
    stripped = error_message.strip()

    if stripped.startswith("ZeroDivisionError"):
        return _fix_zero_division(code)

    if stripped.startswith("NameError"):
        return _fix_name_error(code, stripped)

    if stripped.startswith("SyntaxError") and "was never closed" in stripped:
        return _fix_unclosed_paren(code)

    # ── Unknown / unsupported error ───────────────────────────────────────────
    exc_type = stripped.split(":")[0].strip() if ":" in stripped else stripped
    return _no_fix(
        f"No automatic fix is available for `{exc_type}`.",
        "This error requires manual review. Read the traceback carefully "
        "to locate the exact line and understand what value was unexpected.",
    )


# ── Rule 1: ZeroDivisionError ─────────────────────────────────────────────────

def _fix_zero_division(code: str) -> dict:
    """
    Replace a literal `` / 0 `` or `` // 0 `` divisor with `` / 1 `` (or
    `` // 1 ``) on the first line where it appears.

    This is intentionally a demonstration fix: changing a divisor to 1
    keeps the expression syntactically valid and lets the developer see the
    pipeline work end-to-end.  A real fix depends on the domain.
    """
    # Match  / 0  or  // 0  where 0 is a literal integer (not e.g. 0.5)
    pattern = re.compile(r'(/{1,2})\s*\b0\b(?!\.\d)')

    if not pattern.search(code):
        return _no_fix(
            "ZeroDivisionError detected, but no literal zero divisor was found.",
            "The divisor may be a variable that evaluates to zero at runtime. "
            "Add a guard: `if divisor != 0: result = value / divisor`.",
        )

    fixed_code = pattern.sub(r"\g<1> 1", code, count=1)

    return {
        "success": True,
        "message": "Replaced the literal zero divisor with 1 as a demonstration fix.",
        "fixed_code": fixed_code,
        "explanation": (
            "Dividing by zero is undefined.  The literal `0` on the "
            "right-hand side of the division operator has been changed to "
            "`1` so the expression is mathematically valid.  "
            "In a real fix you should replace `0` with the correct non-zero "
            "value for your use-case, or add a guard that skips the "
            "division when the divisor is zero."
        ),
    }


# ── Rule 2: NameError ─────────────────────────────────────────────────────────

def _fix_name_error(code: str, error_message: str) -> dict:
    """
    If the NameError message names an undefined variable and that exact name
    appears as the left-hand side of a literal assignment elsewhere in the
    code, prepend a ``name = <value>`` line at the top as a safe initialiser.

    If we cannot safely infer an initial value, return success=False.
    """
    # Extract the missing name from  "NameError: name 'foo' is not defined"
    match = re.search(r"name '([^']+)' is not defined", error_message)
    if not match:
        return _no_fix(
            "Could not extract the missing name from the NameError message.",
            "Check the variable name for typos and make sure it is assigned "
            "before the line where it is used.",
        )

    missing_name = match.group(1)

    # Look for a literal assignment like  missing_name = <literal>
    # in the submitted code (e.g. a commented-out or later reassignment).
    # Pattern: name = <int | float | quoted string | True | False | None>
    literal_pattern = re.compile(
        r'^\s*' + re.escape(missing_name) +
        r'\s*=\s*'
        r'('
        r'"[^"]*"'          # double-quoted string
        r"|'[^']*'"         # single-quoted string
        r'|[-+]?\d+\.\d*'  # float
        r'|[-+]?\d+'        # integer
        r'|True|False|None' # bool / None
        r')',
        re.MULTILINE,
    )

    assignment_match = literal_pattern.search(code)

    if not assignment_match:
        return _no_fix(
            f"The variable `{missing_name}` is not defined, and its value "
            "cannot be inferred safely from the surrounding code.",
            f"Add an assignment for `{missing_name}` before the line that "
            "uses it, e.g. `{missing_name} = <correct_value>`.",
        )

    inferred_value = assignment_match.group(1)

    # Prepend  name = value  as the very first line so it is always in scope.
    init_line = f"{missing_name} = {inferred_value}  # added by BugFix Agent\n"
    fixed_code = init_line + code

    # Quick sanity-check: the fixed code must at least parse.
    try:
        ast.parse(fixed_code)
    except SyntaxError:
        return _no_fix(
            "An initialiser line was identified, but inserting it "
            "produced a syntax error — manual review is needed.",
            "Check the code structure around the variable assignment.",
        )

    return {
        "success": True,
        "message": (
            f"Prepended `{missing_name} = {inferred_value}` "
            "based on an existing assignment in the code."
        ),
        "fixed_code": fixed_code,
        "explanation": (
            f"The name `{missing_name}` was used before it was assigned. "
            f"The value `{inferred_value}` was inferred from an existing "
            "assignment found in the submitted code and inserted at the top "
            "to ensure the variable is always defined when it is first used. "
            "Verify that this initial value is correct for your use-case."
        ),
    }


# ── Rule 3: Unclosed parenthesis SyntaxError ──────────────────────────────────

def _fix_unclosed_paren(code: str) -> dict:
    """
    If there is exactly one more ``(`` than ``)`` in the entire code,
    append a single closing parenthesis to the last line.

    We only attempt the fix when the imbalance is exactly 1 — a larger
    imbalance likely means the structure is too complex to repair safely.
    """
    open_count = code.count("(")
    close_count = code.count(")")
    imbalance = open_count - close_count

    if imbalance != 1:
        return _no_fix(
            f"Found {imbalance} unmatched opening parenthesis/parentheses. "
            "Only a single missing `)` can be fixed automatically.",
            "Check all brackets in your code and add the missing closing "
            "parentheses in the correct positions.",
        )

    fixed_code = code.rstrip() + ")"

    # Verify the repair produces valid syntax.
    try:
        ast.parse(fixed_code)
    except SyntaxError:
        return _no_fix(
            "Appending `)` did not produce valid syntax — "
            "the parenthesis structure is too complex to repair automatically.",
            "Count opening and closing parentheses manually to find "
            "where the missing `)` belongs.",
        )

    return {
        "success": True,
        "message": "Appended a single closing parenthesis to balance the expression.",
        "fixed_code": fixed_code,
        "explanation": (
            "Python reported that an opening parenthesis was never closed. "
            "There was exactly one more `(` than `)` in the code, so a "
            "single `)` was appended to the end of the last statement. "
            "Confirm that this closing parenthesis belongs at the end of "
            "the expression and not somewhere in the middle."
        ),
    }


# ── Internal helper ───────────────────────────────────────────────────────────

def _no_fix(message: str, explanation: str) -> dict:
    """Return a uniform failure response with no fixed_code field."""
    return {
        "success": False,
        "message": message,
        "explanation": explanation,
    }
