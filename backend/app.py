from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import ast

app = FastAPI(title="BugFix Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "BugFix Agent is running!"}


@app.post("/analyze")
def analyze_code(data: dict):
    code = data.get("code", "")

    try:
        ast.parse(code)

        return {
            "status": "success",
            "message": "No syntax errors detected."
        }

    except SyntaxError as error:
        explanation = f"Python found a syntax problem on line {error.lineno}."

        if error.msg == "'(' was never closed":
            explanation = (
                "An opening parenthesis was found without a matching "
                "closing parenthesis."
            )

        fixed_code = code

        if error.msg == "'(' was never closed":
            fixed_code = code + ")"

        return {
            "status": "error",
            "message": f"Syntax Error: {error.msg} at line {error.lineno}",
            "explanation": explanation,
            "suggestion": "Check the brackets, quotes, and punctuation around this line.",
            "fixed_code": fixed_code
        }