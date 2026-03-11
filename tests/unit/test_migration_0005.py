"""Unit coverage for migration helper behavior in revision 0005."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0005_normalized_skill_storage_api_cleanup.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0005", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration_module()


@pytest.mark.unit
def test_read_legacy_markdown_reads_existing_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_path = artifact_root / "skills/demo/1.0.0/content.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("# Demo\n", encoding="utf-8")
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(artifact_root))

    result = MIGRATION._read_legacy_markdown(
        relative_path="skills/demo/1.0.0/content.md",
        manifest={},
        skill_id="demo",
        version="1.0.0",
    )

    assert result == "# Demo\n"


@pytest.mark.unit
def test_read_legacy_markdown_builds_placeholder_when_artifact_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("ARTIFACT_ROOT_DIR", str(tmp_path / "artifacts"))

    result = MIGRATION._read_legacy_markdown(
        relative_path="skills/demo/1.0.0/content.md",
        manifest={
            "name": "Demo Skill",
            "description": "Generated from manifest metadata.",
            "tags": ["Python", "Lint"],
        },
        skill_id="demo",
        version="1.0.0",
    )

    assert result == (
        "# Demo Skill\n\n"
        "Generated from manifest metadata.\n\n"
        "Tags: Python, Lint\n\n"
        "> Original markdown artifact was unavailable during migration.\n"
        "> Legacy artifact reference: `skills/demo/1.0.0/content.md`.\n"
        "> Skill version: `demo@1.0.0`.\n"
    )
