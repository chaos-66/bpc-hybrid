"""S2.1-B: stdlib-only streaming importer for the Sun 2024 EStG modality
official supplement (Decision_Logic_data.zip / EStG_sent_vec.csv).

This module is the engine behind ``scripts/ingest_sun_modality.py``. It is
intentionally small, deterministic, and side-effect minimal:

* A pluggable label-adapter seam. This module keeps the headered strict
  one-hot synthetic adapter. The verified headerless official positional
  adapter and complete-vector audit live in ``sun_modality_official``;
  integer-code mappings are never guessed.
* Deterministic stable sample_id derived from source-asset SHA-256,
  explicit source_id, and normalized text. Row-index fallback is used only
  when the caller explicitly omits an id column and is recorded in the
  deterministic manifest.
* Deterministic, stratified, normalized-text-group-aware split. Equal
  normalized texts with one label are indivisible; label conflicts fail
  closed before any data file is written.
* Streaming CSV reader: the official CSV is ~470 MB uncompressed, so
  we never call ``list(reader)`` on the whole file; we walk it
  line-by-line via ``csv.reader`` and yield ``RawRow`` dataclasses.
* Path-traversal-safe ZIP access: member names must be relative POSIX
  paths with no drive letters, NUL bytes, backslashes, or ``..`` segments.
* Overwrite protection: any pre-existing output path aborts the run
  unless ``allow_overwrite=True`` is explicitly passed.
* License: ``unknown_pending_confirmation`` is enforced by the contract;
  the manifest must echo it back without flipping the boolean.

This module does NOT call any LLM, does NOT read ``.env``, does NOT
make network calls, and does NOT touch
``references/`` / ``data/{input,gold,predictions,results}/`` /
``outputs/`` outside the gitignore-allowed reports tree.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import io
import json
import math
import random
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional, Sequence


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class IngestionError(Exception):
    """Base error for the S2.1-B importer."""


class SchemaError(IngestionError):
    """Missing required column / wrong header / wrong number of label columns."""


class OneHotError(IngestionError):
    """A label cell violates the strict one-hot contract."""


class CrossSplitLeakageError(IngestionError):
    """A normalized text appears in more than one split."""


class DuplicateSourceIdError(IngestionError):
    """An explicit source ID appears more than once; ingestion fails closed."""

    code = "duplicate_source_id"


class LabelConflictError(IngestionError):
    """One normalized text maps to conflicting labels; ingestion fails closed."""

    code = "label_conflict"


class MissingSourceIdError(IngestionError):
    """An explicit id column contains an empty source ID."""

    code = "missing_source_id"


class OverwriteRefused(IngestionError):
    """An output path already exists and allow_overwrite is False."""


class ZipSafetyError(IngestionError):
    """A ZIP member name violates the path-traversal safety contract."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class SplitParams:
    train_ratio: float
    dev_ratio: float
    test_ratio: float
    stratified: bool = True
    shuffle: bool = True
    min_per_class_in_smallest_split: int = 1

    def __post_init__(self) -> None:
        total = self.train_ratio + self.dev_ratio + self.test_ratio
        if abs(total - 1.0) > 1e-9:
            raise IngestionError(
                f"split ratios must sum to 1.0, got {total:.6f}"
            )
        if self.train_ratio <= 0 or self.dev_ratio < 0 or self.test_ratio < 0:
            raise IngestionError(
                "train_ratio must be > 0; dev_ratio and test_ratio must be >= 0"
            )
        if self.min_per_class_in_smallest_split < 0:
            raise IngestionError("min_per_class_in_smallest_split must be >= 0")


@dataclasses.dataclass(frozen=True)
class IngestContract:
    """A parsed, validated view of configs/datasets/sun_modality_dataset.json.

    Only the fields the importer actually needs are surfaced; everything
    else is preserved on ``raw`` for downstream manifest use."""

    dataset_id: str
    contract_version: str
    project_root: Path
    contract_path: Path
    contract_sha256: str
    source_zip_path: Path
    source_zip_sha256: str
    source_zip_official_sha1: str
    source_zip_size_bytes: int
    csv_member_logical_name: str
    csv_member_sha256: str
    csv_member_size_uncompressed_bytes: int
    csv_member_crc32: str
    label_classes: tuple[str, ...]
    seed: int
    split: SplitParams
    normalize_for_dedup: "NormalizeFn"
    reject_empty_text: bool
    reject_unknown_label: bool
    reject_missing_label: bool
    reject_one_hot_all_zero: bool
    reject_one_hot_multi_hot: bool
    reject_one_hot_non_binary: bool
    reject_duplicate_id: bool
    reject_cross_split_text_leakage: bool
    rights_status: str
    redistribution_allowed: bool
    publication_in_paper_allowed: bool
    raw: dict

    @property
    def id_namespace(self) -> str:
        return "sun_modality"

    def project_relative_path(self, path: Path, *, field_name: str) -> str:
        """Return a portable project-relative path or fail closed.

        Dataset manifests are deterministic, versioned artifacts.  Persisting a
        caller's drive letter or home directory would make otherwise identical
        imports differ across workspaces, so paths outside ``project_root`` are
        never serialized.
        """
        root = self.project_root.resolve()
        candidate = Path(path).resolve()
        try:
            relative = candidate.relative_to(root)
        except ValueError as exc:
            raise IngestionError(
                f"{field_name} must resolve inside project_root before it can "
                "be written to a deterministic manifest"
            ) from exc
        return relative.as_posix()


# ---------------------------------------------------------------------------
# Normalization + ID
# ---------------------------------------------------------------------------

# Lowercase + collapse whitespace + drop everything except alnum / unicode
# letters. We keep the pattern permissive on purpose: the goal is to detect
# duplicates, not to canonicalize German morphology. The original text is
# always preserved in the output record.
_NORMALIZE_RE = re.compile(r"[\s\u00A0]+", re.UNICODE)
_NON_ALNUM_RE = re.compile(r"[^\w]", re.UNICODE)  # \w includes unicode letters/digits
# \w already includes letters from any script plus digits plus underscore;
# we additionally strip underscores and apostrophes to make German compounds
# join cleanly.
_DROP_LIGHT_PUNCT_RE = re.compile(r"[_\u2019\u2018`\u00b4]", re.UNICODE)


def default_normalize_for_dedup(text: str) -> str:
    """Normalization used both for stable-ID derivation and for
    cross-split leakage detection.

    The function is intentionally simple: lowercase, collapse whitespace,
    drop non-alphanumeric characters, and drop a small set of light
    punctuation. The normalized form is NOT used to overwrite the
    original text in the output record.
    """
    if text is None:
        return ""
    s = text.strip().lower()
    s = _NORMALIZE_RE.sub(" ", s)
    s = _DROP_LIGHT_PUNCT_RE.sub("", s)
    s = _NON_ALNUM_RE.sub("", s)
    return s


def normalize_for_dedup(text: str) -> str:
    """Public alias of :func:`default_normalize_for_dedup`."""
    return default_normalize_for_dedup(text)


# Type alias to keep the IngestContract field readable.
NormalizeFn = Callable[[str], str]


def build_sample_id(
    source_asset_sha256: str,
    normalized_text: str,
    *,
    source_id: Optional[str] = None,
    row_index: Optional[int] = None,
    namespace: str = "sun_modality",
) -> str:
    """Derive a stable deterministic ID from source identity and row identity.

    Explicit ``source_id`` is always preferred. ``row_index`` is accepted only
    as an explicit fallback when no source ID exists. Canonical JSON avoids
    delimiter ambiguity and is stable across platforms.
    """
    source_asset_sha256 = (source_asset_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", source_asset_sha256):
        raise IngestionError("source_asset_sha256 must be 64 lowercase hex characters")
    normalized_text = (normalized_text or "").strip()
    if not normalized_text:
        raise IngestionError("normalized_text must be non-empty for sample ID")
    clean_source_id = (source_id or "").strip()
    if clean_source_id:
        source_key_type = "source_id"
        source_key = clean_source_id
    else:
        if row_index is None or row_index < 0:
            raise IngestionError(
                "row_index fallback must be explicitly provided when source_id is absent"
            )
        source_key_type = "row_index_fallback"
        source_key = str(row_index)
    payload = json.dumps(
        [source_asset_sha256, source_key_type, source_key, normalized_text],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).hexdigest()
    return f"{namespace}_{digest}"


# ---------------------------------------------------------------------------
# CSV / ZIP streaming
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class RawRow:
    row_index: int
    text: str
    label_cells: list[str]
    source_id: Optional[str] = None


def stream_csv_rows_from_zip(
    zip_path: Path,
    member_name: str,
    *,
    text_column: str,
    label_columns: Sequence[str],
    id_column: Optional[str] = None,
    encoding: str = "utf-8",
) -> Iterator[RawRow]:
    """Stream rows from ``member_name`` inside ``zip_path`` without
    extracting anything to disk. Yields :class:`RawRow` records with
    the text and the four (or N) label-cell strings.

    The function NEVER reads the whole file into memory and NEVER
    materializes the full list of rows.
    """
    if not zip_path.is_file():
        raise IngestionError(f"zip not found: {zip_path}")
    label_set = list(label_columns)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # ZIP safety: reject traversal / absolute / drive letters / NUL.
        if _unsafe_member_predicate()(member_name):
            raise ZipSafetyError(f"unsafe member name: {member_name!r}")
        try:
            info = zf.getinfo(member_name)
        except KeyError:
            raise IngestionError(
                f"csv member {member_name!r} not found in {zip_path}"
            )
        with zf.open(info, "r") as raw:
            text_stream = io.TextIOWrapper(raw, encoding=encoding, newline="")
            reader = csv.reader(text_stream)
            try:
                header = next(reader)
            except StopIteration:
                raise SchemaError(f"csv member {member_name!r} is empty (no header)")
            header = [h.strip() for h in header]
            col_index: dict[str, int] = {name: i for i, name in enumerate(header)}
            if text_column not in col_index:
                raise SchemaError(
                    f"csv header missing text column {text_column!r}; got {header}"
                )
            missing = [c for c in label_set if c not in col_index]
            if missing:
                raise SchemaError(
                    f"csv header missing label columns {missing!r}; got {header}"
                )
            text_idx = col_index[text_column]
            label_idxs = [col_index[c] for c in label_set]
            if id_column is not None and id_column not in col_index:
                raise SchemaError(
                    f"csv header missing id column {id_column!r}; got {header}"
                )
            id_idx = col_index[id_column] if id_column is not None else None

            for row_index, row in enumerate(reader):
                # csv.reader returns an empty list for blank lines; treat as
                # "missing label" downstream (validation will fail them).
                if not row:
                    yield RawRow(
                        row_index=row_index,
                        text="",
                        label_cells=[""],
                        source_id="" if id_column is not None else None,
                    )
                    continue
                # Pad short rows so we can index safely.
                if len(row) < len(header):
                    row = row + [""] * (len(header) - len(row))
                text_val = (row[text_idx] or "").strip()
                label_cells = [(row[i] or "").strip() for i in label_idxs]
                source_id = (
                    (row[id_idx] or "").strip() if id_idx is not None else None
                )
                yield RawRow(
                    row_index=row_index,
                    text=text_val,
                    label_cells=label_cells,
                    source_id=source_id,
                )


def stream_csv_rows_from_csv_path(
    csv_path: Path,
    *,
    text_column: str,
    label_columns: Sequence[str],
    id_column: Optional[str] = None,
    encoding: str = "utf-8",
) -> Iterator[RawRow]:
    """Stream rows from a plain CSV path. Used by synthetic fixtures and
    inspect-only mode."""
    if not csv_path.is_file():
        raise IngestionError(f"csv not found: {csv_path}")
    label_set = list(label_columns)
    with csv_path.open("r", encoding=encoding, newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise SchemaError(f"csv is empty (no header): {csv_path}")
        header = [h.strip() for h in header]
        col_index = {name: i for i, name in enumerate(header)}
        if text_column not in col_index:
            raise SchemaError(
                f"csv header missing text column {text_column!r}; got {header}"
            )
        missing = [c for c in label_set if c not in col_index]
        if missing:
            raise SchemaError(
                f"csv header missing label columns {missing!r}; got {header}"
            )
        text_idx = col_index[text_column]
        label_idxs = [col_index[c] for c in label_set]
        if id_column is not None and id_column not in col_index:
            raise SchemaError(
                f"csv header missing id column {id_column!r}; got {header}"
            )
        id_idx = col_index[id_column] if id_column is not None else None

        for row_index, row in enumerate(reader):
            if not row:
                yield RawRow(
                    row_index=row_index,
                    text="",
                    label_cells=[""],
                    source_id="" if id_column is not None else None,
                )
                continue
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            text_val = (row[text_idx] or "").strip()
            label_cells = [(row[i] or "").strip() for i in label_idxs]
            source_id = (
                (row[id_idx] or "").strip() if id_idx is not None else None
            )
            yield RawRow(
                row_index=row_index,
                text=text_val,
                label_cells=label_cells,
                source_id=source_id,
            )


# ---------------------------------------------------------------------------
# Label validation
# ---------------------------------------------------------------------------

def _parse_one_hot_cell(raw: str) -> int:
    s = (raw or "").strip()
    if s in ("0", "1"):
        return int(s)
    if s in ("0.0", "1.0"):
        return int(float(s))
    raise OneHotError(f"non-binary one-hot value: {raw!r}")


def validate_label(
    label_cells: Sequence[str],
    label_classes: Sequence[str],
    *,
    reject_all_zero: bool,
    reject_multi_hot: bool,
    reject_non_binary: bool,
) -> tuple[str, int, int]:
    """Validate a strict one-hot row.

    Returns: ``(label, sum_bits, n_bits)``.

    Raises :class:`OneHotError` on any contract violation.
    """
    if len(label_cells) != len(label_classes):
        raise SchemaError(
            f"label_cells has {len(label_cells)} entries but contract "
            f"requires {len(label_classes)}"
        )
    bits = [_parse_one_hot_cell(c) for c in label_cells]
    sum_bits = sum(bits)
    if reject_non_binary and any(b not in (0, 1) for b in bits):
        raise OneHotError(f"non-binary one-hot value: {bits}")
    if reject_all_zero and sum_bits == 0:
        raise OneHotError("all-zero one-hot row rejected")
    if reject_multi_hot and sum_bits > 1:
        raise OneHotError(f"multi-hot one-hot row rejected: bits={bits}")
    if sum_bits == 0:
        # Caller did not opt into all-zero rejection; fall through but
        # the caller decides what to do.
        return ("__unlabeled__", sum_bits, len(bits))
    label = label_classes[bits.index(1)]
    return (label, sum_bits, len(bits))


def strict_one_hot_label_adapter(raw: RawRow, contract: IngestContract) -> str:
    """Synthetic-fixture adapter used by S2.1-B-R1.

    The official CSV adapter is intentionally absent: its integer-code mapping
    remains pending S2.1-C and must be supplied as a separate adapter only
    after evidence locks the mapping.
    """
    label, _, _ = validate_label(
        raw.label_cells,
        contract.label_classes,
        reject_all_zero=contract.reject_one_hot_all_zero,
        reject_multi_hot=contract.reject_one_hot_multi_hot,
        reject_non_binary=contract.reject_one_hot_non_binary,
    )
    return label


LabelAdapter = Callable[[RawRow, IngestContract], str]


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def deterministic_stratified_split(
    labels: Sequence[str],
    split: SplitParams,
    seed: int,
    *,
    group_keys: Optional[Sequence[str]] = None,
) -> tuple[list[int], list[int], list[int]]:
    """Return a deterministic stratified partition of indivisible groups.

    ``group_keys`` defaults to one unique key per record for callers that have
    no duplicate-text groups. When provided, every record sharing a key must
    share one label and is assigned to one split as an indivisible unit.

    The one and only small-class threshold is expressed in *group count*:

    ``active_nonzero_splits * min_per_class_in_smallest_split``.

    Below that threshold the entire class is assigned to train with an
    explicit warning. At and above it, every active split receives the
    configured minimum number of groups. No record or class is discarded.
    """
    if group_keys is None:
        group_keys = [f"__row_{i}" for i in range(len(labels))]
    if len(labels) != len(group_keys):
        raise IngestionError(
            f"labels/group_keys length mismatch: {len(labels)} != {len(group_keys)}"
        )

    group_to_label: dict[str, str] = {}
    by_class: dict[str, dict[str, list[int]]] = {}
    for i, (lab, group_key) in enumerate(zip(labels, group_keys)):
        previous = group_to_label.get(group_key)
        if previous is not None and previous != lab:
            raise LabelConflictError(
                "label_conflict: normalized-text group "
                f"{group_key!r} has labels {sorted({previous, lab})}"
            )
        group_to_label[group_key] = lab
        by_class.setdefault(lab, {}).setdefault(group_key, []).append(i)

    rng = random.Random(seed)

    train_idx: list[int] = []
    dev_idx: list[int] = []
    test_idx: list[int] = []
    split_order = ("train", "dev", "test")
    ratios = {
        "train": split.train_ratio,
        "dev": split.dev_ratio,
        "test": split.test_ratio,
    }
    active_splits = [name for name in split_order if ratios[name] > 0]
    threshold = len(active_splits) * split.min_per_class_in_smallest_split
    bumped_classes: list[tuple[str, int, int]] = []

    for cls in sorted(by_class):
        group_map = by_class[cls]
        groups = [(key, group_map[key]) for key in sorted(group_map)]
        n_groups = len(groups)
        if n_groups < threshold:
            bumped_classes.append(
                (cls, n_groups, sum(len(indices) for _, indices in groups))
            )
            for _, indices in groups:
                train_idx.extend(indices)
            continue

        # Hamilton allocation on group counts, then enforce the same minimum
        # for every active split by moving groups only from a split that has
        # surplus. This preserves the exact total and never drops a group.
        raw_targets = {name: n_groups * ratios[name] for name in split_order}
        counts = {name: int(math.floor(raw_targets[name])) for name in split_order}
        remainder = n_groups - sum(counts.values())
        fractional_order = sorted(
            split_order,
            key=lambda name: (
                -(raw_targets[name] - counts[name]),
                split_order.index(name),
            ),
        )
        for name in fractional_order[:remainder]:
            counts[name] += 1

        minimum = split.min_per_class_in_smallest_split
        for target in active_splits:
            while counts[target] < minimum:
                donors = [
                    name for name in active_splits if counts[name] > minimum
                ]
                if not donors:
                    raise IngestionError(
                        "small-class threshold allocation invariant failed: "
                        f"class={cls!r}, groups={n_groups}, threshold={threshold}"
                    )
                donor = max(
                    donors,
                    key=lambda name: (
                        counts[name] - minimum,
                        -split_order.index(name),
                    ),
                )
                counts[donor] -= 1
                counts[target] += 1

        rng.shuffle(groups)
        cursor = 0
        destinations = {
            "train": train_idx,
            "dev": dev_idx,
            "test": test_idx,
        }
        for name in split_order:
            for _, indices in groups[cursor:cursor + counts[name]]:
                destinations[name].extend(indices)
            cursor += counts[name]
        if cursor != n_groups:
            raise IngestionError(
                f"group allocation lost groups for class {cls!r}: {cursor}/{n_groups}"
            )

    if bumped_classes:
        sys.stderr.write(
            "[sun_modality_importer] WARNING: small-class group fallback; "
            "formula=active_nonzero_splits*min_per_class_in_smallest_split; "
            f"threshold={threshold}; classes=(label,group_count,record_count)="
            f"{bumped_classes}; assigned every record in those classes to "
            "train-only; no classes or samples dropped.\n"
        )
    return train_idx, dev_idx, test_idx


def check_cross_split_leakage(
    splits: dict[str, Sequence[int]],
    normalized_texts: Sequence[str],
) -> list[tuple[str, tuple[str, ...]]]:
    """Return a list of ``(normalized_text, (split_names, ...))`` for
    every normalized text that appears in more than one split. Empty
    list means no leakage."""
    text_to_splits: dict[str, set[str]] = {}
    for split_name, indices in splits.items():
        for idx in indices:
            text_to_splits.setdefault(normalized_texts[idx], set()).add(split_name)
    leaks = [
        (nt, tuple(sorted(splits_seen)))
        for nt, splits_seen in text_to_splits.items()
        if len(splits_seen) > 1
    ]
    leaks.sort()
    return leaks


# ---------------------------------------------------------------------------
# Manifest + hashing
# ---------------------------------------------------------------------------

def compute_membership_hash(records: Sequence["Record"]) -> str:
    """blake2b-256 over the sorted canonical JSON of (sample_id, label)
    pairs."""
    pairs = sorted((r.sample_id, r.label) for r in records)
    blob = json.dumps(pairs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=32).hexdigest()


def compute_file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def compute_file_sha1(path: Path, chunk: int = 1 << 20) -> str:
    """Stream a file through SHA-1 for official-archive identity checks."""
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def compute_zip_member_sha256(zip_path: Path, member: str) -> str:
    """SHA-256 of a ZIP member, streamed (no extraction to disk)."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        info = zf.getinfo(member)
        h = hashlib.sha256()
        with zf.open(info, "r") as f:
            while True:
                buf = f.read(1 << 20)
                if not buf:
                    break
                h.update(buf)
        return h.hexdigest()


def file_sha256_str(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


# ---------------------------------------------------------------------------
# Record (immutable)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Record:
    sample_id: str
    source_row_index: int
    source_id: Optional[str]
    sample_id_source: str
    text: str
    normalized_text: str
    label: str
    label_one_hot: tuple[int, ...]


# ---------------------------------------------------------------------------
# Importer entry point
# ---------------------------------------------------------------------------

def _unsafe_member_predicate():
    """Factory for the path-traversal safety predicate. Used by both
    the streaming reader and the inspect-only pass."""
    forbidden = re.compile(r"[\x00]")
    drive = re.compile(r"^[A-Za-z]:")

    def is_unsafe(name: str) -> bool:
        if not name:
            return True
        if forbidden.search(name):
            return True
        if name.startswith("/") or name.startswith("\\"):
            return True
        if drive.match(name):
            return True
        if "\\" in name:
            return True
        parts = name.split("/")
        return any(p == ".." for p in parts)

    return is_unsafe


@dataclasses.dataclass
class RejectStats:
    rejected_empty_text: int = 0
    rejected_duplicate_id: int = 0
    rejected_missing_source_id: int = 0
    rejected_unknown_label: int = 0
    rejected_missing_label: int = 0
    rejected_one_hot_all_zero: int = 0
    rejected_one_hot_multi_hot: int = 0
    rejected_one_hot_non_binary: int = 0
    rejected_cross_split_text_leakage: int = 0
    label_conflict: int = 0
    rejected_other: int = 0

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def ingest(
    contract: IngestContract,
    *,
    text_column: str,
    label_columns: Sequence[str],
    id_column: Optional[str] = None,
    out_dir: Path,
    allow_overwrite: bool = False,
    encoding: str = "utf-8",
    csv_path_override: Optional[Path] = None,
    label_adapter: Optional[LabelAdapter] = None,
    extra_records_callback=None,
) -> dict:
    """Run the full ingestion. Returns the parsed manifest as a dict.

    The function streams the source CSV line-by-line, validates each
    row against the contract, writes the valid records to
    ``<out_dir>/records.jsonl``, then writes train/dev/test
    ``.jsonl`` files, and finally writes the manifest as
    ``<out_dir>/manifest.json``.

    The function does NOT call any LLM, does NOT read ``.env``, and
    does NOT touch forbidden paths.
    """
    if not label_columns:
        raise IngestionError("label_columns must be a non-empty list")
    active_label_adapter = label_adapter or strict_one_hot_label_adapter
    if (
        active_label_adapter is strict_one_hot_label_adapter
        and len(label_columns) != len(contract.label_classes)
    ):
        raise IngestionError(
            "strict_one_hot synthetic adapter requires one label column per "
            f"canonical class; got {len(label_columns)} columns for "
            f"{len(contract.label_classes)} classes"
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records_path = out_dir / "records.jsonl"
    splits_dir = out_dir / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)
    train_path = splits_dir / "train.jsonl"
    dev_path = splits_dir / "dev.jsonl"
    test_path = splits_dir / "test.jsonl"
    manifest_path = out_dir / "manifest.json"
    for p in (records_path, train_path, dev_path, test_path, manifest_path):
        if p.exists() and not allow_overwrite:
            raise OverwriteRefused(
                f"output path already exists (refuse overwrite): {p}. "
                "Re-run with allow_overwrite=True to force."
            )
    if allow_overwrite:
        for p in (records_path, train_path, dev_path, test_path, manifest_path):
            if p.exists():
                p.unlink()

    # Decide row source: ZIP-streaming (default) or plain CSV.
    if csv_path_override is not None:
        rows_iter = stream_csv_rows_from_csv_path(
            csv_path_override,
            text_column=text_column,
            label_columns=label_columns,
            id_column=id_column,
            encoding=encoding,
        )
    else:
        rows_iter = stream_csv_rows_from_zip(
            contract.source_zip_path,
            contract.csv_member_logical_name,
            text_column=text_column,
            label_columns=label_columns,
            id_column=id_column,
            encoding=encoding,
        )

    label_in_counter: Counter = Counter()
    valid_records: list[Record] = []
    seen_sample_ids: set[str] = set()
    seen_source_ids: set[str] = set()
    normalized_text_labels: dict[str, str] = {}
    stats = RejectStats()
    source_asset_sha256 = (
        compute_file_sha256(csv_path_override)
        if csv_path_override is not None
        else contract.source_zip_sha256
    )

    # Validate every raw identity and group-label invariant before writing any
    # derived data file. Duplicate source IDs and label conflicts fail closed.
    for raw in rows_iter:
        text = (raw.text or "").strip()
        label_in_counter["__total__"] += 1

        if id_column is not None:
            source_id = (raw.source_id or "").strip()
            if not source_id:
                stats.rejected_missing_source_id += 1
                error = MissingSourceIdError(
                    "missing_source_id: explicit id column "
                    f"{id_column!r} is empty at row {raw.row_index}"
                )
                error.stats = stats.as_dict()  # type: ignore[attr-defined]
                raise error
            if source_id in seen_source_ids:
                stats.rejected_duplicate_id += 1
                error = DuplicateSourceIdError(
                    "duplicate_source_id: explicit source_id "
                    f"{source_id!r} appears more than once (row {raw.row_index})"
                )
                error.stats = stats.as_dict()  # type: ignore[attr-defined]
                raise error
            seen_source_ids.add(source_id)
        else:
            source_id = None

        if contract.reject_empty_text and not text:
            stats.rejected_empty_text += 1
            continue
        nt = contract.normalize_for_dedup(text)
        if not nt:
            stats.rejected_empty_text += 1
            continue
        try:
            label = active_label_adapter(raw, contract)
        except SchemaError as e:
            stats.rejected_other += 1
            sys.stderr.write(f"[ingest] schema error at row {raw.row_index}: {e}\n")
            continue
        except OneHotError as e:
            msg = str(e)
            if "all-zero" in msg:
                stats.rejected_one_hot_all_zero += 1
            elif "multi-hot" in msg:
                stats.rejected_one_hot_multi_hot += 1
            elif "non-binary" in msg:
                stats.rejected_one_hot_non_binary += 1
            else:
                stats.rejected_other += 1
            continue
        if label == "__unlabeled__":
            stats.rejected_missing_label += 1
            continue
        if label not in contract.label_classes:
            stats.rejected_unknown_label += 1
            continue

        previous_label = normalized_text_labels.get(nt)
        if previous_label is not None and previous_label != label:
            stats.label_conflict += 1
            error = LabelConflictError(
                "label_conflict: normalized_text "
                f"{nt!r} maps to conflicting labels "
                f"{sorted({previous_label, label})}"
            )
            error.stats = stats.as_dict()  # type: ignore[attr-defined]
            raise error
        normalized_text_labels[nt] = label

        sid = build_sample_id(
            source_asset_sha256,
            nt,
            source_id=source_id,
            row_index=raw.row_index if source_id is None else None,
            namespace=contract.id_namespace,
        )
        if contract.reject_duplicate_id and sid in seen_sample_ids:
            stats.rejected_duplicate_id += 1
            error = DuplicateSourceIdError(
                f"duplicate_sample_id: derived ID {sid!r} appears more than once"
            )
            error.stats = stats.as_dict()  # type: ignore[attr-defined]
            raise error
        seen_sample_ids.add(sid)
        label_in_counter[label] += 1
        rec = Record(
            sample_id=sid,
            source_row_index=raw.row_index,
            source_id=source_id,
            sample_id_source=("source_id" if source_id is not None else "row_index_fallback"),
            text=text,
            normalized_text=nt,
            label=label,
            label_one_hot=_to_one_hot(label, contract.label_classes),
        )
        valid_records.append(rec)
        if extra_records_callback is not None:
            extra_records_callback(rec)

    if not valid_records:
        raise IngestionError(
            f"no valid records produced; total_rows={sum(label_in_counter.values())}; "
            f"stats={stats.as_dict()}"
        )

    # Split by normalized-text group, never by individual record.
    labels = [r.label for r in valid_records]
    train_idx, dev_idx, test_idx = deterministic_stratified_split(
        labels,
        contract.split,
        contract.seed,
        group_keys=[r.normalized_text for r in valid_records],
    )
    splits = {
        "train": train_idx,
        "dev": dev_idx,
        "test": test_idx,
    }
    # Cross-split leakage check
    if contract.reject_cross_split_text_leakage:
        nt_seq = [r.normalized_text for r in valid_records]
        leaks = check_cross_split_leakage(splits, nt_seq)
        if leaks:
            sample = leaks[:3]
            raise CrossSplitLeakageError(
                f"cross-split normalized-text leakage detected: "
                f"{len(leaks)} colliding texts (first 3: {sample})."
            )

    # Write records and splits only after every fail-closed validation and
    # group-leakage invariant has succeeded.
    _write_split_jsonl(records_path, valid_records)
    _write_split_jsonl(train_path, [valid_records[i] for i in train_idx])
    _write_split_jsonl(dev_path, [valid_records[i] for i in dev_idx])
    _write_split_jsonl(test_path, [valid_records[i] for i in test_idx])

    # Membership hash (over all valid records, not just splits)
    membership_hash = compute_membership_hash(valid_records)

    # Output file hashes
    role_for_path = {
        records_path: "records",
        train_path: "train_split",
        dev_path: "dev_split",
        test_path: "test_split",
    }
    output_files: list[dict] = []
    for p, role in role_for_path.items():
        sha = compute_file_sha256(p)
        size = p.stat().st_size
        with p.open("r", encoding="utf-8") as f:
            row_count = sum(1 for _ in f)
        output_files.append(
            {
                "role": role,
                "path": p.relative_to(out_dir).as_posix(),
                "sha256": sha,
                "size_bytes": size,
                "row_count": row_count,
            }
        )

    # Label distributions per split
    def _label_dist(idxs: list[int]) -> dict:
        c = Counter(valid_records[i].label for i in idxs)
        return {k: int(v) for k, v in sorted(c.items())}

    label_dist_valid = {k: int(v) for k, v in sorted(
        Counter(r.label for r in valid_records).items()
    )}
    label_dist_in = {k: int(v) for k, v in sorted(label_in_counter.items()) if k != "__total__"}
    total_in = int(label_in_counter.get("__total__", 0))
    total_rejected = total_in - len(valid_records)

    manifest = {
        "schema_version": "1.3.1",
        "manifest_id": f"{contract.dataset_id}@{contract.contract_version}",
        "dataset_id": contract.dataset_id,
        "contract_version": contract.contract_version,
        "contract_path": contract.project_relative_path(
            contract.contract_path, field_name="contract_path"
        ),
        "contract_sha256": contract.contract_sha256,
        "importer_version": "sun_modality_importer@1.3.1",
        "importer_module": "bpc_hybrid.datasets.sun_modality_importer",
        "label_adapter": active_label_adapter.__name__,
        "split_origin": "project_reconstructed_deterministic_split",
        "source_schema": {
            "mode": "headered_named_columns",
            "encoding": encoding,
            "delimiter": ",",
            "has_header": True,
            "text_column": text_column,
            "source_id_column": id_column,
            "label_mode": "strict_one_hot_synthetic_fixture",
            "label_columns": list(label_columns),
            "vector_column": None,
        },
        "vector_policy": {
            "present": False,
            "structure": None,
            "element_dimension": None,
            "validation_status": "not_applicable_synthetic_fixture",
            "use_for_training": "not_applicable",
        },
        "source_asset": {
            "logical_name": "Decision_Logic_data.zip",
            "local_path": contract.project_relative_path(
                contract.source_zip_path, field_name="source_asset.local_path"
            ),
            "official_sha1": contract.source_zip_official_sha1,
            "local_sha256": contract.source_zip_sha256,
            "size_bytes": contract.source_zip_size_bytes,
            "csv_member_logical_name": contract.csv_member_logical_name,
            "csv_member_sha256": contract.csv_member_sha256,
            "csv_member_size_uncompressed_bytes": contract.csv_member_size_uncompressed_bytes,
            "csv_member_crc32": contract.csv_member_crc32,
        },
        "seed": contract.seed,
        "sample_id_policy": {
            "algorithm": (
                "blake2b-64 over canonical JSON of "
                "[source_asset_sha256, source_key_type, source_key, normalized_text]"
            ),
            "source_asset_sha256": source_asset_sha256,
            "source_id_column": id_column,
            "source_id_mode": (
                "explicit_source_id" if id_column is not None else "row_index_fallback"
            ),
            "row_index_fallback_used": id_column is None,
        },
        "split_params": {
            "train_ratio": contract.split.train_ratio,
            "dev_ratio": contract.split.dev_ratio,
            "test_ratio": contract.split.test_ratio,
            "stratified": contract.split.stratified,
            "shuffle": contract.split.shuffle,
            "min_per_class_in_smallest_split": contract.split.min_per_class_in_smallest_split,
        },
        "total_samples_in": total_in,
        "total_samples_valid": len(valid_records),
        "total_samples_rejected": total_rejected,
        "label_distribution_in": label_dist_in,
        "label_distribution_valid": label_dist_valid,
        "train_size": len(train_idx),
        "dev_size": len(dev_idx),
        "test_size": len(test_idx),
        "train_label_distribution": _label_dist(train_idx),
        "dev_label_distribution": _label_dist(dev_idx),
        "test_label_distribution": _label_dist(test_idx),
        "membership_hash": {
            "algorithm": "blake2b-256 over sorted JSON of [(sample_id, label)]",
            "value": membership_hash,
        },
        "output_files": output_files,
        "stats": stats.as_dict(),
        "lifecycle": {
            "stage": "development",
            "ready_for_training": False,
            "ready_for_evaluation": False,
            "ready_for_publication": False,
            "notes": (
                "S2.1-B development manifest. License is unknown_pending_confirmation; "
                "this manifest must NOT be used to publish or re-distribute the original CSV."
            ),
        },
        "license": {
            "rights_status": contract.rights_status,
            "redistribution_allowed": contract.redistribution_allowed,
            "publication_in_paper_allowed": contract.publication_in_paper_allowed,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_split_jsonl(path: Path, records: Sequence[Record]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(
                json.dumps(
                    {
                        "sample_id": r.sample_id,
                        "source_row_index": r.source_row_index,
                        "source_id": r.source_id,
                        "sample_id_source": r.sample_id_source,
                        "text": r.text,
                        "normalized_text": r.normalized_text,
                        "label": r.label,
                        "label_one_hot": list(r.label_one_hot),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )


def _to_one_hot(label: str, classes: Sequence[str]) -> tuple[int, ...]:
    return tuple(1 if c == label else 0 for c in classes)


# ---------------------------------------------------------------------------
# Contract loader
# ---------------------------------------------------------------------------

def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            buf = f.read(1 << 20)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def load_contract(contract_path: Path, *, project_root: Path) -> IngestContract:
    """Parse the JSON contract and return a typed :class:`IngestContract`.

    Only the S2.1-B-relevant fields are typed; the full raw JSON is
    preserved on ``IngestContract.raw`` for downstream manifest use.
    """
    project_root = Path(project_root).resolve()
    contract_path = Path(contract_path)
    if not contract_path.is_absolute():
        contract_path = project_root / contract_path
    contract_path = contract_path.resolve()
    raw = json.loads(contract_path.read_text(encoding="utf-8"))
    src = raw.get("source_zip_local_path")
    if not src:
        raise IngestionError("contract missing source_zip_local_path")
    zip_path = (project_root / src) if not Path(src).is_absolute() else Path(src)
    split = SplitParams(
        train_ratio=float(raw["split"]["ratios"]["train"]),
        dev_ratio=float(raw["split"]["ratios"]["dev"]),
        test_ratio=float(raw["split"]["ratios"]["test"]),
        stratified=bool(raw["split"].get("stratified", True)),
        shuffle=bool(raw["split"].get("shuffle", True)),
        min_per_class_in_smallest_split=int(
            raw["split"].get("min_per_class_in_smallest_split", 1)
        ),
    )
    return IngestContract(
        dataset_id=str(raw["dataset_id"]),
        contract_version=str(raw["contract_version"]),
        project_root=project_root,
        contract_path=contract_path,
        contract_sha256=_sha256_of_file(contract_path),
        source_zip_path=zip_path,
        source_zip_sha256=str(raw["source_zip_local_sha256"]),
        source_zip_official_sha1=str(raw["source_zip_official_sha1"]),
        source_zip_size_bytes=int(raw["source_zip_size_bytes"]),
        csv_member_logical_name=str(raw["csv_member_logical_name"]),
        csv_member_sha256=str(raw["csv_member_local_sha256"]),
        csv_member_size_uncompressed_bytes=int(raw["csv_member_size_uncompressed_bytes"]),
        csv_member_crc32=str(raw["csv_member_crc32"]),
        label_classes=tuple(raw["label_taxonomy"]["modality_classes_canonical"]),
        seed=int(raw["split"]["seed"]),
        split=split,
        normalize_for_dedup=default_normalize_for_dedup,
        reject_empty_text=bool(raw["validation"]["reject_empty_text"]),
        reject_unknown_label=True,  # implicit: only known classes accepted
        reject_missing_label=True,  # implicit: an all-zero row is "missing"
        reject_one_hot_all_zero=bool(raw["validation"]["reject_one_hot_all_zero"]),
        reject_one_hot_multi_hot=bool(raw["validation"]["reject_one_hot_multi_hot"]),
        reject_one_hot_non_binary=bool(raw["validation"]["reject_one_hot_non_binary"]),
        reject_duplicate_id=bool(
            raw["validation"].get("reject_duplicate_source_id", True)
            and raw["validation"].get("reject_duplicate_sample_id", True)
        ),
        reject_cross_split_text_leakage=bool(
            raw["validation"]["reject_cross_split_text_leakage"]
        ),
        rights_status=str(raw["license"]["rights_status"]),
        redistribution_allowed=bool(raw["license"]["redistribution_allowed"]),
        publication_in_paper_allowed=bool(raw["license"]["publication_in_paper_allowed"]),
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Inspect-only
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class InspectReport:
    zip_path: str
    zip_size_bytes: int
    zip_actual_sha1: str
    zip_expected_official_sha1: str
    zip_official_sha1_match: bool
    zip_actual_sha256: str
    zip_expected_local_sha256: str
    zip_local_sha256_match: bool
    csv_member: str
    csv_member_size_uncompressed: int
    csv_member_crc32: str
    csv_member_sha256: str
    csv_member_sha256_match_expected: bool
    header: list[str]
    sample_rows: list[dict]
    write_action: str  # always "none" for inspect-only

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def inspect_only(
    contract: IngestContract,
    *,
    text_column: str,
    label_columns: Sequence[str],
    id_column: Optional[str] = None,
    csv_path_override: Optional[Path] = None,
    sample_n: int = 5,
    encoding: str = "utf-8",
) -> InspectReport:
    """Open the ZIP, verify integrity, list members, dump the first
    ``sample_n`` rows of the CSV member, and report. NEVER writes any
    file to disk; NEVER materializes the full CSV in memory.
    """
    sample_n = max(0, int(sample_n))
    # SHA-1 and SHA-256 are independent streamed identity checks.
    zip_sha1 = compute_file_sha1(contract.source_zip_path)
    zip_sha256 = compute_file_sha256(contract.source_zip_path)
    zip_size = contract.source_zip_path.stat().st_size

    # Open ZIP
    with zipfile.ZipFile(contract.source_zip_path, "r") as zf:
        # Confirm testzip
        bad = zf.testzip()
        if bad is not None:
            raise IngestionError(f"zip corruption: {bad!r}")
        # Compute member sha256 via streaming
        member_sha256 = compute_zip_member_sha256(
            contract.source_zip_path, contract.csv_member_logical_name
        )
        info = zf.getinfo(contract.csv_member_logical_name)
        if csv_path_override is None:
            with zf.open(info, "r") as raw:
                text_stream = io.TextIOWrapper(raw, encoding=encoding, newline="")
                reader = csv.reader(text_stream)
                try:
                    header = next(reader)
                except StopIteration:
                    raise SchemaError(
                        f"csv member {contract.csv_member_logical_name!r} is empty"
                    )
                col_index = {name: i for i, name in enumerate(header)}
                if text_column not in col_index:
                    raise SchemaError(
                        f"csv header missing text column {text_column!r}; got {header}"
                    )
                label_idxs = [col_index[c] for c in label_columns]
                text_idx = col_index[text_column]
                if id_column is not None and id_column not in col_index:
                    raise SchemaError(
                        f"csv header missing id column {id_column!r}; got {header}"
                    )
                id_idx = col_index[id_column] if id_column is not None else None
                sample_rows: list[dict] = []
                for row_index, row in enumerate(reader):
                    if not row:
                        continue
                    if len(row) < len(header):
                        row = row + [""] * (len(header) - len(row))
                    sample_rows.append(
                        {
                            "row_index": row_index,
                            "source_id": (
                                (row[id_idx] or "").strip()
                                if id_idx is not None else None
                            ),
                            "text": (row[text_idx] or "").strip(),
                            "label_cells": [
                                (row[i] or "").strip() for i in label_idxs
                            ],
                        }
                    )
                    if len(sample_rows) >= sample_n:
                        break
        else:
            with csv_path_override.open("r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    raise SchemaError(f"csv is empty (no header): {csv_path_override}")
                col_index = {name: i for i, name in enumerate(header)}
                if text_column not in col_index:
                    raise SchemaError(
                        f"csv header missing text column {text_column!r}; got {header}"
                    )
                label_idxs = [col_index[c] for c in label_columns]
                text_idx = col_index[text_column]
                if id_column is not None and id_column not in col_index:
                    raise SchemaError(
                        f"csv header missing id column {id_column!r}; got {header}"
                    )
                id_idx = col_index[id_column] if id_column is not None else None
                sample_rows = []
                for row_index, row in enumerate(reader):
                    if not row:
                        continue
                    if len(row) < len(header):
                        row = row + [""] * (len(header) - len(row))
                    sample_rows.append(
                        {
                            "row_index": row_index,
                            "source_id": (
                                (row[id_idx] or "").strip()
                                if id_idx is not None else None
                            ),
                            "text": (row[text_idx] or "").strip(),
                            "label_cells": [
                                (row[i] or "").strip() for i in label_idxs
                            ],
                        }
                    )
                    if len(sample_rows) >= sample_n:
                        break

    return InspectReport(
        zip_path=str(contract.source_zip_path).replace("\\", "/"),
        zip_size_bytes=zip_size,
        zip_actual_sha1=zip_sha1,
        zip_expected_official_sha1=contract.source_zip_official_sha1,
        zip_official_sha1_match=(zip_sha1 == contract.source_zip_official_sha1),
        zip_actual_sha256=zip_sha256,
        zip_expected_local_sha256=contract.source_zip_sha256,
        zip_local_sha256_match=(zip_sha256 == contract.source_zip_sha256),
        csv_member=contract.csv_member_logical_name,
        csv_member_size_uncompressed=info.file_size,
        csv_member_crc32=f"{info.CRC:08X}",
        csv_member_sha256=member_sha256,
        csv_member_sha256_match_expected=(
            member_sha256 == contract.csv_member_sha256
        ),
        header=list(header),
        sample_rows=sample_rows,
        write_action="none",
    )
