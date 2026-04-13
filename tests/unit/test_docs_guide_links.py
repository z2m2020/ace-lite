from __future__ import annotations

import re
from pathlib import Path

from ace_lite.cli_app.cli_enhancements import HelpExamples
from ace_lite.cli_app.commands.doctor import DOCTOR_HELP_EXAMPLES
from ace_lite.cli_app.commands.plan_quick import PLAN_QUICK_EXAMPLES
from ace_lite.cli_app.docs_links import COMMAND_GUIDES, GUIDES, HELP_TEMPLATES

DOC_PATTERN = re.compile(r"docs/[A-Za-z0-9_./-]+\.md")
REPO_ROOT = Path(__file__).resolve().parents[2]


def _all_referenced_docs() -> set[str]:
    docs: set[str] = set(GUIDES.values()) | set(COMMAND_GUIDES.values())
    for template in HELP_TEMPLATES.values():
        docs.update(DOC_PATTERN.findall(template))
    docs.update(DOC_PATTERN.findall(HelpExamples.BASE_EXAMPLES))
    docs.update(DOC_PATTERN.findall(HelpExamples.PLAN_EXAMPLES))
    docs.update(DOC_PATTERN.findall(HelpExamples.REPO_MAP_EXAMPLES))
    docs.update(DOC_PATTERN.findall(HelpExamples.INDEX_EXAMPLES))
    docs.update(DOC_PATTERN.findall(HelpExamples.DOCTOR_EXAMPLES))
    docs.update(DOC_PATTERN.findall(DOCTOR_HELP_EXAMPLES))
    docs.update(DOC_PATTERN.findall(PLAN_QUICK_EXAMPLES))
    return docs


def test_all_help_referenced_docs_exist() -> None:
    missing = sorted(
        doc_path
        for doc_path in _all_referenced_docs()
        if not (REPO_ROOT / doc_path).exists()
    )

    assert missing == []
