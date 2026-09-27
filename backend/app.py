from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import ast
import sys
import os

from backend.ai_service import analyze_with_ai
from backend.runner import run_code

# core/ lives one level above backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.fixer import propose_fix
from core.test_generator import generate_regression_test

app = FastAPI(title="BugFix Agent")`r`n`r`napp.mount("/static", StaticFiles(directory="frontend"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.responses import FileResponse`r`nfrom fastapi.staticfiles import StaticFiles
@app.get("/")
def home():
    return FileResponse("frontend/index.html")
@app.post("/analyze")
def analyze_code(data: dict):
    code = data.get("code", "")

    # ------------------------------------------------------------------
    # Phase 1 — Syntax check (fast, no subprocess needed)
    # ------------------------------------------------------------------
    try:
        ast.parse(code)
    except SyntaxError as error:
        explanation = f"Python found a syntax problem on line {error.lineno}."
        fixed_code = None

        if error.msg == "'(' was never closed":
            explanation = (
                "An opening parenthesis was found without a matching "
                "closing parenthesis."
            )
            fixed_code = code + ")"
            suggestion = (
                "Add the missing closing parenthesis at the end "
                "of the statement."
            )

        elif "unterminated string literal" in error.msg:
            explanation = (
                "A string was started with a quote but was not closed "
                "before the end of the line."
            )
            suggestion = (
                "Check that every opening quote has a matching "
                "closing quote."
            )

        elif error.msg == "expected ':'":
            explanation = (
                "Python expected a colon at the end of a statement "
                "such as if, for, while, def, or class."
            )
            suggestion = (
                "Add ':' at the end of the statement on the reported line."
            )

        else:
            suggestion = (
                "Check the brackets, quotes, and punctuation around "
                "the reported line."
            )

        result = {
            "status": "error",
            "message": f"Syntax Error: {error.msg} at line {error.lineno}",
            "explanation": explanation,
            "suggestion": suggestion,
        }

        if fixed_code:
            result["fixed_code"] = fixed_code

        return result

    # ------------------------------------------------------------------
    # Phase 2 — Execute in an isolated subprocess
    # ------------------------------------------------------------------
    run_result = run_code(code)

    # Timeout — report clearly without exposing filesystem internals
    if run_result["timed_out"]:
        return {
            "status": "error",
            "message": "Execution timed out after 5 seconds.",
            "explanation": (
                "The code did not finish within the 5-second time limit. "
                "This usually means there is an infinite loop or a blocking "
                "operation that never completes."
            ),
            "suggestion": (
                "Look for `while True` loops or recursive calls that have "
                "no exit condition. Make sure every loop has a reachable "
                "termination point."
            ),
        }

    # Clean execution — code ran without errors
    if run_result["success"]:
        response = {
            "status": "success",
            "message": "Code executed successfully with no errors.",
        }
        if run_result["stdout"].strip():
            response["stdout"] = run_result["stdout"]
        return response

    # ------------------------------------------------------------------
    # Phase 3 — Runtime error: analyse, explain, and propose a fix
    # ------------------------------------------------------------------
    error_summary = run_result["error"]   # e.g. "ZeroDivisionError: division by zero"

    ai = analyze_with_ai(code, error_summary)

    # Strip temp-file paths from the traceback so the user sees
    # clean line references rather than internal /tmp/... paths.
    clean_traceback = _clean_traceback(run_result["stderr"])

    response = {
        "status": "error",
        "message": error_summary if error_summary else "Runtime error occurred.",
        "explanation": ai["explanation"],
        "suggestion": ai["suggestion"],
        "stderr": clean_traceback,
    }

    # Ask the fixer whether it can propose a safe, deterministic fix.
    # The fixer never executes code — verification is a separate /verify step.
    fix = propose_fix(code, error_summary)
    if fix["success"]:
        response["fixed_code"] = fix["fixed_code"]
        response["fix_message"] = fix["message"]
        response["fix_explanation"] = fix["explanation"]

    # Ask the test generator for a regression test.
    # If generation is unsupported we silently continue — the caller receives
    # all existing fields unchanged.
    test_gen = generate_regression_test(code, error_summary)
    if test_gen["success"]:
        response["regression_test"] = test_gen["test_code"]

    return response


# ----------------------------------------------------------------------
# Verify endpoint
# ----------------------------------------------------------------------

@app.post("/verify")
def verify_fix(data: dict):
    """
    Run the caller-supplied fixed code in an isolated subprocess and
    report whether it executes cleanly.

    Expected request body:
        {
            "original_code": "...",   # kept for audit; not executed here
            "fixed_code":    "..."    # this is what gets run
        }
    """
    fixed_code = data.get("fixed_code", "")

    run_result = run_code(fixed_code)

    # Timeout
    if run_result["timed_out"]:
        return {
            "status": "error",
            "success": False,
            "message": "Verification timed out after 5 seconds.",
            "timed_out": True,
        }

    # Fixed code still fails
    if not run_result["success"]:
        response = {
            "status": "error",
            "success": False,
            "message": "The fixed code still produces an error.",
            "timed_out": False,
            "error": run_result["error"],
        }
        if run_result["stdout"].strip():
            response["stdout"] = run_result["stdout"]
        return response

    # Fixed code runs cleanly
    response = {
        "status": "success",
        "success": True,
        "message": "Fixed code executed successfully with no errors.",
        "timed_out": False,
    }
    if run_result["stdout"].strip():
        response["stdout"] = run_result["stdout"]
    return response


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _clean_traceback(stderr: str) -> str:
    """
    Remove the absolute temp-file path from traceback lines so the
    user sees  File "script.py", line N  rather than the full system path.

    Example input line:
        File "/tmp/tmpABC123.py", line 3, in <module>
    Becomes:
        File "script.py", line 3, in <module>
    """
    import re
    # Match the quoted path on a traceback File line and replace it.
    return re.sub(
        r'File "[^"]*[\\/]([^\\/]+\.py)"',
        r'File "script.py"',
        stderr,
    )



