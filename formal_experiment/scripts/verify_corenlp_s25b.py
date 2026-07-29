"""Run the pinned S2.5-B CoreNLP/Tregex/Tsurgeon synthetic live smoke.

The verifier is offline: it requires an already-downloaded external CoreNLP
4.5.10 installation and archive.  It hashes the external distribution, checks
ZIP path safety, runs CoreNLP over two synthetic sentences, compiles the Java 8
bridge, executes every locked Tregex/Tsurgeon expression in field order, and
compares exact token spans against a synthetic expected fixture.  It never
reads experiment Gold, trains/evaluates a model, or calls an LLM/API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_style.corenlp_runtime import (  # noqa: E402
    EXTRACTION_ORDER,
    CoreNLPContractError,
    validate_annotation,
)


CONFIG_PATH = ROOT / "configs" / "sun_corenlp_runtime.json"
REGISTRY_PATH = ROOT / "resources" / "corenlp" / "sun_phrase_patterns_v1.json"
INPUT_PATH = ROOT / "tests" / "fixtures" / "corenlp" / "s25b_smoke_input.txt"
EXPECTED_PATH = ROOT / "tests" / "fixtures" / "corenlp" / "s25b_live_expected.json"
BRIDGE_PATH = ROOT / "tools" / "corenlp" / "SunPhraseRuleBridge.java"
MANIFEST_PATH = ROOT / "resources" / "corenlp" / "s25b_runtime_verification_manifest.json"


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CoreNLPContractError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stdout + "\n" + completed.stderr)[-4000:]
        raise CoreNLPContractError(
            f"command failed ({completed.returncode}): {command[0]}\n{detail}"
        )
    return completed


def _verify_archive(archive: Path, distribution: dict[str, Any]) -> dict[str, Any]:
    if not archive.is_file():
        raise CoreNLPContractError(f"CoreNLP archive missing: {archive}")
    archive_hash = _sha256(archive)
    archive_size = archive.stat().st_size
    if archive_hash != distribution.get("archive_sha256"):
        raise CoreNLPContractError("CoreNLP archive SHA-256 mismatch")
    if archive_size != distribution.get("archive_bytes"):
        raise CoreNLPContractError("CoreNLP archive byte size mismatch")
    unsafe: list[str] = []
    with zipfile.ZipFile(archive) as package:
        names = [info.filename.replace("\\", "/") for info in package.infolist()]
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or ":" in name or "\x00" in name:
                unsafe.append(name)
        top = sorted({name.split("/", 1)[0] for name in names if name})
    if unsafe:
        raise CoreNLPContractError(f"unsafe ZIP entries: {unsafe[:5]}")
    if len(names) != distribution.get("archive_entry_count") or top != [
        "stanford-corenlp-4.5.10"
    ]:
        raise CoreNLPContractError("CoreNLP ZIP inventory identity mismatch")
    return {
        "archive_bytes": archive_size,
        "archive_entry_count": len(names),
        "archive_sha256": archive_hash,
        "unsafe_archive_entry_count": 0,
    }


def _resolve_java(runtime_home: Path) -> tuple[str, str, list[Path]]:
    java = shutil.which("java")
    javac = shutil.which("javac")
    if not java or not javac:
        raise CoreNLPContractError("java and javac must both be available")
    jars = sorted(runtime_home.rglob("*.jar"))
    if not jars:
        raise CoreNLPContractError("external CoreNLP classpath is empty")
    return java, javac, jars


def _verify_jars(
    runtime_home: Path,
    identity: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key in ("code_jar", "models_jar"):
        expected = identity[key]
        path = runtime_home / expected["name"]
        if not path.is_file():
            raise CoreNLPContractError(f"required runtime JAR missing: {path}")
        actual = {"bytes": path.stat().st_size, "sha256": _sha256(path)}
        if actual != {"bytes": expected["bytes"], "sha256": expected["sha256"]}:
            raise CoreNLPContractError(f"runtime JAR identity mismatch: {expected['name']}")
        result[key] = {"name": expected["name"], **actual}
    return result


def _write_rule_plan(registry: dict[str, Any], target: Path) -> int:
    if tuple(registry.get("extraction_order", ())) != EXTRACTION_ORDER:
        raise CoreNLPContractError("rule registry extraction order changed")
    fields = registry.get("fields")
    if not isinstance(fields, list) or tuple(item.get("field") for item in fields) != (
        EXTRACTION_ORDER
    ):
        raise CoreNLPContractError("rule registry fields are not in extraction order")
    lines: list[str] = []
    for item in fields:
        operations = item.get("tsurgeon_operations")
        if not isinstance(operations, list) or len(operations) > 1:
            raise CoreNLPContractError("each field must have zero or one live operation")
        operation = operations[0] if operations else ""
        patterns = item.get("tregex_patterns")
        if not isinstance(patterns, list) or not patterns:
            raise CoreNLPContractError("each field must have at least one Tregex pattern")
        for pattern in patterns:
            if not isinstance(pattern, str) or "\t" in pattern or "\n" in pattern:
                raise CoreNLPContractError("Tregex pattern is not plan-safe")
            lines.append(f"{item['field']}\t{pattern}\t{operation}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def _parse_bridge_output(output: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    cases: dict[int, dict[str, Any]] = {}
    summary: dict[str, int] | None = None
    for raw in output.splitlines():
        parts = raw.split("\t")
        if parts[0] == "MATCH" and len(parts) == 8:
            index = int(parts[1])
            fields = cases.setdefault(
                index, {field: None for field in EXTRACTION_ORDER}
            )
            fields[parts[2]] = {
                "begin": int(parts[3]),
                "end": int(parts[4]),
                "text": parts[5],
                "pattern_index": int(parts[6]),
                "operation_applied": parts[7] == "true",
            }
        elif parts[0] == "MISS" and len(parts) == 3:
            index = int(parts[1])
            cases.setdefault(index, {field: None for field in EXTRACTION_ORDER})
        elif parts[0] == "SUMMARY" and len(parts) == 5:
            summary = {
                "tree_count": int(parts[1]),
                "pattern_count": int(parts[2]),
                "match_count": int(parts[3]),
                "surgery_count": int(parts[4]),
            }
    if summary is None:
        raise CoreNLPContractError("Java bridge did not emit SUMMARY")
    ordered = [
        {"sentence_index": index, "fields": cases[index]}
        for index in sorted(cases)
    ]
    return ordered, summary


def run_live(runtime_home: Path, archive: Path) -> dict[str, Any]:
    config = _load_object(CONFIG_PATH)
    registry = _load_object(REGISTRY_PATH)
    expected = _load_object(EXPECTED_PATH)
    distribution = config["official_distribution"]
    identity = config["external_runtime_identity"]
    archive_report = _verify_archive(archive, distribution)
    jar_report = _verify_jars(runtime_home, identity)
    java, javac, jars = _resolve_java(runtime_home)
    classpath = os.pathsep.join(str(path) for path in jars)
    ROOT.joinpath(".tmp").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="s25b-live-", dir=ROOT / ".tmp") as raw_tmp:
        temporary = Path(raw_tmp)
        output_dir = temporary / "corenlp-output"
        output_dir.mkdir()
        corenlp_command = [
            java,
            "-Xmx4g",
            "-cp",
            classpath,
            "edu.stanford.nlp.pipeline.StanfordCoreNLP",
            "-annotators",
            "tokenize,ssplit,pos,lemma,parse,depparse",
            "-outputFormat",
            "json",
            "-file",
            str(INPUT_PATH),
            "-outputDirectory",
            str(output_dir),
            "-replaceExtension",
        ]
        _run(corenlp_command, cwd=ROOT, timeout=180)
        annotation_path = output_dir / "s25b_smoke_input.json"
        annotation = _load_object(annotation_path)
        annotation_summary = validate_annotation(
            annotation, INPUT_PATH.read_text(encoding="utf-8")
        )
        tree_path = temporary / "live-trees.txt"
        tree_path.write_text(
            "\n".join(
                " ".join(sentence["parse"].split())
                for sentence in annotation["sentences"]
            )
            + "\n",
            encoding="utf-8",
        )
        plan_path = temporary / "rule-plan.tsv"
        pattern_count = _write_rule_plan(registry, plan_path)
        classes = temporary / "classes"
        classes.mkdir()
        compile_command = [
            javac,
            "--release",
            "8",
            "-encoding",
            "UTF-8",
            "-cp",
            classpath,
            "-d",
            str(classes),
            str(BRIDGE_PATH),
        ]
        _run(compile_command, cwd=ROOT, timeout=120)
        bridge_classpath = os.pathsep.join((str(classes), classpath))
        bridge_command = [
            java,
            "-cp",
            bridge_classpath,
            "SunPhraseRuleBridge",
            str(plan_path),
            str(tree_path),
        ]
        bridge = _run(bridge_command, cwd=ROOT, timeout=120)
        cases, summary = _parse_bridge_output(bridge.stdout)
        if pattern_count != summary["pattern_count"]:
            raise CoreNLPContractError("bridge pattern count mismatch")
        observed = {
            "schema_version": "s25b_live_expected@1.0.0",
            "extraction_order": list(EXTRACTION_ORDER),
            "cases": cases,
            "summary": summary,
        }
        if observed != expected:
            raise CoreNLPContractError(
                "live Tregex/Tsurgeon observations disagree with locked synthetic fixture\n"
                + json.dumps(observed, ensure_ascii=False, indent=2)
            )
        java_version_result = _run([java, "-version"], cwd=ROOT, timeout=30)
        java_version_lines = (
            java_version_result.stderr or java_version_result.stdout
        ).splitlines()
        return {
            "schema_version": "s25b_locked_evidence@1.0.0",
            "task_id": "S2.5-B",
            "runtime": {
                "corenlp_version": "4.5.10",
                "archive": archive_report,
                "jars": jar_report,
                "java_version_first_line": java_version_lines[0],
            },
            "artifacts": {
                "rule_registry_sha256": _sha256(REGISTRY_PATH),
                "smoke_input_sha256": _sha256(INPUT_PATH),
                "live_expected_sha256": _sha256(EXPECTED_PATH),
                "java_bridge_sha256": _sha256(BRIDGE_PATH),
            },
            "live_smoke": {
                "annotation_summary": annotation_summary,
                "corenlp_output_sha256": _sha256(annotation_path),
                "bridge_stdout_sha256": hashlib.sha256(
                    bridge.stdout.encode("utf-8")
                ).hexdigest(),
                "observed": observed,
                "commands": {
                    "corenlp": "java -Xmx4g -cp ${CORENLP_HOME}/* edu.stanford.nlp.pipeline.StanfordCoreNLP -annotators tokenize,ssplit,pos,lemma,parse,depparse -outputFormat json -file tests/fixtures/corenlp/s25b_smoke_input.txt -outputDirectory ${TEMP} -replaceExtension",
                    "compile_bridge": "javac --release 8 -encoding UTF-8 -cp ${CORENLP_HOME}/* -d ${TEMP}/classes tools/corenlp/SunPhraseRuleBridge.java",
                    "run_bridge": "java -cp ${TEMP}/classes${PATHSEP}${CORENLP_HOME}/* SunPhraseRuleBridge ${TEMP}/rule-plan.tsv ${TEMP}/live-trees.txt",
                },
            },
            "boundaries": {
                "synthetic_fixture_only": True,
                "training_run": False,
                "evaluation_run": False,
                "formal_gold_read_or_modified": False,
                "llm_api_called": False,
                "network_called_by_verifier": False,
                "third_party_binary_vendored": False,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--check-manifest", action="store_true")
    args = parser.parse_args()
    evidence = run_live(args.runtime_home.resolve(), args.archive.resolve())
    if args.check_manifest:
        manifest = _load_object(MANIFEST_PATH)
        if manifest.get("locked_evidence") != evidence:
            raise CoreNLPContractError("stored S2.5-B manifest disagrees with live evidence")
        print("S2.5-B live manifest matches the current external runtime and fixtures.")
    else:
        print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
