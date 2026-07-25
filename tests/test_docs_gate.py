from pathlib import Path

from scripts.docs_gate import validate


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_docs_gate_rejects_missing_index_backlog_link(tmp_path):
    write(
        tmp_path / "docs" / "INDEX.md",
        "# Project Index\n\n"
        "## Active\n\n"
        "| Date | Feature | Status | Sprint Backlog |\n"
        "|------|---------|--------|----------------|\n"
        "| 20260725 | broken | planned | [->](./missing/sprint-backlog.md) |\n",
    )

    errors = validate(tmp_path)

    assert errors == ["docs/INDEX.md links to missing target ./missing/sprint-backlog.md"]


def test_docs_gate_rejects_invalid_adr_status(tmp_path):
    write(tmp_path / "docs" / "INDEX.md", "# Project Index\n")
    write(
        tmp_path / "docs" / "adr" / "0001-example.md",
        "---\nstatus: maybe\n---\n\n# Example\n",
    )

    errors = validate(tmp_path)

    assert errors == ["docs/adr/0001-example.md has invalid ADR status maybe"]


def test_docs_gate_accepts_existing_index_links_and_adr_status(tmp_path):
    write(
        tmp_path / "docs" / "INDEX.md",
        "# Project Index\n\n"
        "## Active\n\n"
        "| Date | Feature | Status | Sprint Backlog |\n"
        "|------|---------|--------|----------------|\n"
        "| 20260725 | audit | planned | [->](./20260725/audit/sprint-backlog.md) |\n",
    )
    write(tmp_path / "docs" / "20260725" / "audit" / "sprint-backlog.md", "# Sprint\n")
    write(
        tmp_path / "docs" / "adr" / "0001-example.md",
        "---\nstatus: accepted\n---\n\n# Example\n",
    )
    write(tmp_path / "docs" / "adr" / "0002-legacy.md", "# Legacy ADR Without Frontmatter\n")

    assert validate(tmp_path) == []
