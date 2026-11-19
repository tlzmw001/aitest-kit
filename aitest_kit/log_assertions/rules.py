"""Interpret the deferred assertion language over plain JSON values."""
from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any

from .values import LogInputError, freeze_expected, safe_copy, sensitive_name

_COMPARE = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_, ast.IsNot: operator.is_not,
}
_ARITHMETIC = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod,
}
_METHODS = {"startswith": (1,), "endswith": (1,), "strip": (0, 1),
            "lower": (0,), "upper": (0,), "get": (1, 2)}
_REGEX = {"regex_search": re.search, "regex_fullmatch": re.fullmatch}


def _validate(node: ast.AST, names: set[str], *, generator: bool = False) -> None:
    def child(item: ast.AST) -> None:
        _validate(item, names, generator=generator)

    if isinstance(node, ast.Constant):
        value = safe_copy(node.value)
        if type(value) is int and value.bit_length() > 4096:
            raise ValueError("integer exceeds 4096 bits")
    elif isinstance(node, ast.Name) and node.id in names:
        return
    elif isinstance(node, (ast.List, ast.Tuple, ast.BoolOp)):
        for item in node.elts if hasattr(node, "elts") else node.values:
            child(item)
    elif isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant) or type(key.value) is not str:
                raise ValueError("dictionary keys must be strings")
            child(value)
    elif isinstance(node, ast.Subscript):
        child(node.value)
        child(node.slice)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.UAdd, ast.USub)):
        child(node.operand)
    elif isinstance(node, ast.BinOp) and type(node.op) in _ARITHMETIC:
        child(node.left)
        child(node.right)
    elif isinstance(node, ast.Compare):
        child(node.left)
        for op, right in zip(node.ops, node.comparators):
            if type(op) not in _COMPARE:
                raise ValueError("unsupported comparison")
            if isinstance(op, (ast.Is, ast.IsNot)) and (
                not isinstance(right, ast.Constant) or type(right.value) not in (bool, type(None))
            ):
                raise ValueError("identity comparison requires None, True or False")
            child(right)
    elif isinstance(node, ast.Call) and not node.keywords:
        func = node.func
        if isinstance(func, ast.Attribute) and len(node.args) in _METHODS.get(func.attr, ()):
            child(func.value)
        elif isinstance(func, ast.Name) and func.id in _REGEX and len(node.args) == 2:
            pattern = node.args[0]
            if not isinstance(pattern, ast.Constant) or type(pattern.value) is not str or len(pattern.value) > 1024:
                raise ValueError("regex pattern must be a string literal of up to 1024 characters")
            try:
                re.compile(pattern.value)
            except (re.error, RecursionError, OverflowError) as exc:
                raise ValueError("invalid regular expression") from exc
        elif isinstance(func, ast.Name) and func.id in {"len", "any", "all"} and len(node.args) == 1:
            arg = node.args[0]
            if isinstance(arg, ast.GeneratorExp) and func.id != "len":
                if generator or len(arg.generators) != 1:
                    raise ValueError("only one generator clause is allowed")
                clause = arg.generators[0]
                if (clause.is_async or len(clause.ifs) > 1 or not isinstance(clause.target, ast.Name)
                        or clause.target.id.startswith("_") or clause.target.id in names
                        or clause.target.id in {"len", "any", "all", *_REGEX}):
                    raise ValueError("invalid generator clause")
                _validate(clause.iter, names, generator=True)
                for item in [*clause.ifs, arg.elt]:
                    _validate(item, names | {clause.target.id}, generator=True)
                return
        else:
            raise ValueError("unsupported function or method call")
        for arg in node.args:
            child(arg)
    else:
        raise ValueError(f"unsupported expression: {type(node).__name__}")


def parse_check(source: str) -> ast.Assert:
    if not isinstance(source, str) or len(source) > 4096:
        raise ValueError("check must be a string of up to 4096 characters")
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("check must be valid Python assertion syntax") from exc
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assert):
        raise ValueError("check must contain exactly one assert")
    check = tree.body[0]
    if check.msg is not None and not (isinstance(check.msg, ast.Constant) and type(check.msg.value) is str):
        raise ValueError("assert message must be a string literal")
    todo = [(check, 1)]
    count = 0
    while todo:
        node, depth = todo.pop()
        count += 1
        if count > 512 or depth > 32:
            raise ValueError("check exceeds AST budget")
        todo.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    _validate(check.test, {"events", "expected"})
    return check


class _Interpreter:
    def __init__(self) -> None:
        self.remaining = 100000
        self.failed_operands = None

    def spend(self) -> None:
        self.remaining -= 1
        if self.remaining < 0:
            raise ValueError("check execution budget exhausted")

    def run(self, node: ast.AST, names: dict[str, Any]) -> Any:
        self.spend()

        def value(child: ast.AST) -> Any:
            return self.run(child, names)

        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return names[node.id]
        if isinstance(node, ast.List):
            return [value(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(value(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return {key.value: value(item) for key, item in zip(node.keys, node.values)}
        if isinstance(node, ast.Subscript):
            container, key = value(node.value), value(node.slice)
            if type(container) not in (list, dict, tuple):
                raise TypeError("indexing requires a list, tuple or dictionary")
            return container[key]
        if isinstance(node, ast.BoolOp):
            result = None
            for item in node.values:
                result = value(item)
                if bool(result) == isinstance(node.op, ast.Or):
                    break
            return result
        if isinstance(node, ast.Compare):
            left = value(node.left)
            for op, expr in zip(node.ops, node.comparators):
                right = value(expr)
                if not _COMPARE[type(op)](left, right):
                    self.failed_operands = (left, right)
                    return False
                left = right
            return True
        if isinstance(node, ast.UnaryOp):
            operand = value(node.operand)
            if isinstance(node.op, ast.Not):
                return not operand
            operand = self._numeric(operand)
            return -operand if isinstance(node.op, ast.USub) else +operand
        if isinstance(node, ast.BinOp):
            left, right = self._numeric(value(node.left)), self._numeric(value(node.right))
            return self._numeric(_ARITHMETIC[type(node.op)](left, right))
        if isinstance(node, ast.Call):
            return self.call(node, names)
        raise ValueError("invalid validated node")

    @staticmethod
    def _numeric(value: Any) -> Any:
        if type(value) is int and value.bit_length() <= 4096:
            return value
        if type(value) is float and math.isfinite(value):
            return value
        raise ValueError("expected a finite number within the numeric budget")

    def call(self, node: ast.Call, names: dict[str, Any]) -> Any:
        func = node.func
        if isinstance(func, ast.Name) and func.id in {"any", "all"}:
            arg = node.args[0]
            if isinstance(arg, ast.GeneratorExp):
                values = self.generate(arg, names)
            else:
                values = self.run(arg, names)
                if type(values) is not list:
                    raise TypeError("any/all requires a list or a generator")
                values = self.iterate(values)
            return any(values) if func.id == "any" else all(values)
        args = [self.run(arg, names) for arg in node.args]
        if isinstance(func, ast.Attribute):
            target = self.run(func.value, names)
            if func.attr == "get" and type(target) is dict:
                return target.get(*args)
            if func.attr != "get" and type(target) is str:
                return getattr(target, func.attr)(*args)
            raise TypeError("invalid method receiver")
        if func.id == "len":
            return len(args[0])
        pattern, content = args
        if type(content) is not str or len(content) > 65536:
            raise ValueError("regex input must be a string of up to 65536 characters")
        return _REGEX[func.id](pattern, content) is not None

    def iterate(self, items: Any):
        for item in items:
            self.spend()
            yield item

    def generate(self, node: ast.GeneratorExp, names: dict[str, Any]):
        clause = node.generators[0]
        items = self.run(clause.iter, names)
        if type(items) not in (list, tuple, str, dict):
            raise TypeError("invalid generator input")
        for item in self.iterate(items):
            local = {**names, clause.target.id: item}
            if not clause.ifs or self.run(clause.ifs[0], local):
                yield self.run(node.elt, local)


def protect_comparison(source):
    """Only report values that can be attributed to safe scalar inputs or a count."""
    try:
        test = parse_check(source).test
    except (SyntaxError, ValueError):
        return False
    if not isinstance(test, ast.Compare):
        return False
    for node in [test.left, *test.comparators]:
        literal = isinstance(node, ast.Constant) and type(node.value) in (int, float, bool, type(None))
        count = (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len"
                 and len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == "events")
        expected = (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                    and node.value.id == "expected" and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str) and not sensitive_name(node.slice.value))
        if not (literal or count or expected):
            return False
    return True


def _operand_summary(value):
    if type(value) in (str, list, tuple, dict):
        return f"{type(value).__name__} (length {len(value)})"
    if type(value) in (int, float, bool) or value is None:
        return str(value)[:80]
    return type(value).__name__


def evaluate_request(rules, events, expected_inputs):
    """Evaluate all groups, with expected inputs in the same order as the groups."""
    try:
        inputs = freeze_expected(expected_inputs)
        if type(inputs) is not list or len(inputs) != len(rules) or any(type(item) is not dict for item in inputs):
            raise LogInputError("expected one input mapping per group")
    except LogInputError:
        return {"state": "ERROR", "code": "LOG_INPUT_ERROR", "groups": []}
    try:
        events = safe_copy(events)
        if type(events) is not list or any(type(item) is not dict for item in events):
            raise LogInputError("expected a list of event objects")
    except LogInputError:
        return {"state": "ERROR", "code": "RULE_ERROR", "groups": []}
    interpreter = _Interpreter()
    groups = []
    precedence = {"PASSED": 0, "FAILED": 1, "ERROR": 2}
    for index, (rule, expected) in enumerate(zip(rules, inputs)):
        selected = [event for event in events if all(event.get(k) == v for k, v in rule.get("select", {}).items())]
        checks = []
        state = "PASSED"
        for check_index, source in enumerate(rule["checks"]):
            report = {"check_index": check_index, "source": source}
            if state != "PASSED":
                report.update(state="NOT_RUN", code="PREVIOUS_CHECK_FAILED")
            else:
                try:
                    check = parse_check(source)
                    if any(isinstance(node, ast.Constant) and isinstance(node.value, str)
                           and sensitive_name(node.value) for node in ast.walk(check)):
                        report["source"] = "[REDACTED]"
                    interpreter.failed_operands = None
                    if not interpreter.run(check.test, {"events": selected, "expected": expected}):
                        state = "FAILED"
                        report["code"] = "ASSERTION_FAILURE"
                        if interpreter.failed_operands is not None and protect_comparison(source):
                            actual, expected_value = interpreter.failed_operands
                            report.update(actual_summary=_operand_summary(actual), expected_summary=_operand_summary(expected_value))
                except (ValueError, LookupError, TypeError, ArithmeticError, re.error) as exc:
                    state = "ERROR"
                    report.update(code="RULE_ERROR", exception_type=type(exc).__name__)
                report["state"] = state
            checks.append(report)
        evidence = [{key: selected[0][key] for key in ("event_id", "offset") if key in selected[0]}] if selected else []
        groups.append({"group_index": rule.get("group_index", index), "state": state,
                       "checks": checks, "matched_count": len(selected), "evidence": evidence})
    return {"state": max((group["state"] for group in groups), key=precedence.get, default="PASSED"),
            "groups": groups}
