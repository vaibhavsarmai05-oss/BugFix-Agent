"""
test_bugfix_agent.py
--------------------
pytest test suite for the BugFix Agent backend.

Covers:
  - runner.run_code()   : clean execution, runtime errors, timeout
  - POST /analyze       : syntax errors, runtime errors, clean code
  - POST /verify        : passing fix, failing fix

Run from the backend/ directory:
    pytest test_bugfix_agent.py -v
"""

import sys
import os
import pytest

# Make sure imports resolve when pytest is run from the backend/ directory
sys.path.insert(0, os.path.dirname(__file__))

from runner import run_code
from starlette.testclient import TestClient
from app import app

client = TestClient(app)


# ══════════════════════════════════════════════════════════════════════
# runner.run_code() tests
# ══════════════════════════════════════════════════════════════════════

class TestRunCode:

    def test_clean_execution_succeeds(self):
        """Valid Python with no errors should return success=True."""
        result = run_code("x = 1 + 1")
        assert result["success"] is True
        assert result["timed_out"] is False
        assert result["returncode"] == 0
        assert result["error"] == ""

    def test_stdout_is_captured(self):
        """Output from print() should appear in the stdout field."""
        result = run_code("print('hello bugfix')")
        assert result["success"] is True
        assert "hello bugfix" in result["stdout"]

    def test_runtime_error_is_captured(self):
        """A ZeroDivisionError should set success=False and populate error."""
        result = run_code("x = 1 / 0")
        assert result["success"] is False
        assert result["timed_out"] is False
        assert "ZeroDivisionError" in result["error"]
        assert result["returncode"] != 0

    def test_full_traceback_in_stderr(self):
        """stderr should contain the full Python traceback text."""
        result = run_code("x = 1 / 0")
        assert "Traceback" in result["stderr"]
        assert "ZeroDivisionError" in result["stderr"]

    def test_timeout_stops_infinite_loop(self):
        """An infinite loop should be killed after 5 seconds."""
        result = run_code("while True: pass")
        assert result["timed_out"] is True
        assert result["success"] is False
        # The error field should mention timeout
        assert "TimeoutError" in result["error"]


# ══════════════════════════════════════════════════════════════════════
# POST /analyze tests
# ══════════════════════════════════════════════════════════════════════

class TestAnalyzeEndpoint:

    def test_syntax_error_is_detected(self):
        """A SyntaxError should be caught by ast.parse in Phase 1."""
        response = client.post("/analyze", json={"code": "def foo("})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Syntax Error" in data["message"]
        assert data["explanation"] != ""
        assert data["suggestion"] != ""

    def test_unclosed_paren_returns_fixed_code(self):
        """Unclosed parenthesis should include a fixed_code suggestion."""
        response = client.post("/analyze", json={"code": "print('hi'"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "fixed_code" in data

    def test_runtime_zero_division_error(self):
        """A ZeroDivisionError should trigger Phase 3 with explanation."""
        response = client.post("/analyze", json={"code": "x = 1 / 0"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "ZeroDivisionError" in data["message"]
        assert "zero" in data["explanation"].lower()
        assert data["suggestion"] != ""
        # Full traceback should be present but paths cleaned
        assert "stderr" in data
        assert "tmp" not in data["stderr"]

    def test_clean_code_returns_success(self):
        """Code with no errors should return status=success."""
        response = client.post("/analyze", json={"code": "x = 40 + 2"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_stdout_included_on_success(self):
        """stdout from a clean run should be included in the response."""
        response = client.post("/analyze", json={"code": "print('result:', 42)"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "stdout" in data
        assert "42" in data["stdout"]

    def test_name_error_is_explained(self):
        """A NameError should produce a relevant explanation."""
        response = client.post("/analyze", json={"code": "print(undefined_var)"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "NameError" in data["message"]
        assert data["explanation"] != ""

    # ------------------------------------------------------------------
    # Fix-proposal integration tests (Phase 3 + fixer)
    # ------------------------------------------------------------------

    def test_zero_division_with_literal_zero_returns_fixed_code(self):
        """
        When the fixer can produce a safe fix, fixed_code, fix_message,
        and fix_explanation must all be present in the response.
        """
        response = client.post("/analyze", json={"code": "x = 10 / 0"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        # Existing diagnosis fields must still be present
        assert "ZeroDivisionError" in data["message"]
        assert data["explanation"] != ""
        assert data["suggestion"] != ""
        # Fixer fields
        assert "fixed_code" in data, "fixer should propose a fix for literal / 0"
        assert "10 / 1" in data["fixed_code"]
        assert "fix_message" in data
        assert "fix_explanation" in data
        assert data["fix_message"] != ""
        assert data["fix_explanation"] != ""

    def test_zero_division_fixed_code_does_not_overwrite_diagnosis(self):
        """
        The fixer's fix_explanation must NOT replace the ai_service explanation.
        Both must coexist in the response under separate keys.
        """
        response = client.post("/analyze", json={"code": "result = 5 / 0"})
        data = response.json()
        # ai_service diagnosis
        assert "explanation" in data
        assert "suggestion" in data
        # fixer output is in its own keys
        assert "fix_explanation" in data
        # They are separate strings
        assert data["explanation"] != data["fix_explanation"]

    def test_runtime_error_without_safe_fix_has_no_fixed_code(self):
        """
        When the fixer cannot propose a safe fix, fixed_code must be absent
        and the existing diagnosis must still be returned normally.
        """
        # NameError with no literal assignment in the code — fixer returns success=False
        response = client.post("/analyze", json={"code": "print(totally_unknown)"})
        data = response.json()
        assert data["status"] == "error"
        assert "NameError" in data["message"]
        assert data["explanation"] != ""
        assert data["suggestion"] != ""
        # No fix available — these keys must be absent
        assert "fixed_code" not in data
        assert "fix_message" not in data
        assert "fix_explanation" not in data

    def test_name_error_with_inferrable_value_returns_fixed_code(self):
        """
        NameError where the missing variable has a literal assignment later
        in the code should trigger a successful fix proposal.
        """
        code = "print(count)\ncount = 0"
        response = client.post("/analyze", json={"code": code})
        data = response.json()
        assert data["status"] == "error"
        assert "NameError" in data["message"]
        assert "fixed_code" in data, "fixer should prepend count = 0"
        assert "count = 0" in data["fixed_code"]
        assert data["fix_message"] != ""

    def test_syntax_error_path_unaffected_by_fixer(self):
        """
        Phase 1 (SyntaxError) returns before Phase 3 is ever reached.
        The fixer must never be called for syntax errors.
        fix_message and fix_explanation must not appear in syntax-error responses.
        """
        response = client.post("/analyze", json={"code": "def broken("})
        data = response.json()
        assert data["status"] == "error"
        assert "Syntax Error" in data["message"]
        # These fixer keys must be absent from syntax-error responses
        assert "fix_message" not in data
        assert "fix_explanation" not in data

    def test_success_path_unaffected_by_fixer(self):
        """
        Clean code that executes without errors must not include any fixer fields.
        """
        response = client.post("/analyze", json={"code": "x = 1 + 1"})
        data = response.json()
        assert data["status"] == "success"
        assert "fix_message" not in data
        assert "fix_explanation" not in data
        assert "fixed_code" not in data

    # ------------------------------------------------------------------
    # Regression-test generation integration tests (Phase 3 + test_generator)
    # ------------------------------------------------------------------

    def test_zero_division_with_literal_zero_includes_regression_test(self):
        """
        ZeroDivisionError with a literal zero divisor should include a
        regression_test field containing valid Python source.
        """
        import ast as _ast
        response = client.post("/analyze", json={"code": "x = 10 / 0"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        # regression_test must be present and parse cleanly
        assert "regression_test" in data, (
            "Expected regression_test key for ZeroDivisionError with literal 0"
        )
        test_src = data["regression_test"]
        assert isinstance(test_src, str) and test_src.strip() != ""
        assert _ast.parse(test_src)  # must be valid Python

    def test_zero_division_regression_test_uses_pytest_raises(self):
        """The generated test for a literal-zero divisor must use pytest.raises."""
        response = client.post("/analyze", json={"code": "result = 5 / 0"})
        data = response.json()
        assert "regression_test" in data
        assert "pytest.raises" in data["regression_test"]
        assert "ZeroDivisionError" in data["regression_test"]

    def test_name_error_includes_regression_test(self):
        """
        NameError with a recognisable missing name should include a
        regression_test field in the response.
        """
        import ast as _ast
        response = client.post("/analyze", json={"code": "print(missing_var)"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "regression_test" in data, (
            "Expected regression_test key for NameError with extractable name"
        )
        test_src = data["regression_test"]
        assert isinstance(test_src, str) and test_src.strip() != ""
        assert _ast.parse(test_src)

    def test_regression_test_absent_for_unsupported_error_type(self):
        """
        For error types the generator does not support (e.g. ValueError),
        regression_test must be absent and the response must remain valid.
        """
        # int('abc') raises ValueError — generator returns success=False
        response = client.post("/analyze", json={"code": "int('abc')"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        # generator cannot handle ValueError → key must be absent
        assert "regression_test" not in data

    def test_regression_test_does_not_overwrite_existing_fields(self):
        """
        Adding regression_test must not remove or overwrite explanation,
        suggestion, fix_message, or fix_explanation.
        """
        response = client.post("/analyze", json={"code": "x = 10 / 0"})
        data = response.json()
        assert "explanation" in data
        assert "suggestion" in data
        assert "fix_message" in data
        assert "fix_explanation" in data
        assert "regression_test" in data

    def test_regression_test_absent_on_success_path(self):
        """
        Clean code that runs without errors must not include regression_test.
        """
        response = client.post("/analyze", json={"code": "x = 1 + 1"})
        data = response.json()
        assert data["status"] == "success"
        assert "regression_test" not in data

    def test_regression_test_absent_on_syntax_error_path(self):
        """
        Phase 1 (SyntaxError) returns before Phase 3 is reached.
        regression_test must never appear in syntax-error responses.
        """
        response = client.post("/analyze", json={"code": "def broken("})
        data = response.json()
        assert data["status"] == "error"
        assert "Syntax Error" in data["message"]
        assert "regression_test" not in data


# ══════════════════════════════════════════════════════════════════════
# POST /verify tests
# ══════════════════════════════════════════════════════════════════════

class TestVerifyEndpoint:

    def test_working_fix_returns_success(self):
        """Fixed code that runs cleanly should return success=True."""
        response = client.post("/verify", json={
            "original_code": "x = 1 / 0",
            "fixed_code": "x = 1 / 1",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["success"] is True
        assert data["timed_out"] is False

    def test_broken_fix_returns_error(self):
        """Fixed code that still raises should return success=False."""
        response = client.post("/verify", json={
            "original_code": "x = 1 / 0",
            "fixed_code": "x = 1 / 0",   # intentionally still broken
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["success"] is False
        assert data["timed_out"] is False
        assert "ZeroDivisionError" in data["error"]

    def test_verify_stdout_included_when_present(self):
        """stdout from successful fixed code should be in the response."""
        response = client.post("/verify", json={
            "original_code": "x = 1 / 0",
            "fixed_code": "print('fixed!')",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "stdout" in data
        assert "fixed!" in data["stdout"]

    def test_original_code_is_not_executed(self):
        """original_code that would crash must not affect the result."""
        response = client.post("/verify", json={
            "original_code": "while True: pass",   # would timeout if run
            "fixed_code": "x = 1",
        })
        assert response.status_code == 200
        data = response.json()
        # Result must be clean — original_code was never executed
        assert data["success"] is True
        assert data["timed_out"] is False
