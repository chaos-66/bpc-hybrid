from __future__ import annotations

from bpc_hybrid.b0_v10.segmentation import find_deontic_nuclei, plan_clause_units_b1


def _fake_annotation(source: str) -> dict:
    """Single CoreNLP-like sentence spanning full source."""
    return {
        "sentences": [
            {
                "tokens": [
                    {
                        "index": 1,
                        "word": source.split()[0] if source.split() else "X",
                        "characterOffsetBegin": 0,
                        "characterOffsetEnd": max(1, len(source.split()[0]) if source.split() else 1),
                    },
                    {
                        "index": 2,
                        "word": source.split()[-1] if source.split() else "Y",
                        "characterOffsetBegin": max(0, len(source) - len(source.split()[-1]) if source.split() else 0),
                        "characterOffsetEnd": len(source),
                    },
                ]
            }
        ]
    }


def _n_units(text: str) -> int:
    units, _ = plan_clause_units_b1(_fake_annotation(text), text)
    return len(units)


def test_shall_and_may_should_split() -> None:
    text = "The taxpayer shall file the return and the office may inspect the records."
    assert _n_units(text) >= 2
    units, stats = plan_clause_units_b1(_fake_annotation(text), text)
    assert stats["deontic_nucleus_splits"] >= 1
    assert any(u.get("reason") == "deontic_nucleus_split" for u in units)


def test_may_but_shall_should_split() -> None:
    text = "The employee may leave early but the employer shall pay overtime."
    assert _n_units(text) >= 2


def test_shall_mean_plus_independent_obligation_should_split() -> None:
    text = "Income shall mean net profit and the taxpayer shall declare it annually."
    assert _n_units(text) >= 2


def test_may_not_stays_one_nucleus() -> None:
    text = "The employee may not sell the allowance to third parties."
    nuclei = find_deontic_nuclei(text)
    assert len(nuclei) == 1
    assert nuclei[0]["label"] == "prohibition"
    assert _n_units(text) == 1


def test_shall_not_stays_one_nucleus() -> None:
    text = "The authority shall not disclose personal data without consent."
    nuclei = find_deontic_nuclei(text)
    assert len(nuclei) == 1
    assert nuclei[0]["label"] == "prohibition"
    assert _n_units(text) == 1


def test_same_modal_coordinated_actions_no_split() -> None:
    # only one modal nucleus controlling A and B
    text = "The taxpayer shall perform A and B under this section."
    nuclei = find_deontic_nuclei(text)
    assert len(nuclei) == 1
    assert _n_units(text) == 1


def test_numbered_list_no_spurious_split() -> None:
    text = "Business expenses shall include: 1. contributions to funds 2. travel costs."
    nuclei = find_deontic_nuclei(text)
    assert len(nuclei) == 1
    assert _n_units(text) == 1


def test_subordinate_independent_modal_should_split() -> None:
    # two independent deontic nuclei separated by semicolon
    text = "The taxpayer shall file the return; the office may grant an exemption."
    assert _n_units(text) >= 2


def test_relative_clause_without_modal_no_split() -> None:
    text = "The taxpayer who files late shall pay a surcharge."
    # one shall only
    assert len(find_deontic_nuclei(text)) == 1
    assert _n_units(text) == 1


def test_v4_underseg_counterexample_not_over_split() -> None:
    # aggressive multi-predicate would over-split; B1 should keep single obligation nucleus lists intact
    text = "The fund shall collect contributions, maintain accounts and publish reports."
    assert len(find_deontic_nuclei(text)) == 1
    assert _n_units(text) == 1
