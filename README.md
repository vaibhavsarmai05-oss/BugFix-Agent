# BugFix Agent

An AI-assisted Python debugging tool built for the IBM Bob Hackathon.

BugFix Agent accepts Python source code, executes it in a separate subprocess with a timeout, diagnoses runtime and syntax errors, proposes fixes for recognised error patterns, generates regression tests, and verifies whether a proposed fix resolves the problem.

---

## Table of Contents

1. [Overview](#overview)
2. [Problem](#problem)
3. [Solution](#solution)
4. [How It Works](#how-it-works)
5. [Features](#features)
6. [Tech Stack](#tech-stack)
7. [Project Structure](#project-structure)
8. [Running Locally](#running-locally)
9. [API Endpoints](#api-endpoints)
10. [Testing](#testing)
11. [IBM Bob Usage](#ibm-bob-usage)
12. [Limitations](#limitations)
13. [Future Improvements](#future-improvements)

---

## Overview

BugFix Agent is a student-built tool that walks through the core loop of debugging:

**Bug → Diagnose → Fix → Test → Verify**

A user pastes Python code into a web interface. The backend executes the code, identifies the error, explains what went wrong, and — where the error matches a known pattern — proposes a concrete fix, generates a pytest regression test, and verifies that the fix resolves the problem.

---

## Problem

Debugging is one of the most time-consuming parts of writing code, especially for students and less experienced developers. Reading a raw Python traceback and knowing what to do about it requires context that is not always obvious. There is no single tool that takes code, runs it, explains the error in plain English, suggests a fix, generates a test to guard against regression, and confirms the fix works — all in one step.

---

## Solution

BugFix Agent automates the full debugging feedback loop in a single web interface:

- Paste code → click Analyze
- See a plain-English explanation of the error and a concrete suggestion
- If the error matches a supported pattern, receive a proposed fix inline
- Copy the fix or click Verify Fix to confirm it runs cleanly
- Copy the generated regression test to add to your test suite

The analysis, fix generation, and test generation are all deterministic and rule-based — no external AI API is called at runtime.

---

## How It Works

```
User pastes code
      │
      ▼
Phase 1 — Syntax check (ast.parse)
      │  SyntaxError → return explanation + suggestion (+ fix if unclosed paren)
      │
      ▼
Phase 2 — Execute in isolated subprocess (5-second timeout)
      │  Timeout      → return timeout message
      │  Success      → return stdout
      │
      ▼
Phase 3 — Runtime error
      │
      ├─ ai_service.py   → matches error type against a catalogue of known errors
      │                     returns plain-English explanation + suggestion
      │
      ├─ core/fixer.py   → applies rule-based rewrite rules for recognised patterns
      │                     returns proposed fixed_code (or nothing, if unsupported)
      │
      └─ core/test_generator.py → generates a minimal pytest regression test
                                   for recognised patterns (or nothing, if unsupported)

/verify endpoint — reruns fixed_code in an isolated subprocess
                   returns pass or fail
```

---

## Features

- **Syntax error detection** — catches and explains common syntax problems (unclosed parentheses, unterminated strings, missing colons) before executing
- **Isolated execution** — code runs in a separate subprocess with a 5-second hard timeout; the FastAPI process is never exposed to user code
- **Plain-English error explanations** — 20+ known Python exception types are matched against a catalogue with actionable suggestions
- **Proposed fixes** — deterministic rewrite rules handle: literal zero divisors, undefined variables with inferable values, and single unclosed parentheses
- **Regression test generation** — produces a minimal pytest test for: `ZeroDivisionError` (empty-list average pattern and literal zero divisor) and `NameError` with an extractable variable name
- **Fix verification** — the `/verify` endpoint reruns the proposed fix and reports a clear pass or fail
- **Clean frontend** — plain HTML/CSS/JS, no frameworks; Copy and Verify buttons; all user content is HTML-escaped

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, FastAPI, Uvicorn |
| Execution | `subprocess` + `tempfile` (standard library) |
| Frontend | HTML, CSS, Vanilla JavaScript |
| Testing | pytest |
| Dev environment | IBM Bob 2.0 |

No external AI API is called at runtime. All analysis is performed by deterministic Python code.

---

## Project Structure

```
ibm-bob-hackathon/
├── backend/
│   ├── app.py               # FastAPI application — /analyze and /verify endpoints
│   ├── ai_service.py        # Rule-based error catalogue (explanation + suggestion)
│   ├── runner.py            # Subprocess executor with 5-second timeout
│   ├── test_bugfix_agent.py # Backend integration tests
│   └── requirements.txt     # Backend dependencies
│
├── core/
│   ├── fixer.py             # Rule-based fix proposer
│   └── test_generator.py    # Rule-based regression-test generator
│
├── frontend/
│   ├── index.html           # Single-page UI
│   ├── script.js            # Fetch calls, DOM rendering, copy/verify handlers
│   └── style.css            # Styling
│
├── tests/
│   └── test_analyzer.py     # Unit tests for core/test_generator.py
│
├── demo_project/
│   └── calculator_bug/
│       ├── calculator.py    # Demo: calculate_average() with empty-list guard
│       └── tests/
│           └── test_calculator.py  # Demo pytest suite
│
└── requirements.txt         # Top-level dependencies (pytest)
```

---

## Running Locally

### Prerequisites

- Python 3.10 or later
- pip

### 1. Clone the repository

```bash
git clone <repository-url>
cd ibm-bob-hackathon
```

### 2. Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Start the backend

```bash
cd backend
uvicorn app:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### 4. Open the frontend

Open `frontend/index.html` directly in a browser. No build step or server is required for the frontend.

> The frontend fetches from `http://127.0.0.1:8000` — the backend must be running before you use the UI.

---

## API Endpoints

### `GET /`

Health check.

**Response**
```json
{ "message": "BugFix Agent is running!" }
```

---

### `POST /analyze`

Analyze a Python code snippet. Executes the code in an isolated subprocess and returns a diagnosis, and optionally a proposed fix, regression test, and stdout.

**Request body**
```json
{ "code": "x = 1 / 0" }
```

**Response — successful execution**
```json
{
  "status": "success",
  "message": "Code executed successfully with no errors.",
  "stdout": "..."          // present only when the code produced output
}
```

**Response — error**
```json
{
  "status": "error",
  "message": "ZeroDivisionError: division by zero",
  "explanation": "The program attempted to divide a number by zero...",
  "suggestion": "Add a guard before the division...",
  "stderr": "Traceback (most recent call last):\n  ...",

  // Present only when the fixer supports this error pattern:
  "fixed_code": "x = 1 / 1",
  "fix_message": "Replaced the literal zero divisor with 1...",
  "fix_explanation": "Dividing by zero is undefined...",

  // Present only when the test generator supports this error pattern:
  "regression_test": "import pytest\n\ndef test_division_by_zero_raises():..."
}
```

Syntax errors return early (no subprocess is run):

```json
{
  "status": "error",
  "message": "Syntax Error: '(' was never closed at line 1",
  "explanation": "An opening parenthesis was found without...",
  "suggestion": "Add the missing closing parenthesis...",
  "fixed_code": "print('hi')"   // present for single unclosed-paren case only
}
```

---

### `POST /verify`

Run a proposed fix in an isolated subprocess and report whether it executes cleanly.

**Request body**
```json
{
  "original_code": "x = 1 / 0",
  "fixed_code":    "x = 1 / 1"
}
```

`original_code` is accepted for auditing purposes but is not executed.

**Response — pass**
```json
{
  "status": "success",
  "success": true,
  "message": "Fixed code executed successfully with no errors.",
  "timed_out": false,
  "stdout": "..."   // present only when the fixed code produced output
}
```

**Response — fail**
```json
{
  "status": "error",
  "success": false,
  "message": "The fixed code still produces an error.",
  "timed_out": false,
  "error": "ZeroDivisionError: division by zero"
}
```

---

## Testing

Tests are split into two suites:

| Suite | File | What it covers |
|---|---|---|
| Unit | `tests/test_analyzer.py` | `core/test_generator.py` — all rule branches and edge cases |
| Integration | `backend/test_bugfix_agent.py` | `runner.run_code()`, `POST /analyze`, `POST /verify` |

### Run from the repository root

```bash
cd ibm-bob-hackathon
python -m pytest tests/test_analyzer.py backend/test_bugfix_agent.py -v
```

**Current result: 53 passed, 1 warning** (the warning is a pre-existing `httpx`/`starlette` deprecation notice, not a test failure).

### Run the demo project tests

```bash
cd demo_project/calculator_bug
python -m pytest tests/ -v
```

---

## IBM Bob Usage

IBM Bob 2.0 was used as the primary development environment throughout this project.

Bob assisted with:

- **Planning** — breaking the overall workflow into phases (execute → diagnose → fix → test → verify) and deciding what each module should own
- **Implementation** — writing initial versions of `ai_service.py`, `runner.py`, `fixer.py`, `test_generator.py`, and `app.py`, then iterating on each based on test results
- **Debugging** — diagnosing test failures, tracing import path issues (the `sys.path.insert` pattern for `core/`), and fixing edge cases in the regex rules
- **Testing** — generating and refining the pytest test suites for both unit and integration coverage
- **Refinement** — iterating on the frontend to add the Proposed Fix, Regression Test, and Verify Fix sections

All code was reviewed, tested, and verified by the developer. The test results reported above reflect actual runs on the final codebase, not claimed results.

---

## Limitations

- **Rule-based analysis only.** The current debugging intelligence is entirely deterministic. `ai_service.py` matches error type prefixes against a fixed catalogue. There is no LLM or machine learning involved.
- **Fix generation covers a small set of patterns.** Automatic fixes are only produced for: a literal zero divisor (`x / 0`), a `NameError` where the missing variable has a literal assignment elsewhere in the same code, and a single unclosed parenthesis. All other errors are diagnosed but not fixed automatically.
- **Regression test generation is similarly limited.** Tests are generated for `ZeroDivisionError` (empty-list average and literal zero divisor patterns) and `NameError` with an extractable variable name. Other error types receive no generated test.
- **The subprocess executor is not a full sandbox.** Code runs in a child process with a 5-second timeout, but there are no filesystem, network, or resource restrictions beyond what the OS enforces.
- **Python only.** The tool is scoped to Python code. Other languages are not supported.
- **No persistent storage.** Results are not saved; everything is stateless per request.

---

## Future Improvements

- Integrate an LLM (e.g. via watsonx.ai) for open-ended error analysis and fix generation beyond the current rule catalogue
- Expand the fixer and test generator to cover more error patterns
- Add resource limits to the subprocess executor (CPU, memory, filesystem writes)
- Support multi-file projects, not just single code snippets
- Persist analysis history so users can revisit previous results
- Add syntax highlighting to code blocks in the frontend
- Support other languages beyond Python
