"""
tests/test_analyzer.py
----------------------
Unit tests for core/test_generator.py — the regression-test generator.

Run from the repository root:
    pytest tests/test_analyzer.py -v
"""

import sys
import os
import ast

# core/ is a sibling of tests/ — resolve from this file's directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.test_generator import generate_regression_test


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_valid_python(source: str) -> bool:
    """Return True if `source` parses without a SyntaxError."""
    try:
        ast.parse(source)
        return True
    except SyntaxError:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# ZeroDivisionError — empty-list average pattern (sub-pattern A)
# ══════════════════════════════════════════════════════════════════════════════

BUGGY_AVERAGE = "def calculate_average(numbers):\n    return sum(numbers) / len(numbers)"
ZDIV_MSG = "ZeroDivisionError: division by zero"


class TestZeroDivisionAveragePattern:

    def test_success_flag_is_true(self):
        r = generate_regression_test(BUGGY_AVERAGE, ZDIV_MSG)
        assert r["success"] is True

    def test_test_code_key_present(self):
        r = generate_regression_test(BUGGY_AVERAGE, ZDIV_MSG)
        assert "test_code" in r

    def test_message_is_non_empty(self):
        r = generate_regression_test(BUGGY_AVERAGE, ZDIV_MSG)
        assert r["message"] != ""

    def test_generated_code_is_valid_python(self):
        r = generate_regression_test(BUGGY_AVERAGE, ZDIV_MSG)
        assert _is_valid_python(r["test_code"]), (
            "Generated test_code is not valid Python:\n" + r["test_code"]
        )

    def test_generated_code_contains_function_name(self):
        """The test function name should mention the detected function."""
        r = generate_regression_test(BUGGY_AVERAGE, ZDIV_MSG)
        assert "calculate_average" in r["test_code"]

    def test_generated_code_asserts_empty_list_returns_zero(self):
        """Key assertion: empty list → 0."""
        r = generate_regression_test(BUGGY_AVERAGE, ZDIV_MSG)
        assert "[]" in r["test_code"]
        assert "== 0" in r["test_code"]

    def test_generated_code_contains_import(self):
        """The test must import the function under test."""
        r = generate_regression_test(BUGGY_AVERAGE, ZDIV_MSG)
        assert "import" in r["test_code"]

    def test_alternative_param_name_is_used(self):
        """Pattern works for any parameter name, not just 'numbers'."""
        code = "def mean(values):\n    return sum(values) / len(values)"
        r = generate_regression_test(code, ZDIV_MSG)
        assert r["success"] is True
        assert "mean" in r["test_code"]
        assert "values" in r["test_code"]


# ══════════════════════════════════════════════════════════════════════════════
# ZeroDivisionError — literal zero divisor (sub-pattern B)
# ══════════════════════════════════════════════════════════════════════════════

LITERAL_ZERO_CODE = "result = 10 / 0"


class TestZeroDivisionLiteralPattern:

    def test_success_flag_is_true(self):
        r = generate_regression_test(LITERAL_ZERO_CODE, ZDIV_MSG)
        assert r["success"] is True

    def test_test_code_key_present(self):
        r = generate_regression_test(LITERAL_ZERO_CODE, ZDIV_MSG)
        assert "test_code" in r

    def test_generated_code_is_valid_python(self):
        r = generate_regression_test(LITERAL_ZERO_CODE, ZDIV_MSG)
        assert _is_valid_python(r["test_code"])

    def test_generated_code_uses_pytest_raises(self):
        """The test must assert that ZeroDivisionError is raised."""
        r = generate_regression_test(LITERAL_ZERO_CODE, ZDIV_MSG)
        assert "pytest.raises" in r["test_code"]
        assert "ZeroDivisionError" in r["test_code"]

    def test_floor_division_also_detected(self):
        r = generate_regression_test("x = 5 // 0", ZDIV_MSG)
        assert r["success"] is True
        assert "test_code" in r


# ══════════════════════════════════════════════════════════════════════════════
# ZeroDivisionError — unrecognised pattern → no test
# ══════════════════════════════════════════════════════════════════════════════

class TestZeroDivisionUnknownPattern:

    def test_variable_divisor_returns_no_test(self):
        """A divisor that is a variable cannot be safely tested automatically."""
        r = generate_regression_test("result = x / y", ZDIV_MSG)
        assert r["success"] is False
        assert "test_code" not in r
        assert r["message"] != ""

    def test_explanation_key_present_on_failure(self):
        r = generate_regression_test("result = x / y", ZDIV_MSG)
        assert "explanation" in r


# ══════════════════════════════════════════════════════════════════════════════
# NameError
# ══════════════════════════════════════════════════════════════════════════════

NAME_ERR_CODE = "print(missing_var)"
NAME_ERR_MSG = "NameError: name 'missing_var' is not defined"


class TestNameError:

    def test_success_flag_is_true(self):
        r = generate_regression_test(NAME_ERR_CODE, NAME_ERR_MSG)
        assert r["success"] is True

    def test_test_code_key_present(self):
        r = generate_regression_test(NAME_ERR_CODE, NAME_ERR_MSG)
        assert "test_code" in r

    def test_generated_code_is_valid_python(self):
        r = generate_regression_test(NAME_ERR_CODE, NAME_ERR_MSG)
        assert _is_valid_python(r["test_code"]), (
            "Generated test_code is not valid Python:\n" + r["test_code"]
        )

    def test_generated_code_uses_pytest_raises_name_error(self):
        r = generate_regression_test(NAME_ERR_CODE, NAME_ERR_MSG)
        assert "pytest.raises" in r["test_code"]
        assert "NameError" in r["test_code"]

    def test_missing_name_appears_in_test_function_name(self):
        r = generate_regression_test(NAME_ERR_CODE, NAME_ERR_MSG)
        assert "missing_var" in r["test_code"]

    def test_malformed_name_error_message_returns_no_test(self):
        """If the variable name cannot be extracted, no test should be generated."""
        r = generate_regression_test(NAME_ERR_CODE, "NameError: something unexpected")
        assert r["success"] is False
        assert "test_code" not in r


# ══════════════════════════════════════════════════════════════════════════════
# Unsupported / unknown error types
# ══════════════════════════════════════════════════════════════════════════════

class TestUnsupportedErrors:

    def test_value_error_returns_no_test(self):
        r = generate_regression_test("int('abc')", "ValueError: invalid literal")
        assert r["success"] is False
        assert "test_code" not in r

    def test_type_error_returns_no_test(self):
        r = generate_regression_test("1 + '2'", "TypeError: unsupported operand")
        assert r["success"] is False
        assert "test_code" not in r

    def test_unsupported_error_message_is_informative(self):
        r = generate_regression_test("x = 1", "AttributeError: no attribute 'foo'")
        assert r["message"] != ""
        assert "explanation" in r

    def test_exc_type_appears_in_failure_message(self):
        r = generate_regression_test("x = 1", "RuntimeError: something went wrong")
        assert "RuntimeError" in r["message"]
