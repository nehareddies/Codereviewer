"""Web UI for Code Reviewer. Run with: python app.py  ->  http://127.0.0.1:5000

Uploaded files are only parsed with ast. They are never executed or saved.
"""

from collections import Counter

from flask import Flask, render_template, request

from analyzer import analyze, parse_source
from llm_client import LLMError, explain_issues

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1 MB upload limit

RANK = {"High": 3, "Medium": 2, "Low": 1}


def split_explanation(text):
    """Split AI text into ('text'|'code', content) parts so code gets its own box."""
    parts = []
    for i, chunk in enumerate(text.split("```")):
        if i % 2 == 1:  # inside a code fence: drop the language tag line
            first, _, rest = chunk.partition("\n")
            chunk = rest if first.strip().isalpha() or not first.strip() else chunk
            parts.append(("code", chunk.strip("\n")))
        elif chunk.strip():
            parts.append(("text", chunk.strip()))
    return parts


def review(filename, raw):
    """Return a dict of results (or an 'error') for the template."""
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": "That file is not UTF-8 text."}
    if not source.strip():
        return {"error": "The file is empty."}
    try:
        tree = parse_source(source)
    except (SyntaxError, ValueError) as exc:
        where = f" on line {exc.lineno}" if getattr(exc, "lineno", None) else ""
        return {"error": f"Syntax error{where}: {getattr(exc, 'msg', exc)}"}

    issues = analyze(tree)
    counts = Counter(i.severity for i in issues)

    flagged = {}  # line number -> worst severity on that line
    for i in issues:
        if RANK[i.severity] > RANK.get(flagged.get(i.line), 0):
            flagged[i.line] = i.severity
    code_lines = [(n, text, flagged.get(n))
                  for n, text in enumerate(source.splitlines(), start=1)]

    explanation, ai_error = None, None
    if issues:
        try:
            explanation = split_explanation(explain_issues(issues, source))
        except LLMError as exc:
            ai_error = str(exc)
        except Exception as exc:  # never crash because of the AI part
            ai_error = f"Unexpected error ({type(exc).__name__})."

    return {"filename": filename, "issues": issues, "counts": counts,
            "code_lines": code_lines, "explanation": explanation, "ai_error": ai_error}


@app.errorhandler(413)
def too_large(_):
    return render_template("templates/index.html", result={"error": "File too large (limit is 1 MB)."}), 413


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            result = {"error": "Please choose a Python file first."}
        elif not file.filename.lower().endswith(".py"):
            result = {"error": "Only .py files are supported."}
        else:
            result = review(file.filename, file.read())
    return render_template("index.html", result=result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)