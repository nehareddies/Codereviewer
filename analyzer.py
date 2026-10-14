"""Static analysis of Python source using the built-in ast module.

The code is only parsed, never executed.
"""

import ast
from dataclasses import dataclass

MAX_NESTING = 3  # more than this many nested blocks is reported

FUNCTION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
SCOPE_TYPES = FUNCTION_TYPES + (ast.Lambda, ast.ClassDef)
BLOCK_TYPES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)


@dataclass
class Issue:
    line: int
    severity: str  # "High", "Medium" or "Low"
    kind: str
    description: str


def parse_source(source):
    """Parse source text into an AST. Raises SyntaxError on bad code."""
    return ast.parse(source)


def analyze(tree):
    """Run all checks and return issues sorted by line number."""
    issues = []
    issues += check_docstrings(tree)
    issues += check_nesting(tree)
    issues += check_unused_variables(tree)
    return sorted(issues, key=lambda i: i.line)


# --- Check 1: missing docstrings -------------------------------------------

def check_docstrings(tree):
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, FUNCTION_TYPES) and ast.get_docstring(node) is None:
            # Private helpers (leading underscore) matter a bit less.
            severity = "Low" if node.name.startswith("_") else "Medium"
            issues.append(Issue(node.lineno, severity, "Missing docstring",
                                f"Function '{node.name}' has no docstring."))
    return issues


# --- Check 2: deeply nested code -------------------------------------------

def check_nesting(tree):
    """Report the deepest block in each function (or at module level)."""
    issues = []
    scopes = [tree] + [n for n in ast.walk(tree) if isinstance(n, FUNCTION_TYPES)]
    for scope in scopes:
        depth, line = _deepest_block(scope, 0, scope.body[0].lineno if scope.body else 1)
        if depth > MAX_NESTING:
            severity = "High" if depth >= MAX_NESTING + 2 else "Medium"
            name = "module level" if scope is tree else f"function '{scope.name}'"
            issues.append(Issue(line, severity, "Deep nesting",
                                f"Code in {name} is nested {depth} levels deep."))
    return issues


def _deepest_block(node, depth, line):
    """Return (max depth, line of deepest block) inside node.

    Nested functions are skipped: they are analyzed as their own scope.
    """
    best = (depth, line)
    for child in ast.iter_child_nodes(node):
        if isinstance(child, SCOPE_TYPES):
            continue
        if isinstance(child, BLOCK_TYPES):
            result = _deepest_block(child, depth + 1, child.lineno)
        else:
            result = _deepest_block(child, depth, line)
        if result[0] > best[0]:
            best = result
    return best


# --- Check 3: unused local variables ---------------------------------------

def check_unused_variables(tree):
    issues = []
    for func in ast.walk(tree):
        if not isinstance(func, FUNCTION_TYPES):
            continue

        # Names read anywhere in the function (including nested functions,
        # which may use them as closures).
        used = {n.id for n in ast.walk(func)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        # Names declared global/nonlocal are not true locals.
        for n in ast.walk(func):
            if isinstance(n, (ast.Global, ast.Nonlocal)):
                used.update(n.names)

        first_assigned = {}
        for name, line in _assigned_names(func):
            first_assigned.setdefault(name, line)

        for name, line in first_assigned.items():
            if name not in used and not name.startswith("_"):
                issues.append(Issue(line, "Low", "Unused variable",
                                    f"Variable '{name}' in '{func.name}' is assigned but never used."))
    return issues


def _assigned_names(func):
    """Yield (name, line) for simple assignments directly in this function."""
    stack = list(func.body)
    while stack:
        node = stack.pop()
        if isinstance(node, SCOPE_TYPES):
            continue  # separate scope
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id, target.lineno
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                yield node.target.id, node.target.lineno
        stack.extend(ast.iter_child_nodes(node))
