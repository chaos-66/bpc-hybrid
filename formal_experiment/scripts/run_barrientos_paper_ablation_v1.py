"""S2-BARR-4: reproduce the supplied FULL / NO-PATTERNS prompt comparison.

Prepare and inspect offline; real calls require a separate, contract-bound user
authorization. The historical 1140-call executor and its results stay frozen.
Native RC4PC output is evaluated before any repair or six-field conversion.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import math
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
from bpc_hybrid.de_contract_schema import validate_instance

SOURCE = REPO / "references/barrientos_2026"
PROMPTS = {
    "FULL": SOURCE / "artifact_input/prompts/formalize_requirements_prompt.txt",
    "NO-PATTERNS": SOURCE / "artifact_input/prompts/formalize_requirements_prompt_no_patterns.txt",
}
INPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
SCHEMA = SOURCE / "artifact_input/formats/compliance_requirements_format.json"
NOTEBOOK = SOURCE / "notebooks/AnalyzeImpactRequirementChangesBusinessProcessCompliance.ipynb"
PAPER = REPO / "references/papers/Barrientos_2026_Impact_analysis.pdf"
CONTRACT = ROOT / "configs/ablations/barrientos_paper_ablation_v1.json"
PREFLIGHT = ROOT / "outputs/reports/barrientos_paper_ablation_preflight_v1.json"
REPORT = ROOT / "outputs/reports/barrientos_paper_ablation_results_v1.json"
LOCAL = ROOT / "outputs/development/barrientos_paper_ablation_v1"
MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
REPEATS = 5
CALLS = 360
MAX_OUTPUT = 4096


class Refused(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def samples():
    doc = read(INPUT)
    if doc.get("gold_blind") is not True or len(doc["records"]) != 36:
        raise Refused("expected frozen Gold-blind 36-record input")
    result = []
    for row in doc["records"]:
        loc = row["source"]
        path = (REPO / loc["path"]).resolve()
        if not path.is_relative_to((SOURCE / "artifact_input/requirements").resolve()):
            raise Refused("source locator outside authorized requirement directory")
        if sha(path) != loc["file_sha256"]:
            raise Refused("frozen requirement file changed")
        found = [r for r in read(path)
                 if str(r.get("ID", "")).strip().rstrip("’'´`") == loc["record_id"]
                 and str(r.get("version")) == str(loc["version"])]
        if len(found) != 1:
            raise Refused("source locator did not identify one version")
        text = found[0]["text"]
        if not text.strip() or text.strip() == "-" or digest(text.encode()) != loc["text_sha256"]:
            raise Refused("input text hash/eligibility mismatch")
        result.append({"sample_id": row["sample_id"], "ID": loc["record_id"],
                       "version": str(loc["version"]), "text": text})
    if len({r["sample_id"] for r in result}) != 36:
        raise Refused("duplicate input ids")
    return result


def vocabulary():
    text = PROMPTS["FULL"].read_text(encoding="utf-8")
    section = text.split("1. **Allowed Compliance Patterns**", 1)[1].split(
        "2. **Control-Flow Exclusivity Rule**", 1)[0]
    result, dimension = {}, None
    for line in section.splitlines():
        match = re.fullmatch(r"- (control_flow|resource|data|time):", line)
        if match:
            dimension = match[1]
            result[dimension] = []
        elif line.startswith("  - ") and dimension:
            result[dimension].append(line[4:].strip())
    if {k: len(v) for k, v in result.items()} != {
            "control_flow": 13, "resource": 9, "data": 14, "time": 8}:
        raise Refused("source 44-pattern vocabulary changed")
    return result


def source_audit():
    full = PROMPTS["FULL"].read_text(encoding="utf-8")
    removed = PROMPTS["NO-PATTERNS"].read_text(encoding="utf-8")
    a = full.index("1. **Allowed Compliance Patterns**")
    b = full.index("3. **Label and Structure Consistency Across Versions**")
    expected = full[:a] + full[b:]
    for old, new in ((3, 1), (4, 2), (5, 3)):
        expected = re.sub(rf"(?m)^{old}\. \*\*", f"{new}. **", expected)
    if expected != removed:
        raise Refused("artifact prompt difference changed; re-review required")
    cells = read(NOTEBOOK)["cells"]
    pdf = "".join(cells[6]["source"])
    xml = "".join(cells[7]["source"])
    if "client.files.create" not in pdf or "bpmn_xml" not in xml:
        raise Refused("source notebook PDF/XML cells changed")
    return {
        "paper_pages": {"step1_and_step3_ablation": 9, "evaluation_population": 10,
                        "main_results_not_ablation_table": 11},
        "paper_model": "gpt-4.1", "paper_temperature": 0,
        "artifact_removed_sections": ["Allowed Compliance Patterns",
                                      "Control-Flow Exclusivity Rule"],
        "other_difference": "remaining rule headings renumbered 3/4/5 -> 1/2/3",
        "retained_no_pattern_instruction": "do NOT invent new patterns; refers to an absent list",
        "is_pure_whitelist_one_factor": False,
        "schema_pattern_is_enum": False,
        "schema_note": "compliance_pattern is a string: schema validity does not imply vocabulary validity",
        "step3": {
            "artifact_cells_zero_based": [6, 7],
            "comparison": "uploaded PDF vs raw BPMN XML in user text",
            "prompt_confound": "MIGHT violate becomes violates; deviation instructions and output descriptions also change",
            "runnable_here": False,
            "remaining_requirements": [
                "freeze identical natural-language versions/formalizations/deltas for both arms",
                "authorize a PDF-capable model and file uploads (paper uses GPT-4.1)",
                "approve a separate Stage 3 reproduction contract; current Stage 3 gates unchanged"],
        },
        "five_repeats": "adopted from paper main evaluation; separate ablation sample/repeat counts not stated in the paper paragraphs",
        "claim_scope": "development source-artifact reproduction with model substitution; not our six-field method ablation",
    }


def request_body(arm, sample):
    return {"model": MODEL, "messages": [
        {"role": "system", "content": PROMPTS[arm].read_text(encoding="utf-8").strip()},
        {"role": "user", "content": json.dumps({k: sample[k] for k in ("ID", "version", "text")},
                                                  ensure_ascii=False)}],
        "temperature": 0, "top_p": 1, "max_tokens": MAX_OUTPUT,
        "stream": False, "thinking": {"type": "disabled"}}


def plan():
    rows = samples()
    result = []
    for repeat in range(1, REPEATS + 1):
        for i, row in enumerate(rows):
            order = tuple(PROMPTS) if (repeat + i) % 2 else tuple(reversed(PROMPTS))
            for arm in order:
                body = request_body(arm, row)
                result.append({"key": f"{repeat}/{arm}/{row['sample_id']}",
                               "repeat": repeat, "arm": arm, "sample_id": row["sample_id"],
                               "body_sha256": digest(canonical(body).encode()),
                               "input_byte_bound": len(canonical(body).encode())})
    return result


def bindings():
    paths = [Path(__file__), INPUT, SCHEMA, NOTEBOOK, PAPER, *PROMPTS.values(),
             ROOT / "src/bpc_hybrid/de_contract_schema.py"]
    paths.extend(REPO / r["source"]["path"] for r in read(INPUT)["records"])
    return {p.relative_to(REPO).as_posix(): sha(p) for p in sorted(set(paths))}


def build_contract():
    runs = plan()
    input_cap = sum(r["input_byte_bound"] + 1024 for r in runs)
    output_cap = CALLS * MAX_OUTPUT
    usd = math.ceil((input_cap * 1.32 + output_cap * 3.96) / 1e6 * 1.2 * 100) / 100
    return {
        "schema_version": "barrientos_paper_ablation@1.0.0", "task_id": "S2-BARR-4",
        "status": "prepared_not_authorized_not_run", "source_audit": source_audit(),
        "endpoint": ENDPOINT, "model": MODEL, "model_release_reference": "DeepSeek-V4-Pro-0813",
        "historical_baseline_reused": False, "calls": CALLS, "repeats": REPEATS,
        "plan": runs, "bindings": bindings(), "vocabulary": vocabulary(),
        "budget": {"input_token_cap": input_cap, "output_token_cap": output_cap,
                   "usd_cost_cap": usd, "retry": 0,
                   "input_cache_miss_usd_per_million": 1.32, "output_usd_per_million": 3.96,
                   "price_source": "https://api-docs.deepseek.com/quick_start/pricing/",
                   "verified_date": "2026-09-05", "mode": "conservative peak, cache miss",
                   "calculation": "input reserves UTF-8 request bytes + 1024 per call; max output 4096; 20% USD margin"},
        "authorization": None,
        "primary_metrics": ["out_of_vocabulary_action_rate", "wrong_dimension_action_rate",
                            "records_with_vocabulary_errors/all_requests", "raw_schema_valid_rate",
                            "usable_nonempty_rate", "same_arguments_pattern_disagreement_proxy"],
        "semantic_accuracy": "not scored automatically; no six-field F1 substitution; cases remain human-review candidates",
        "stability": "nonempty schema-valid canonical-JSON exact agreement, 36*C(5,2) pairs/arm; auxiliary, not paper distance<=2",
    }


def authorization_sentence(contract):
    return (f"我授权 S2-BARR-4 Barrientos 原始 FULL/NO-PATTERNS 消融："
            f"36条×2条件×5次，{CALLS}次 deepseek-v4-pro API 调用，"
            f"费用上限 USD {contract['budget']['usd_cost_cap']:.2f}，retry=0，允许发送该36条输入。")


def validate_contract(path=CONTRACT):
    value = read(path)
    if value != build_contract():
        raise Refused("contract/input/prompt/code changed; prepare a new reviewed contract")
    return value


def verify_authorization(contract, path, contract_path=CONTRACT):
    if path is None:
        raise Refused("missing contract-bound explicit API authorization")
    auth = read(path)
    if auth != {"contract_sha256": sha(contract_path),
                "user_authorization": authorization_sentence(contract)}:
        raise Refused("API authorization does not match the reviewed contract and budget")


def expand_refs(node, root):
    if isinstance(node, dict):
        if "$ref" in node:
            if not node["$ref"].startswith("#/definitions/"):
                raise Refused("unsupported schema reference")
            return expand_refs(root["definitions"][node["$ref"].split("/")[-1]], root)
        return {k: expand_refs(v, root) for k, v in node.items() if k != "definitions"}
    if isinstance(node, list):
        return [expand_refs(v, root) for v in node]
    return node


def parse_raw(text):
    # The artifact falls back to Python literals. We report strict JSON and
    # artifact parseability separately so non-JSON never becomes strict-JSON success.
    clean = text.strip().strip("`").strip()
    if clean.lower().startswith("json"):
        clean = clean[4:].strip()
    try:
        value = json.loads(clean, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        canonical(value)  # Also rejects overflowing JSON numbers such as 1e999.
        return value, True
    except (ValueError, TypeError):
        try:
            value = ast.literal_eval(clean)
            canonical(value)  # Sets/bytes/complex values cannot enter JSON reports.
            return value, False
        except (ValueError, SyntaxError, TypeError):
            return None, False


def inspect_response(text, vocab, schema):
    tree, strict = parse_raw(text)
    valid = isinstance(tree, dict) and not validate_instance(tree, schema)
    actions = []
    if isinstance(tree, dict):
        pre = tree.get("precondition")
        if isinstance(pre, dict):
            for key in ("and", "or", "not"):
                if isinstance(pre.get(key), list):
                    actions.extend(a for a in pre[key] if isinstance(a, dict))
        if isinstance(tree.get("norms"), list):
            actions.extend(n["action"] for n in tree["norms"] if isinstance(n, dict)
                           and isinstance(n.get("action"), dict))
    all_patterns = set(itertools.chain.from_iterable(vocab.values()))
    unknown = wrong_dim = 0
    groups = {}
    for action in actions:
        pattern, dimension = action.get("compliance_pattern"), action.get("dimension")
        if not isinstance(pattern, str) or pattern not in all_patterns:
            unknown += 1
        elif not isinstance(dimension, str) or pattern not in vocab.get(dimension, []):
            wrong_dim += 1
        args = {k: v for k, v in action.items() if k != "compliance_pattern"}
        try:
            groups.setdefault(canonical(args), set()).add(canonical(pattern))
        except (TypeError, ValueError):
            valid = False
    return {"strict_json": strict, "artifact_parseable": isinstance(tree, dict),
            "schema_valid": valid, "nonempty": bool(actions), "action_count": len(actions),
            "out_of_vocabulary": unknown, "wrong_dimension": wrong_dim,
            "same_arguments_pattern_disagreement_proxy": sum(len(v) > 1 for v in groups.values()),
            "tree": tree}


def summarize(completions, contract):
    schema_doc = read(SCHEMA)
    schema = expand_refs(schema_doc, schema_doc)
    by_arm = {a: [] for a in PROMPTS}
    cases = []
    for row in completions:
        item = inspect_response(row["content"], contract["vocabulary"], schema)
        by_arm[row["arm"]].append((row, item))
        cases.append({"key": row["key"], "diagnostic": item})
    output = {}
    for arm, values in by_arm.items():
        n = len(values)
        actions = sum(i["action_count"] for _, i in values)
        unknown = sum(i["out_of_vocabulary"] for _, i in values)
        wrong = sum(i["wrong_dimension"] for _, i in values)
        rate = lambda count: count / n if n else None
        pairs = equal = 0
        for sid in {r["sample_id"] for r, _ in values}:
            items = [i for r, i in values if r["sample_id"] == sid]
            for a, b in itertools.combinations(items, 2):
                pairs += 1
                if all(i["schema_valid"] and i["nonempty"] for i in (a, b)):
                    equal += canonical(a["tree"]) == canonical(b["tree"])
        output[arm] = {
            "requests": n, "action_count": actions, "out_of_vocabulary_actions": unknown,
            "out_of_vocabulary_action_rate": unknown / actions if actions else None,
            "wrong_dimension_actions": wrong, "wrong_dimension_action_rate": wrong / actions if actions else None,
            "records_with_vocabulary_errors_rate": rate(sum(bool(i["out_of_vocabulary"] or i["wrong_dimension"]) for _, i in values)),
            "raw_strict_json_rate": rate(sum(i["strict_json"] for _, i in values)),
            "raw_schema_valid_rate": rate(sum(i["strict_json"] and i["schema_valid"] for _, i in values)),
            "usable_nonempty_rate": rate(sum(i["schema_valid"] and i["nonempty"] and not i["out_of_vocabulary"] and not i["wrong_dimension"] for _, i in values)),
            "same_arguments_pattern_disagreement_proxy": sum(i["same_arguments_pattern_disagreement_proxy"] for _, i in values),
            "stability_pair_count": pairs, "valid_nonempty_exact_agreement": equal / pairs if pairs else None,
        }
    return {"claim_scope": "development_only", "conditions": output,
            "raw_or_semantic_cases_published": False,
            "note": "out-of-list does not establish semantic incorrectness; no automated semantic F1; all request failures remain in record denominators"}, cases


def append_event(path, event, previous):
    row = {"previous_sha256": previous, **event}
    row["sha256"] = digest(canonical(row).encode())
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(canonical(row) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return row["sha256"]


def restore(path, contract):
    previous, pending, done = "0" * 64, None, []
    if not path.exists():
        return previous, done
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        checksum = row.pop("sha256")
        if row.get("previous_sha256") != previous or digest(canonical(row).encode()) != checksum:
            raise Refused("call ledger integrity failure")
        previous = checksum
        expected = contract["plan"][len(done)] if len(done) < CALLS else None
        if expected is None or row.get("key") != expected["key"]:
            raise Refused("call ledger is not an exact plan prefix")
        if row["state"] == "started" and pending is None:
            if row.get("body_sha256") != expected["body_sha256"]:
                raise Refused("ledger payload mismatch")
            pending = row
        elif row["state"] == "completed" and pending is not None:
            if row.get("response_sha256") != digest(row.get("content", "").encode()):
                raise Refused("raw response hash mismatch")
            if (type(row.get("input_tokens")) is not int or type(row.get("output_tokens")) is not int
                    or not 0 <= row["input_tokens"] <= expected["input_byte_bound"] + 1024
                    or not 0 <= row["output_tokens"] <= MAX_OUTPUT
                    or row.get("returned_model") not in (MODEL, "DeepSeek-V4-Pro-0813", "deepseek-v4-pro-0813")):
                raise Refused("recorded usage/model violation; automatic resume refused")
            done.append({**expected, **row})
            pending = None
        else:
            raise Refused("invalid call ledger state sequence")
    if pending is not None:
        raise Refused("in-doubt request; never automatically retry or resume past it")
    return previous, done


def usage_totals(rows):
    return (sum(r["input_tokens"] for r in rows), sum(r["output_tokens"] for r in rows))


def send_request(body):
    # Credentials are read only from process environment after authorization.
    key = next((os.environ[k] for k in ("DEEPSEEK_API_KEY", "BPC_HYBRID_DeepSeek_API_KEY",
                                      "BPC_HYBRID_LLM_API_KEY") if os.environ.get(k)), None)
    if not key:
        raise Refused("no DeepSeek credential in process environment; .env is never read")
    request = urllib.request.Request(ENDPOINT, data=canonical(body).encode(),
                                    headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    # A redirect must not forward the Authorization header to another host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    with urllib.request.build_opener(NoRedirect).open(request, timeout=180) as response:
        return json.loads(response.read())


def execute(contract_path, auth_path, *, sender=None, local=LOCAL):
    contract = validate_contract(contract_path)
    verify_authorization(contract, auth_path, contract_path)
    if REPORT.exists():
        raise Refused("final result already exists; overwrite forbidden")
    local.mkdir(parents=True, exist_ok=True)
    ledger = local / "calls.jsonl"
    bound = local / "contract.sha256"
    if bound.exists():
        if bound.read_text().strip() != sha(contract_path):
            raise Refused("local output bound to another contract")
    else:
        with bound.open("x", encoding="ascii") as f:
            f.write(sha(contract_path))
    previous, done = restore(ledger, contract)
    inputs = {r["sample_id"]: r for r in samples()}
    budget = contract["budget"]
    for step in contract["plan"][len(done):]:
        body = request_body(step["arm"], inputs[step["sample_id"]])
        if digest(canonical(body).encode()) != step["body_sha256"] or bindings() != contract["bindings"]:
            raise Refused("source/payload changed before send")
        ti, to = usage_totals(done)
        pi, po = step["input_byte_bound"] + 1024, MAX_OUTPUT
        if ti + pi > budget["input_token_cap"] or to + po > budget["output_token_cap"] or (
                (ti + pi) * 1.32 + (to + po) * 3.96) / 1e6 > budget["usd_cost_cap"]:
            raise Refused("budget would be exceeded")
        previous = append_event(ledger, {"state": "started", **step}, previous)
        try:
            response = (sender or send_request)(body)
            content = response["choices"][0]["message"].get("content") or ""
            usage = response.get("usage") or {}
            a, b = usage.get("prompt_tokens"), usage.get("completion_tokens")
            if not all(type(x) is int and x >= 0 for x in (a, b)):
                raise Refused("missing usage; request remains in doubt")
            record = {"state": "completed", "key": step["key"], "content": content,
                      "response_sha256": digest(content.encode()), "input_tokens": a,
                      "output_tokens": b, "returned_model": response.get("model"),
                      "request_id": response.get("id"), "finish_reason": response["choices"][0].get("finish_reason")}
            previous = append_event(ledger, record, previous)
            done.append({**step, **record})
            if a > pi or b > po or response.get("model") not in (MODEL, "DeepSeek-V4-Pro-0813", "deepseek-v4-pro-0813"):
                raise Refused("usage or returned model outside contract; stopped after recording response")
        except Exception as exc:
            raise Refused(f"stopped at {step['key']}: {type(exc).__name__}; inspect local ledger, no retry") from None
        if len(done) % 36 == 0:
            print(f"Completed {len(done)}/{CALLS}", flush=True)
    summary, cases = summarize(done, contract)
    write_new(local / "review_cases.json", cases)
    ti, to = usage_totals(done)
    summary.update({"complete": len(done) == CALLS, "actual_calls": len(done),
                    "contract_sha256": sha(contract_path), "ledger_sha256": sha(ledger),
                    "input_tokens": ti, "output_tokens": to,
                    "cost_usd_peak_upper_bound": (ti * 1.32 + to * 3.96) / 1e6})
    write_new(REPORT, summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract-file", type=Path, default=CONTRACT)
    parser.add_argument("--authorization-file", type=Path)
    args = parser.parse_args()
    if args.prepare:
        value = build_contract()
        if args.contract_file.exists() or PREFLIGHT.exists():
            raise Refused("preparation artifacts exist; overwrite forbidden")
        write_new(args.contract_file, value)
        report = {"status": "offline_prepared_API_not_authorized", "api_calls": 0,
                  "contract_sha256": sha(args.contract_file), "source_audit": value["source_audit"],
                  "budget": value["budget"], "calls": CALLS,
                  "authorization_template": {"contract_sha256": sha(args.contract_file),
                                             "user_authorization": authorization_sentence(value)}}
        write_new(PREFLIGHT, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.dry_run:
        value = validate_contract(args.contract_file)
        print(f"Prepared {len(value['plan'])} requests; API calls=0; authorization=null")
    else:
        execute(args.contract_file, args.authorization_file)


if __name__ == "__main__":
    try:
        main()
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
