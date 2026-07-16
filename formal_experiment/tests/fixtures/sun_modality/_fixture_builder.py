"""Build S2.1-B-R1 synthetic-only Sun modality fixtures.

Every fixture except ``synthetic_no_source_id.csv`` contains a real
``source_id`` column. The strict-one-hot columns belong only to this test
adapter and say nothing about the pending official CSV integer-code mapping.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence

FIXTURE_DIR = Path(__file__).resolve().parent

ID_COLUMN = "source_id"
TEXT_COLUMN = "text"
LABEL_COLUMNS = [
    "label_definition",
    "label_obligation",
    "label_permission",
    "label_prohibition",
]
LABEL_CLASSES = ["definition", "obligation", "permission", "prohibition"]


def _write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _label_row(label: str) -> list[str]:
    return ["1" if canonical == label else "0" for canonical in LABEL_CLASSES]


def _with_ids(rows: Sequence[tuple[str, str]], prefix: str) -> list[list[str]]:
    return [
        [f"{prefix}-{index:03d}", text] + _label_row(label)
        for index, (text, label) in enumerate(rows, start=1)
    ]


def _write_labelled(name: str, rows: Sequence[tuple[str, str]], prefix: str) -> Path:
    path = FIXTURE_DIR / name
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS, _with_ids(rows, prefix))
    return path


def normal_rows() -> list[tuple[str, str]]:
    return [
        ("Erste Definition eines Steuerbegriffs.", "definition"),
        ("Zweite Definition mit Beispiel.", "definition"),
        ("Der Steuerpflichtige muss die Erklärung abgeben.", "obligation"),
        ("Die Behörde hat den Bescheid zuzustellen.", "obligation"),
        ("Der Bürger darf den Antrag stellen.", "permission"),
        ("Die Behörde kann die Frist verlängern.", "permission"),
        ("Der Steuerpflichtige darf die Daten nicht weitergeben.", "prohibition"),
        ("Niemand darf die Frist überschreiten.", "prohibition"),
        ("Definition des Begriffs Wohnsitz.", "definition"),
        ("Die Pflicht zur Meldung besteht.", "obligation"),
    ]


def build_normal() -> Path:
    return _write_labelled("synthetic_normal.csv", normal_rows(), "normal")


def build_large_normal() -> Path:
    rows: list[tuple[str, str]] = []
    stems = {
        "definition": "Definition Satz",
        "obligation": "Pflicht Satz",
        "permission": "Erlaubnis Satz",
        "prohibition": "Verbot Satz",
    }
    for label in LABEL_CLASSES:
        rows.extend((f"{stems[label]} {index}", label) for index in range(10))
    return _write_labelled("synthetic_large_normal.csv", rows, "large")


def build_empty_text() -> Path:
    rows = [
        ["empty-001", "Definition eins"] + _label_row("definition"),
        ["empty-002", "   "] + _label_row("obligation"),
        ["empty-003", "Pflicht zwei"] + _label_row("obligation"),
    ]
    path = FIXTURE_DIR / "synthetic_empty_text.csv"
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS, rows)
    return path


def build_duplicate_id() -> Path:
    """Two different rows intentionally reuse one explicit source ID."""
    rows = [
        ["duplicate-source-001", "Definition Begriff Wohnsitz."]
        + _label_row("definition"),
        ["duplicate-source-001", "Pflicht zur Anmeldung."]
        + _label_row("obligation"),
        ["duplicate-source-002", "Erlaubnis zur Abgabe."]
        + _label_row("permission"),
    ]
    path = FIXTURE_DIR / "synthetic_duplicate_id.csv"
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS, rows)
    return path


def duplicate_text_same_label_rows() -> list[list[str]]:
    """Three normalized-text groups per class, two source IDs per group."""
    rows: list[list[str]] = []
    stems = {
        "definition": "Definition Gruppe",
        "obligation": "Pflicht Gruppe",
        "permission": "Erlaubnis Gruppe",
        "prohibition": "Verbot Gruppe",
    }
    source_number = 1
    for label in LABEL_CLASSES:
        for group_number in range(3):
            text = f"{stems[label]} {group_number}"
            for _ in range(2):
                rows.append(
                    [f"same-label-{source_number:03d}", text] + _label_row(label)
                )
                source_number += 1
    return rows


def build_duplicate_text_same_label() -> Path:
    path = FIXTURE_DIR / "synthetic_duplicate_text_same_label.csv"
    _write_csv(
        path,
        [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS,
        duplicate_text_same_label_rows(),
    )
    return path


def build_cross_split_leakage_legacy_name() -> Path:
    """Legacy filename retained as a regression input.

    R1's group-aware allocator must now ingest it without cross-split leakage.
    """
    path = FIXTURE_DIR / "synthetic_cross_split_leakage.csv"
    _write_csv(
        path,
        [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS,
        duplicate_text_same_label_rows(),
    )
    return path


def build_duplicate_text_conflicting_label() -> Path:
    rows = [
        ["conflict-001", "Gleicher normierter Text"] + _label_row("definition"),
        ["conflict-002", "Gleicher, normierter Text!"] + _label_row("obligation"),
        ["conflict-003", "Unabhängiger Satz"] + _label_row("permission"),
    ]
    path = FIXTURE_DIR / "synthetic_duplicate_text_conflicting_label.csv"
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS, rows)
    return path


def build_no_source_id() -> Path:
    path = FIXTURE_DIR / "synthetic_no_source_id.csv"
    rows = [[text] + _label_row(label) for text, label in normal_rows()]
    _write_csv(path, [TEXT_COLUMN] + LABEL_COLUMNS, rows)
    return path


def build_unknown_label() -> Path:
    rows = [
        ["unknown-001", "Definition A", "1", "0", "0", "0"],
        ["unknown-002", "Bad unknown", "0", "0", "0", "2"],
    ]
    path = FIXTURE_DIR / "synthetic_unknown_label.csv"
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS, rows)
    return path


def build_one_hot_all_zero() -> Path:
    rows = [
        ["zero-001", "Definition A", "0", "0", "0", "0"],
        ["zero-002", "Pflicht B", "0", "0", "0", "0"],
    ]
    path = FIXTURE_DIR / "synthetic_one_hot_all_zero.csv"
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS, rows)
    return path


def build_one_hot_multi_hot() -> Path:
    rows = [
        ["multi-001", "Definition A", "1", "0", "0", "0"],
        ["multi-002", "Bad multi-hot", "1", "1", "0", "0"],
    ]
    path = FIXTURE_DIR / "synthetic_one_hot_multi_hot.csv"
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS, rows)
    return path


def build_one_hot_non_binary() -> Path:
    rows = [
        ["binary-001", "Definition A", "1", "0", "0", "0"],
        ["binary-002", "Bad non-binary", "0", "0", "0", "2"],
    ]
    path = FIXTURE_DIR / "synthetic_one_hot_non_binary.csv"
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS, rows)
    return path


def build_missing_label_column() -> Path:
    rows = [
        ["missing-001", "Definition A", "1", "0", "0"],
        ["missing-002", "Pflicht B", "0", "1", "0"],
    ]
    path = FIXTURE_DIR / "synthetic_missing_label_column.csv"
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS[:3], rows)
    return path


def build_small_class() -> Path:
    rows: list[tuple[str, str]] = []
    for label, stem in (
        ("definition", "Definition"),
        ("obligation", "Pflicht"),
        ("permission", "Erlaubnis"),
    ):
        rows.extend((f"{stem} {letter}", label) for letter in "ABCDEF")
    rows.append(("Verbot A", "prohibition"))
    return _write_labelled("synthetic_small_class.csv", rows, "small")


def build_encoding_error() -> Path:
    rows = [
        ["encoding-001", "Definition A"] + _label_row("definition"),
        ["encoding-002", "\x00bad bytes here"] + _label_row("obligation"),
    ]
    path = FIXTURE_DIR / "synthetic_encoding_error.csv"
    _write_csv(path, [ID_COLUMN, TEXT_COLUMN] + LABEL_COLUMNS, rows)
    return path


def build_all() -> list[Path]:
    return [
        build_normal(),
        build_large_normal(),
        build_empty_text(),
        build_duplicate_id(),
        build_duplicate_text_same_label(),
        build_cross_split_leakage_legacy_name(),
        build_duplicate_text_conflicting_label(),
        build_no_source_id(),
        build_unknown_label(),
        build_one_hot_all_zero(),
        build_one_hot_multi_hot(),
        build_one_hot_non_binary(),
        build_missing_label_column(),
        build_small_class(),
        build_encoding_error(),
    ]


if __name__ == "__main__":
    for fixture_path in build_all():
        print(fixture_path)
