"""Code Reviewer CLI: static analysis + AI explanations for Python files.

Usage: python reviewer.py path/to/file.py
The reviewed file is only read and parsed. It is never executed or modified.
"""

import argparse
import sys
from collections import Counter

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from analyzer import analyze, parse_source
from llm_client import LLMError, explain_issues

console = Console()
COLORS = {"High": "bold red", "Medium": "bold yellow", "Low": "bold cyan"}


def read_file(path):
    """Read the file or print a friendly error and exit."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        fail(f"File not found: {path}")
    except IsADirectoryError:
        fail(f"'{path}' is a directory, please give a Python file.")
    except UnicodeDecodeError:
        fail(f"'{path}' is not a UTF-8 text file.")
    except OSError as exc:
        fail(f"Could not read '{path}': {exc.strerror}")


def fail(message):
    console.print(Panel(message, title="Error", border_style="red"))
    sys.exit(1)


def show_issues(issues):
    table = Table(title="Static Analysis Findings", header_style="bold magenta")
    table.add_column("Line", justify="right")
    table.add_column("Severity")
    table.add_column("Issue")
    table.add_column("Description")
    for i in issues:
        table.add_row(str(i.line), f"[{COLORS[i.severity]}]{i.severity}[/]", i.kind, i.description)
    console.print(table)


def show_summary(issues):
    counts = Counter(i.severity for i in issues)
    parts = [f"[{COLORS[s]}]{s}: {counts[s]}[/]" for s in ("High", "Medium", "Low")]
    console.print(Panel(f"Total issues: [bold]{len(issues)}[/]   " + "   ".join(parts),
                        title="Summary", border_style="green" if not issues else "blue"))


def main():
    parser = argparse.ArgumentParser(description="Review a Python file and explain problems with AI.")
    parser.add_argument("file", help="path to the Python file to review")
    args = parser.parse_args()

    console.print(Panel(f"Reviewing [bold]{args.file}[/]", title="Code Reviewer CLI", border_style="blue"))

    source = read_file(args.file)
    try:
        tree = parse_source(source)
    except (SyntaxError, ValueError) as exc:
        where = f" on line {exc.lineno}" if getattr(exc, "lineno", None) else ""
        fail(f"Syntax error{where}: {getattr(exc, 'msg', exc)}\nFix it and run the reviewer again.")

    issues = analyze(tree)
    if not issues:
        console.print("[bold green]No issues found. Nice work![/]")
        show_summary(issues)
        return

    show_issues(issues)
    show_summary(issues)

    with console.status("Asking Gemini for explanations..."):
        try:
            explanation = explain_issues(issues, source)
        except LLMError as exc:
            explanation = None
            error = str(exc)
        except Exception as exc:  # never crash because of the AI part
            explanation = None
            error = f"Unexpected error ({type(exc).__name__})."

    if explanation:
        console.print(Panel(Markdown(explanation), title="AI Explanation & Suggested Fixes",
                            border_style="green"))
    else:
        console.print(Panel(f"{error}\nShowing static-analysis results only.",
                            title="AI explanation unavailable", border_style="yellow"))


if __name__ == "__main__":
    main()
