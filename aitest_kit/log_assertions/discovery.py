"""Read generated step metadata without executing test modules."""
import ast
import tokenize


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def iter_log_steps(tree):
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "__aitest_log_step"):
            continue
        keywords = {item.arg: item.value for item in node.keywords}
        try:
            step = ast.literal_eval(keywords["request_step"])
            anchor = ast.literal_eval(keywords["source_id"])
            rules = ast.literal_eval(keywords["rules"])
            if (not _text(step) or not _text(anchor) or not isinstance(rules, list) or not rules
                    or not all(isinstance(rule, dict) for rule in rules)):
                raise ValueError
            by_source = group_log_rules(anchor, rules)
        except (KeyError, ValueError, SyntaxError, TypeError) as exc:
            raise ValueError(f"invalid generated log step metadata at line {node.lineno}") from exc
        for source, indices in by_source.items():
            yield {"step": step, "source": source, "rules": [rules[i] for i in indices]}


def group_log_rules(anchor, rules):
    if not rules:
        raise ValueError("log request step has no rules")
    sourced = any("source_id" in rule for rule in rules)
    by_source = {}
    for index, rule in enumerate(rules):
        source = rule.get("source_id") if sourced else anchor
        if not _text(source):
            raise ValueError("invalid log rule source")
        by_source.setdefault(source, []).append(index)
    return by_source


def plan_sources(tree):
    return source_permissions(iter_log_steps(tree))


def source_permissions(plans):
    sources = {}
    for plan in plans:
        source = plan["source"]
        cleanup = any(rule.get("cleanup") == "on_success" for rule in plan["rules"])
        sources[source] = sources.get(source, False) or cleanup
    return sources


def has_log_plans(files):
    for filename in files:
        try:
            with tokenize.open(filename) as stream:
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
    """Return statically declared step/source groups keyed by their pytest owner."""
    with tokenize.open(filename) as stream:
        tree = ast.parse(stream.read(), filename=str(filename))
    result = {}
    for klass in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        for function in (node for node in klass.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            steps = list(iter_log_steps(function))
            if steps:
                result[f"{klass.name}::{function.name}"] = steps
    return result
