"""
Deterministic, rule-based fix proposer for BugFix Agent.

This module applies safe, minimal rewrite rules for common Python errors.
"""

import ast
import re


def propose_fix(code: str, error_message: str) -> dict:
    """
    Attempt to propose a safe, minimal fix for the reported error.
    """
    stripped = error_message.strip()

    if stripped.startswith("ZeroDivisionError"):
        return _fix_zero_division(code)

    if stripped.startswith("NameError"):
        return _fix_name_error(code, stripped)

    if stripped.startswith("SyntaxError") and "was never closed" in stripped:
        return _fix_unclosed_paren(code)

    exc_type = stripped.split(":")[0].strip() if ":" in stripped else stripped

    return _no_fix(
        f"No automatic fix is available for `{exc_type}`.",
        "This error requires manual review. Read the traceback carefully "
        "to locate the exact line and understand what value was unexpected.",
    )


def _fix_zero_division(code: str) -> dict:
    """Replace a literal zero divisor with 1 as a demonstration fix."""

    pattern = re.compile(r"(/{1,2})\s*\b0\b(?!\.\d)")

    if not pattern.search(code):
        return _no_fix(
            "ZeroDivisionError detected, but no literal zero divisor was found.",
            "The divisor may be a variable that evaluates to zero at runtime. "
            "Add a guard before performing the division.",
        )

    fixed_code = pattern.sub(r"\g<1> 1", code, count=1)

    return {
        "success": True,
        "message": "Replaced the literal zero divisor with 1.",
        "fixed_code": fixed_code,
        "explanation": (
            "The literal zero divisor was replaced with 1 so the expression "
            "can execute without ZeroDivisionError. In a real application, "
            "the correct non-zero value or validation rule should be used."
        ),
    }


def _fix_name_error(code: str, error_message: str) -> dict:
    """
    Handle NameError.

    If the missing name has an existing literal assignment, move that
    value before its first use.

    For a simple print(undefined_name) case, replace the bare name with
    a quoted string because this is a common beginner mistake.
    """

    match = re.search(r"name '([^']+)' is not defined", error_message)

    if not match:
        return _no_fix(
            "Could not extract the missing name from the NameError message.",
            "Check the variable name and make sure it is assigned before use.",
        )

    missing_name = match.group(1)

    # ---------------------------------------------------------
    # Special safe demonstration case:
    # print(hello) -> print("hello")
    # ---------------------------------------------------------

    print_pattern = re.compile(
        r"print\s*\(\s*" + re.escape(missing_name) + r"\s*\)"
    )

    if print_pattern.search(code):
        fixed_code = print_pattern.sub(
            f'print("{missing_name}")',
            code,
            count=1,
        )

        try:
            ast.parse(fixed_code)
        except SyntaxError:
            return _no_fix(
                "The proposed print fix produced invalid syntax.",
                "Review the print statement manually.",
            )

        return {
            "success": True,
            "message": (
                f"Replaced the undefined name `{missing_name}` with "
                f'the string "{missing_name}".'
            ),
            "fixed_code": fixed_code,
            "explanation": (
                f"`{missing_name}` was being interpreted as a variable, "
                "but no variable with that name was defined. Because the "
                "name is directly passed to print(), it can safely be "
                "interpreted as text in this demonstration case."
            ),
        }

    # ---------------------------------------------------------
    # Existing assignment inference
    # ---------------------------------------------------------

    literal_pattern = re.compile(
        r"^\s*" + re.escape(missing_name) +
        r"\s*=\s*"
        r'('
        r'"[^"]*"'
        r"|'[^']*'"
        r"|[-+]?\d+\.\d*"
        r"|[-+]?\d+"
        r"|True|False|None"
        r")",
        re.MULTILINE,
    )

    assignment_match = literal_pattern.search(code)

    if assignment_match:
        inferred_value = assignment_match.group(1)

        init_line = (
            f"{missing_name} = {inferred_value} "
            "# added by BugFix Agent\n"
        )

        fixed_code = init_line + code

        try:
            ast.parse(fixed_code)
        except SyntaxError:
            return _no_fix(
                "The inferred initializer produced invalid syntax.",
                "Check the variable assignment manually.",
            )

        return {
            "success": True,
            "message": (
                f"Prepended `{missing_name} = {inferred_value}` "
                "based on an existing assignment."
            ),
            "fixed_code": fixed_code,
            "explanation": (
                f"The name `{missing_name}` was used before it was assigned. "
                f"The value `{inferred_value}` was found in another literal "
                "assignment and inserted before the first use."
            ),
        }

    # ---------------------------------------------------------
    # No safe automatic fix
    # ---------------------------------------------------------

    return _no_fix(
        f"The variable `{missing_name}` is not defined.",
        f"BugFix Agent could not safely infer the correct value for "
        f"`{missing_name}`. Define it before using it.",
    )


def _fix_unclosed_paren(code: str) -> dict:
    """Fix exactly one unmatched opening parenthesis."""

    open_count = code.count("(")
    close_count = code.count(")")
    imbalance = open_count - close_count

    if imbalance != 1:
        return _no_fix(
            f"Found {imbalance} unmatched opening parenthesis/parentheses.",
            "Only a single missing closing parenthesis can be fixed automatically.",
        )

    fixed_code = code.rstrip() + ")"

    try:
        ast.parse(fixed_code)
    except SyntaxError:
        return _no_fix(
            "Appending `)` did not produce valid syntax.",
            "Check the bracket structure manually.",
        )

    return {
        "success": True,
        "message": "Appended a missing closing parenthesis.",
        "fixed_code": fixed_code,
        "explanation": (
            "Python reported that an opening parenthesis was never closed. "
            "Exactly one closing parenthesis was missing."
        ),
    }


def _no_fix(message: str, explanation: str) -> dict:
    """Return a uniform failure response."""

    return {
        "success": False,
        "message": message,
        "explanation": explanation,
    }