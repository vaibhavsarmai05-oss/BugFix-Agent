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

        else:
            suggestion = (
                "Check the brackets, quotes, and punctuation around "
                "the reported line."
            )

        result = {
            "status": "error",
            "message": f"Syntax Error: {error.msg} at line {error.lineno}",
            "explanation": explanation,
            "suggestion": suggestion
        }

        if fixed_code:
            result["fixed_code"] = fixed_code

        return result