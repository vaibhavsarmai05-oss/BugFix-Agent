from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import ast
import sys
import os

from backend.ai_service import analyze_with_ai
from backend.runner import run_code

# core/ lives one level above backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.fixer import propose_fix
from core.test_generator import generate_regression_test

app = FastAPI(title="BugFix Agent")

# Serve frontend CSS and JavaScript
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return FileResponse(
        os.path.join(frontend_dir, "index.html")
    )


@app.post("/analyze")
def analyze_code(data: dict):
    code = data.get("code", "")

    try:
        ast.parse(code)
    except SyntaxError as e:
        return {
            "success": False,
            "type": "syntax_error",
            "message": f"Syntax Error: {e.msg} at line {e.lineno}",
            "error": str(e),
        }

    result = run_code(code)

    if result["success"]:
        return {
            "success": True,
            "message": "Code executed successfully.",
            "stdout": result.get("stdout", ""),
        }

    error = result.get("error", "")

    ai_analysis = analyze_with_ai(code, str(error))

    fixed_code = propose_fix(code, error)

    regression_test = generate_regression_test(code, str(error))

    return {
        "success": False,
        "type": "runtime_error",
        "message": ai_analysis,
        "error": error,
        "fixed_code": fixed_code,
        "regression_test": regression_test,
    }


@app.post("/verify")
def verify_fix(data: dict):
    original_code = data.get("original_code", "")
    fixed_code = data.get("fixed_code", "")

    result = run_code(fixed_code)

    if result["success"]:
        return {
            "success": True,
            "stdout": result.get("stdout", ""),
        }

    return {
        "success": False,
        "error": result.get("error", ""),
    }


