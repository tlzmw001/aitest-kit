"""Project durable pytest and log facts into the existing report format."""
from collections import Counter
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from aitest_kit.report.collector import _module_summary
from aitest_kit.report.publication import report_lock, update_latest, write_report
from aitest_kit.report.sanitizer import sanitize_message

from .rules import protect_comparison


def save_base(store, directory, base):
    store.update("INSERT OR REPLACE INTO report_input VALUES(?,?)", (str(directory.resolve()), json.dumps(base)))


def load_base(store, directory):
    rows = store.read("SELECT payload FROM report_input WHERE path=?", (str(directory.resolve()),))
    return json.loads(rows[0]["payload"]) if rows else None


def failure(phase, classification, message):
    return {"phase": phase, "classification": classification, "failure_type": classification,
            "exception_type": "AssertionError" if classification == "ASSERTION_FAILURE" else "RuntimeError",
            "message": sanitize_message(message, max_chars=500)}


def project_request(row, case_outcome, tc_id):
    payload = json.loads(row["payload"]) if row["payload"] else {}
    definitions = json.loads(row["rules"])
    groups = {group["group_index"]: group for group in payload.get("groups", [])}
    scoped = row.get("semantics") == 2 or any("source_id" in rule for rule in definitions)
    rules = []
    for index, definition in enumerate(definitions):
        group_index = definition.get("group_index", index)
        group = groups.get(group_index, {})
        checks = group.get("checks")
        if not checks:
            if scoped:
                check_state = "pending" if row["state"] in {"PREPARED", "WAITING", "READY", "RUNNING", "PENDING"} else "not_run"
                checks = [{"state": check_state}] * len(definition.get("checks", []))
            else:
                checks = [{}]
        for check_index, check in enumerate(checks):
            state = check.get("state", row["state"]).lower()
            code = check.get("code") or (None if scoped and state in {"pending", "not_run"} else payload.get("code"))
            phase = "log_assertion"
            if code == "LOG_READINESS_TIMEOUT":
                phase = "log_evidence"
            elif state == "error":
                phase = "log_rule" if code and code.startswith(("RULE_", "LOG_BINDING", "LOG_INPUT")) else "log_evidence"
            item = {"path": f"case_flows.{tc_id}.log_assertions[{group_index}].checks[{check_index}]",
                    "phase": phase, "result": state, "reason": code, "evidence": group.get("evidence", []),
                    "matched_count": group.get("matched_count")}
            if "source" in check:
                item["expression"] = sanitize_message(check["source"], max_chars=500)
            for detail in ("actual_summary", "expected_summary", "exception_type"):
                if detail in check and (detail == "exception_type" or protect_comparison(check.get("source", ""))):
                    item[detail] = check[detail]
            rules.append(item)
    policy = "on_success" if any(rule.get("cleanup") == "on_success" for rule in definitions) else "retain"
    observation = json.loads(row.get("last_observation") or "null")
    status_fields = {}
    if scoped:
        status_fields = {"result": row["state"].lower(), "reason": payload.get("code"),
                         "last_observation": observation,
                         "last_poll_error": json.loads(row.get("last_poll_error") or "null")}
    return {**status_fields, "request_step": row["step"], "source_id": row["source"], "reqId": row["correlation"],
            "capture_state": payload.get("capture_state", (observation or {}).get("capture_state")),
            "availability": payload.get("availability", (observation or {}).get("availability")),
            "version": row["version"], "rules": rules,
            "cleanup": {"policy": policy, "state": row["cleanup_state"] or "retain", "job_id": row["job_id"],
                        "reason": row["reason"] or ("case_" + case_outcome if policy == "on_success" else None)}}


def project_cases(base, index, facts, final, cancelled):
    by_node = {case["nodeid"]: case for case in base.get("cases", [])}
    runs_by_node = {}
    for attempt in facts:
        if attempt["unit"] == index:
            runs_by_node.setdefault(attempt["nodeid"], []).append(attempt)
    for node, attempts in runs_by_node.items():
        attempt = attempts[-1]
        plain = re.sub(r"\[.*\]$", "", attempt.get("plan_key") or node)
        case = dict(by_node.get(node) or base.get("_node_metadata", {}).get(plain) or {})
        phases = attempt["phases"]
        if phases.get("teardown") == "failed" or phases.get("setup") == "failed":
            immediate = "error"
        elif phases.get("call") == "failed":
            immediate = "failed"
        elif "skipped" in phases.values():
            immediate = "pytest_skipped"
        elif set(phases) == {"setup", "call", "teardown"}:
            immediate = "passed"
        else:
            immediate = "pending"
        outcome = attempt["outcome"] or immediate
        if attempt["outcome"] is None and outcome not in {"failed", "error"}:
            outcome = "error" if final else "pending"
        if case.get("source") and not case.get("source_md"):
            case["source_md"] = case["source"]
        case.update(nodeid=node, outcome=outcome, tc_id=case.get("tc_id", "UNKNOWN"))
        request_rows = list(attempt["requests"])
        seen_steps = {(row["step"], row["source"]) for row in attempt["requests"]}
        for planned in base.get("_planned_steps", {}).get(plain, []):
            if (planned["step"], planned["source"]) in seen_steps:
                continue
            missing = final and immediate == "passed" and outcome == "error"
            state = "ERROR" if missing else "NOT_RUN" if outcome in {"error", "failed", "pytest_skipped"} or final else "PENDING"
            payload = json.dumps({"code": "LOG_INPUT_STEP_NOT_EXECUTED"}) if missing else None
            request_rows.append({
                **planned, "rules": json.dumps(planned["rules"]), "state": state, "payload": payload,
                "correlation": None, "version": None, "cleanup_state": None, "job_id": None, "reason": None,
            })
        planned_order = {(plan["step"], plan["source"]): i
                         for i, plan in enumerate(base.get("_planned_steps", {}).get(plain, []))}
        request_rows.sort(key=lambda row: planned_order.get((row["step"], row["source"]), len(planned_order)))
        requests = [project_request(row, outcome, case["tc_id"]) for row in request_rows]
        if requests:
            case["log_validation"] = {"unit_index": index, "attempt": attempt["number"],
                                      "immediate_outcome": immediate, "requests": requests}
        if len(attempts) > 1:
            case["attempt_history"] = [{
                "attempt": earlier["number"], "phases": earlier["phases"],
                "requests": [project_request(row, "superseded", case["tc_id"]) for row in earlier["requests"]],
            } for earlier in attempts[:-1]]
        if outcome in {"failed", "error"} and not case.get("failure"):
            rule = next((item for status in ("error", "failed") for req in requests for item in req["rules"]
                         if item["result"] == status), None)
            source_failure = next((req for status in ("error", "failed") for req in requests
                                   if req.get("result") == status and req.get("reason")), None)
            if immediate in {"error", "failed"}:
                case["failure"] = failure("teardown" if phases.get("teardown") == "failed" else
                                          "setup" if phases.get("setup") == "failed" else "call",
                                          "ASSERTION_FAILURE" if immediate == "failed" else "TEST_SCAFFOLD_ERROR",
                                          "pytest phase failed")
            elif source_failure and (rule is None or source_failure["result"] == "error"):
                reason = source_failure["reason"]
                phase = "log_rule" if reason.startswith(("RULE_", "LOG_BINDING", "LOG_INPUT")) else "log_evidence"
                classification = ("ASSERTION_FAILURE" if reason == "LOG_READINESS_TIMEOUT" else
                                  "TEST_SCAFFOLD_ERROR" if phase == "log_rule" else "ENVIRONMENT_ERROR")
                context = f"{source_failure['request_step']} · {source_failure['source_id']} · {reason}"
                case["failure"] = failure(phase, classification, context)
            elif rule:
                classification = ("ASSERTION_FAILURE" if rule["reason"] == "LOG_READINESS_TIMEOUT" else
                                  {"log_rule": "TEST_SCAFFOLD_ERROR", "log_evidence": "ENVIRONMENT_ERROR",
                                   "log_assertion": "ASSERTION_FAILURE"}[rule["phase"]])
                context = f"{rule['path']} · {rule.get('expression') or rule.get('reason') or outcome}"
                case["failure"] = failure(rule["phase"], classification, context)
            else:
                case["failure"] = failure("run", "ENVIRONMENT_ERROR", "Run cancelled" if cancelled else "Pytest attempt interrupted")
        by_node[node] = case
    return list(by_node.values())


def summarize(result, cases):
    counts = Counter(case["outcome"] for case in cases)
    result["cases"] = cases
    summary = result.setdefault("summary", {})
    for state in ("passed", "failed", "error", "pytest_skipped", "pending"):
        summary[state] = counts[state]
    summary["auto_collected"] = len(cases)
    result["modules"] = _module_summary(cases, result.get("codegen_skipped_cases", []),
                                        result.get("manual_cases", []))
    for case in cases:
        if case["outcome"] == "pending":
            bucket = result["modules"][case.get("module") or "UNKNOWN"][case.get("category") or "UNKNOWN"]
            bucket["pending"] = bucket.get("pending", 0) + 1


def junit(result):
    root = ET.Element("testsuites")
    suites = {}
    def add(suite, name, outcome, detail=None, duration=0):
        if suite not in suites:
            suites[suite] = (ET.SubElement(root, "testsuite", name=suite), Counter())
        element, counts = suites[suite]
        counts["tests"] += 1
        case = ET.SubElement(element, "testcase", name=_xml(name), classname=suite, time=str(duration))
        tag = {"failed": "failure", "error": "error", "pytest_skipped": "skipped"}.get(outcome)
        if tag:
            message = _xml(detail or outcome)
            ET.SubElement(case, tag, message=message).text = message
            counts[tag + ("s" if tag != "skipped" else "")] += 1

    for case in result["cases"]:
        add(_xml(case.get("module", "aitest")), case["nodeid"], case["outcome"],
            (case.get("failure") or {}).get("message"), case.get("duration_seconds", 0))
    for issue in result["log_validation"]["issues"]:
        add("aitest.infrastructure", issue["kind"], "error", issue.get("message") or issue.get("reason"))
    total = Counter()
    for element, counts in suites.values():
        total.update(counts)
        element.attrib.update({key: str(counts[key]) for key in ("tests", "failures", "errors", "skipped")})
    root.attrib.update({key: str(total[key]) for key in ("tests", "failures", "errors", "skipped")})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _xml(value):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", "", str(value))


def publish(store, settings, *, final=False, prior_code=None, cancelled=False):
    plan_rows = store.read("SELECT payload FROM report_plan")
    if not plan_rows:
        return prior_code
    plan = json.loads(plan_rows[0]["payload"])
    root, bucket = Path(plan["root"]), Path(plan["bucket"])
    if root.resolve() != bucket.resolve() / "runs" / store.path.parent.name:
        raise ValueError("saved log report directory does not match the run")
    if any(Path(path).resolve() != root.resolve() and root.resolve() not in Path(path).resolve().parents
           for _, path in plan["units"]):
        raise ValueError("saved unit report directory is outside its run")
    with store.snapshot() as db:
        read = lambda sql: [dict(row) for row in db.execute(sql)]
        bases = {row["path"]: json.loads(row["payload"]) for row in read("SELECT * FROM report_input")}
        run = read("SELECT id,state FROM run")[0]
        phases = read("SELECT * FROM phase")
        facts = read("""
            SELECT a.*, s.outcome, n.plan_key FROM attempt a LEFT JOIN settled_case s ON s.attempt=a.id
            LEFT JOIN report_node n ON n.unit=a.unit AND n.nodeid=a.nodeid
            ORDER BY a.number,a.id
        """)
        requests = read("""
            SELECT r.id,r.attempt,r.step,r.source,r.correlation,r.state,r.version,r.rules,r.semantics,r.last_observation,r.last_poll_error,x.payload,
                   c.state AS cleanup_state,c.job_id,c.reason, f.request AS conflict
            FROM request r LEFT JOIN result x ON x.request=r.id LEFT JOIN cleanup c ON c.request=r.id
                           LEFT JOIN association_conflict f ON f.request=r.id ORDER BY r.id
        """)
        gates = read("SELECT DISTINCT unit,reason FROM preflight WHERE state='error'")
    by_phase = {}
    for phase in phases:
        by_phase.setdefault(phase["attempt"], {})[phase["name"]] = phase["outcome"]
    by_request = {}
    for row in requests:
        by_request.setdefault(row["attempt"], []).append(row)
    for fact in facts:
        fact["phases"] = by_phase.get(fact["id"], {})
        fact["requests"] = by_request.get(fact["id"], [])
    owners = {fact["id"]: fact["unit"] for fact in facts}
    issues = [{"kind": "PRECONDITION_MISSING", "unit_index": gate["unit"], "message": gate["reason"]}
              for gate in gates]
    for row in requests:
        if row["conflict"] or row["cleanup_state"] in {"failed", "unknown"}:
            issues.append({"kind": "cleanup", "unit_index": owners.get(row["attempt"]), "source_id": row["source"],
                           "request_step": row["step"], "reason": "ASSOCIATION_CONFLICT" if row["conflict"] else row["reason"]})
    base = dict(bases.get(str(root), plan["base"]))
    base.setdefault("run_id", run["id"])
    units = []
    children = []
    cases = []
    for idx, path in plan["units"]:
        unit_path = Path(path)
        unit = bases.get(path)
        if unit is None and path != str(root) and (unit_path / "result.json").exists():
            old = json.loads((unit_path / "result.json").read_text(encoding="utf-8"))
            if "log_validation" not in old:
                save_base(store, unit_path, old)
                unit = old
        if unit is None:
            if final and not any(fact["unit"] == idx for fact in facts):
                issues.append({"kind": "unit_interrupted", "unit_index": idx, "reason": "NO_TERMINAL_FACTS"})
                continue
            unit = base.copy() if path == str(root) else {"run_id": run["id"], "summary": {}}
        unit = dict(unit)
        unit_cases = project_cases(unit, idx, facts, final, cancelled)
        unit.pop("_node_metadata", None)
        unit.pop("_planned_steps", None)
        unit_code = unit.pop("_unit_exit_code", 10 if unit.get("status") == "BLOCKED_RUN" else 0)
        if final and unit_code and not any(case["outcome"] in {"failed", "error"} for case in unit_cases) and not any(
            issue.get("unit_index") == idx for issue in issues
        ):
            issues.append({"kind": "run_exit", "unit_index": idx,
                           "reason": unit.get("blocked_reason") or f"EXIT_{unit_code}"})
        unit["summary"] = dict(unit.get("summary", {}))
        summarize(unit, unit_cases)
        units.append({"index": idx, "summary": unit["summary"],
                      "result_path": str(unit_path / "result.json")})
        cases.extend(unit_cases)
        children.append((idx, unit_path, unit, unit_code))
    if final and prior_code and not issues and not any(c["outcome"] in {"error", "failed"} for c in cases):
        issues.append({"kind": "run_exit", "reason": f"EXIT_{prior_code}"})
    code = ((2 if cancelled else prior_code or int(bool(issues) or any(
        case["outcome"] in {"failed", "error", "pending"} for case in cases))) if final else None)
    blocked = base.get("status") == "BLOCKED_RUN" or (final and bool(gates) and not cases)
    if blocked and gates:
        base["blocked_reason"] = "log_platform_preflight"
    status = ("CANCELLED" if cancelled else "BLOCKED_RUN" if blocked
              else "FAILED_RUN" if final and code else "COMPLETED" if final
              else "INTERRUPTED" if run["state"] == "INTERRUPTED" else "RUNNING")
    validation = {"schema_version": 1, "final": final, "exit_code": code,
                  "case_concurrency": settings.case_concurrency, "log_concurrency": settings.log_concurrency,
                  "issues": issues}
    base.pop("_node_metadata", None)
    base.pop("_planned_steps", None)
    base.pop("_unit_exit_code", None)
    published_units = []
    for idx, path, unit, unit_code in children:
        unit_issues = [issue for issue in issues if issue.get("unit_index") == idx]
        unit_blocked = any(gate["unit"] == idx for gate in gates) and not unit["cases"]
        if unit_blocked:
            unit["blocked_reason"] = "log_platform_preflight"
        unit_failed = bool(unit["summary"]["failed"] or unit["summary"]["error"] or unit_issues)
        unit_status = (status if not final or cancelled else
                       "BLOCKED_RUN" if unit_blocked or unit.get("status") == "BLOCKED_RUN" else
                       "FAILED_RUN" if unit_failed else "COMPLETED")
        unit.update(status=unit_status, log_validation={**validation, "issues": unit_issues,
                                                        "exit_code": (2 if cancelled else unit_code or int(unit_failed)) if final else None})
        published_units.append((path, unit))
    for summary, (_, unit) in zip(units, published_units):
        summary["status"] = unit["status"]
    if len(plan["units"]) > 1 or plan["units"][0][1] != str(root):
        for key in ("run_scope", "task"):
            if key in base:
                original = {unit.get("index"): unit for unit in base[key].get("units", [])}
                base[key]["units"] = [{**original.get(unit["index"], {}), **unit} for unit in units]
        base["manual_cases"] = [case for _, _, unit, _ in children for case in unit.get("manual_cases", [])]
        base["codegen_skipped_cases"] = [case for _, _, unit, _ in children for case in unit.get("codegen_skipped_cases", [])]
    summarize(base, cases)
    base.update(status=status, log_validation=validation)
    with report_lock(bucket):
        marker = root / "result.json"
        if not final and marker.exists():
            previous = json.loads(marker.read_text(encoding="utf-8"))
            previous.get("log_validation", {}).pop("revision", None)
            if previous == base:
                return
        with store.write() as db:
            revision, = db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM report_revision").fetchone()
            db.execute("INSERT INTO report_revision VALUES(?)", (revision,))
        validation["revision"] = revision
        for path, unit in published_units:
            if path != root:
                unit["log_validation"]["revision"] = revision
                write_report(path, unit, junit(unit) if final else None)
        write_report(root, base, junit(base) if final else None)
        if final:
            update_latest(root, bucket, base)
    return code
