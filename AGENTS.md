# BugFix Agent

## Project Goal
Build an AI-powered developer tool that helps diagnose and fix bugs in software repositories.

## Core Workflow
Repository → Analyze → Diagnose → Propose Fix → Generate Regression Test → Run Tests → Verify → Report

## Current MVP
The MVP will focus on Python repositories.

It should:
1. Analyze a repository.
2. Accept a bug report or failing test.
3. Identify the likely root cause.
4. Propose a minimal code fix.
5. Generate a regression test.
6. Run the test suite.
7. Verify that the bug is fixed.
8. Produce a clear final report.

## Technology
- Python
- Streamlit
- pytest
- Git/GitHub
- IBM Bob 2.0 for AI-assisted development

## Development Principles
- Keep the MVP simple.
- Prefer readable Python.
- Make small, focused changes.
- Do not add unnecessary dependencies.
- Always test changes.
- Do not claim a bug is fixed unless verification tests pass.

## Demo
The project will include a deliberately broken Python calculator example.

Expected workflow:
Failing test → Diagnose ZeroDivisionError → Propose fix → Add regression test → Run pytest → All tests pass.