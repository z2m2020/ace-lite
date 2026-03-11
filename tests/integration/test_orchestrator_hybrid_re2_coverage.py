from __future__ import annotations

from ace_lite.rankers import _compute_term_coverage, fuse_rrf, rank_candidates_hybrid_re2


def test_hybrid_re2_term_coverage_scores_underscore_substring_as_partial() -> None:
    entry = {
        'module': 'src.core.auth',
        'symbols': [
            {
                'name': 'validate_tokenize',
                'qualified_name': 'src.core.auth.validate_tokenize',
            },
        ],
        'imports': [],
    }

    coverage = _compute_term_coverage(
        path='src/core/auth.py',
        entry=entry,
        terms=['token'],
    )

    assert coverage == 0.5


def test_hybrid_re2_term_coverage_scores_token_match_as_exact() -> None:
    entry = {
        'module': 'src.core.auth',
        'symbols': [
            {
                'name': 'validate_token',
                'qualified_name': 'src.core.auth.validate_token',
            },
        ],
        'imports': [],
    }

    coverage = _compute_term_coverage(
        path='src/core/token.py',
        entry=entry,
        terms=['token'],
    )

    assert coverage == 1.0


def test_hybrid_re2_term_coverage_normalizes_by_term_count() -> None:
    entry = {
        'module': 'src.core.auth',
        'symbols': [
            {
                'name': 'validate_token',
                'qualified_name': 'src.core.auth.validate_token',
            },
        ],
        'imports': [],
    }

    coverage = _compute_term_coverage(
        path='src/core/token.py',
        entry=entry,
        terms=['token', 'missing'],
    )

    assert coverage == 0.5



def test_fuse_rrf_accumulates_positions() -> None:
    scores = fuse_rrf(
        rankings=[["a.py", "b.py", "c.py"], ["b.py", "a.py"]],
        rrf_k=60,
    )

    assert scores["a.py"] > 0.0
    assert scores["b.py"] > scores["c.py"]


def test_hybrid_re2_rrf_fusion_marks_breakdown() -> None:
    files_map = {
        "src/core/auth.py": {
            "module": "src.core.auth",
            "language": "python",
            "symbols": [
                {
                    "name": "validate_token",
                    "qualified_name": "src.core.auth.validate_token",
                },
                {
                    "name": "refresh_session",
                    "qualified_name": "src.core.auth.refresh_session",
                },
            ],
            "imports": [],
        },
        "src/core/session.py": {
            "module": "src.core.session",
            "language": "python",
            "symbols": [
                {
                    "name": "ensure_session",
                    "qualified_name": "src.core.session.ensure_session",
                },
            ],
            "imports": [{"module": "src.core.auth", "name": "validate_token"}],
        },
    }

    ranked = rank_candidates_hybrid_re2(
        files_map,
        ["validate", "token"],
        min_score=0,
        top_n=4,
        fusion_mode="rrf",
        rrf_k=75,
    )

    assert ranked
    breakdown = ranked[0]["score_breakdown"]
    assert breakdown["fusion_mode"] == "rrf"
    assert breakdown["rrf_k"] == 75
