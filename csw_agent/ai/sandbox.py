"""AST-based safety check for Claude-generated code before exec()."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

# Imports that the generated code is allowed to perform.
ALLOWED_IMPORTS = frozenset({"json", "datetime", "time", "re", "math", "collections", "itertools"})

# Names available in the exec globals; bare attribute access on these is fine.
KNOWN_GLOBALS = frozenset(
    {
        "api_call",
        "tabulate",
        "json",
        "datetime",
        "time",
        "rows",
        "Counter",
        "defaultdict",
        "to_bool",
        "is_blank",
        "display_value",
        "to_number",
        "safe_pct",
    }
)

# Builtin names whose use should be flagged as suspicious.
BANNED_BUILTINS = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "memoryview",
        "exit",
        "quit",
    }
)

# Attribute access patterns that indicate destructive operations.
DESTRUCTIVE_ATTRS = frozenset({"delete", "post", "put", "patch"})


@dataclass(slots=True)
class SandboxReport:
    """Result of validating a code block."""

    is_safe: bool
    has_destructive_intent: bool = False
    violations: list[str] = field(default_factory=list)

    def reason(self) -> str:
        return "; ".join(self.violations)


def validate(code: str, *, allow_destructive: bool = False) -> SandboxReport:
    """Validate Claude-generated code. Returns a report with any violations found."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return SandboxReport(is_safe=False, violations=[f"syntax error at line {exc.lineno}: {exc.msg}"])

    visitor = _Validator()
    visitor.visit(tree)
    destructive = visitor.destructive_calls
    hard_violations = visitor.violations

    is_safe = not hard_violations and (allow_destructive or not destructive)
    if destructive and not allow_destructive:
        hard_violations = [*hard_violations, *(f"destructive call: {d}" for d in destructive)]
    return SandboxReport(
        is_safe=is_safe,
        has_destructive_intent=bool(destructive),
        violations=hard_violations,
    )


class _Validator(ast.NodeVisitor):
    """Walks an AST collecting safety violations."""

    def __init__(self) -> None:
        self.violations: list[str] = []
        self.destructive_calls: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root not in ALLOWED_IMPORTS:
                self.violations.append(f"disallowed import: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        root = (node.module or "").split(".")[0]
        if root not in ALLOWED_IMPORTS:
            self.violations.append(f"disallowed import from: {node.module}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self.violations.append(f"dunder access: .{node.attr}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in BANNED_BUILTINS:
            self.violations.append(f"banned name: {node.id}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._check_destructive_call(node)
        self._check_dynamic_attr(node)
        self.generic_visit(node)

    def _check_destructive_call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr.lower()
            if attr in DESTRUCTIVE_ATTRS:
                target = _attr_chain(node.func)
                self.destructive_calls.append(target)
            return
        if isinstance(node.func, ast.Name) and node.func.id == "api_call" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                method = first.value.upper()
                if method in {"DELETE", "PUT", "PATCH"}:
                    self.destructive_calls.append(f"api_call('{method}', ...)")
                elif method == "POST":
                    path = _post_path(node)
                    if path and not _is_readonly_post(path):
                        self.destructive_calls.append(f"api_call('POST', '{path}')")

    def _check_dynamic_attr(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in {"getattr", "setattr", "delattr", "hasattr"}:
            self.violations.append(f"dynamic attribute access: {node.func.id}()")


READONLY_POST_PREFIXES = (
    "/policies/stats",
    "/flowsearch",
    "/inventory/search",
    "/inventory/count",
    "/inventory/cves",
)


def _is_readonly_post(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in READONLY_POST_PREFIXES)


def _post_path(node: ast.Call) -> str | None:
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
        value = node.args[1].value
        return value if isinstance(value, str) else None
    return None


def _attr_chain(node: ast.Attribute) -> str:
    parts: list[str] = [node.attr]
    current: ast.AST = node.value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))
