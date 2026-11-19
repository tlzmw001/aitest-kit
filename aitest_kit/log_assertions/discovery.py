"""Read generated step metadata without executing test modules."""
import ast
from pathlib import Path
import tokenize


def plan_sources(tree):
    sources = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "__aitest_log_step":
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords}
        source = keywords.get("source_id")
        if not isinstance(source, ast.Constant) or not isinstance(source.value, str) or not source.value:
            continue
        rules = keywords.get("rules")
        cleanup = any(
            isinstance(item, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value == "cleanup"
                    and isinstance(v, ast.Constant) and v.value == "on_success" for k, v in zip(item.keys, item.values))
            for item in (rules.elts if isinstance(rules, ast.List) else ())
        )
        sources[source.value] = sources.get(source.value, False) or cleanup
    return sources


def has_log_plans(files):
    for filename in files:
        try:
            with tokenize.open(Path(filename)) as stream:
                source = stream.read()
        except FileNotFoundError:
            continue
        if "__aitest_log_step" not in source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue  # pytest reports syntax failures through the normal collection path.
        if plan_sources(tree):
            return True
    return False


def planned_steps(filename):
    """Return statically declared request steps keyed by their pytest owner."""
    with tokenize.open(Path(filename)) as stream:
        tree = ast.parse(stream.read(), filename=str(filename))
    result = {}
    for klass in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        for function in (node for node in klass.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            steps = []
            for node in ast.walk(function):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "__aitest_log_step"):
                    continue
                keywords = {kw.arg: kw.value for kw in node.keywords}
                try:
                    steps.append({"step": ast.literal_eval(keywords["request_step"]),
                                  "source": ast.literal_eval(keywords["source_id"]),
                                  "rules": ast.literal_eval(keywords["rules"])})
                except (KeyError, ValueError, SyntaxError):
                    continue
            if steps:
                result[f"{klass.name}::{function.name}"] = steps
    return result
