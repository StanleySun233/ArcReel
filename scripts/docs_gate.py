from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWED_ADR_STATUSES = frozenset({"proposed", "accepted", "deprecated", "superseded"})
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*]\(([^)]+)\)")


def _display_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _target_exists(base_file: Path, raw_target: str) -> bool:
    target = raw_target.strip()
    if not target or target.startswith("#"):
        return True
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return True
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return True
    return (base_file.parent / target).resolve().exists()


def validate_docs_index(root: Path) -> list[str]:
    index = root / "docs" / "INDEX.md"
    if not index.exists():
        return ["docs/INDEX.md is missing"]

    errors: list[str] = []
    text = index.read_text(encoding="utf-8")
    for raw_target in MARKDOWN_LINK_RE.findall(text):
        if not _target_exists(index, raw_target):
            errors.append(f"docs/INDEX.md links to missing target {raw_target}")
    return errors


def validate_adr_statuses(root: Path) -> list[str]:
    adr_dir = root / "docs" / "adr"
    if not adr_dir.exists():
        return []

    errors: list[str] = []
    for path in sorted(adr_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---", 4)
        if end < 0:
            errors.append(f"{_display_path(path, root)} has unterminated frontmatter")
            continue
        frontmatter = text[4:end]
        status = None
        for line in frontmatter.splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() == "status":
                status = value.strip()
                break
        if status is None:
            errors.append(f"{_display_path(path, root)} frontmatter is missing status")
        elif status not in ALLOWED_ADR_STATUSES:
            errors.append(f"{_display_path(path, root)} has invalid ADR status {status}")
    return errors


def validate(root: Path) -> list[str]:
    root = root.resolve()
    return [
        *validate_docs_index(root),
        *validate_adr_statuses(root),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    errors = validate(Path(args.root))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
