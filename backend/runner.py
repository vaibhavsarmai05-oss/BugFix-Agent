"""
runner.py
---------
Safe, isolated Python code executor for BugFix Agent.
Standard library only — no exec(), no eval(), no in-process execution.

Public interface
----------------
    run_code(code: str) -> dict
"""

import subprocess
import sys
import tempfile
import os


def run_code(code: str) -> dict:
    """
    Write `code` to a temporary file and execute it in a fresh Python
    subprocess.  The subprocess is killed after 5 seconds.

    The submitted code never runs inside the FastAPI process — it is always
    a completely separate child process.

    Parameters
    ----------
    code : str
        The Python source code to execute.

    Returns
    -------
    dict with keys:
        success    : bool   – True if the process exited with code 0
        stdout     : str    – Everything written to stdout
        stderr     : str    – Everything written to stderr (includes traceback)
        returncode : int    – OS exit code (0 = clean, 1 = unhandled exception)
        error      : str    – The last line of stderr, i.e. the exception
                              summary ("ExcType: message"), or "" if none
        timed_out  : bool   – True if execution exceeded the 5-second limit
    """
    # -- Write code to a self-deleting temporary file ------------------------
    # delete=False is required on Windows because the subprocess needs to open
    # the file by name; we delete it manually in the finally block.
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    )
    try:
        tmp.write(code)
        tmp.flush()
        tmp.close()

        # -- Run the temp file in a child Python process ---------------------
        try:
            result = subprocess.run(
                [sys.executable, tmp.name],
                capture_output=True,
                text=True,
                timeout=5,
            )

            stdout = result.stdout
            stderr = result.stderr
            returncode = result.returncode

            # Extract the exception summary from the last non-empty line of
            # stderr, e.g. "ZeroDivisionError: division by zero".
            # That is the most useful single piece of information for the
            # analysis layer.
            error = _last_error_line(stderr)

            return {
                "success": returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "returncode": returncode,
                "error": error,
                "timed_out": False,
            }

        except subprocess.TimeoutExpired:
            # The child process is automatically killed by Python when
            # TimeoutExpired is raised from subprocess.run().
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "returncode": -1,
                "error": "TimeoutError: code execution exceeded the 5-second limit",
                "timed_out": True,
            }

    finally:
        # Always remove the temp file, even if an unexpected error occurs.
        try:
            os.remove(tmp.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _last_error_line(stderr: str) -> str:
    """
    Return the last non-empty line of stderr.

    Python tracebacks end with the exception summary on the final line:

        Traceback (most recent call last):
          File "...", line N, in <module>
            ...
        ZeroDivisionError: division by zero   ← this is what we want

    Returns an empty string if stderr is empty or contains only whitespace.
    """
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else ""
