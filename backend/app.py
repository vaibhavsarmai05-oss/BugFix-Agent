from fastapi import FastAPI

app = FastAPI(title="BugFix Agent")

@app.get("/")
def home():
    return {"message": "BugFix Agent is running!"}