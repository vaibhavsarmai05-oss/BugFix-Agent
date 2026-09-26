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
