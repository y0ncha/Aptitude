"""Filesystem adapter for immutable artifact storage."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.core.ports import (
    ArtifactAlreadyExistsError,
    ArtifactStoreError,
    ArtifactStorePort,
    ArtifactWriteResult,
)


class FileSystemArtifactStore(ArtifactStorePort):
    """Persist immutable artifact and manifest snapshot in filesystem layout."""

    def __init__(self, *, root_dir: str) -> None:
        self._root_path = Path(root_dir).resolve()

    def store_immutable_artifact(
        self,
        *,
        skill_id: str,
        version: str,
        artifact_bytes: bytes,
        manifest_json: dict[str, Any],
    ) -> ArtifactWriteResult:
        relative_dir = Path("skills") / skill_id / version
        absolute_dir = self._root_path / relative_dir
        artifact_path = absolute_dir / "artifact.bin"
        manifest_path = absolute_dir / "manifest.json"

        if absolute_dir.exists():
            raise ArtifactAlreadyExistsError(
                f"Immutable artifact path already exists: {relative_dir.as_posix()}",
            )

        try:
            absolute_dir.mkdir(parents=True, exist_ok=False)
            with artifact_path.open("xb") as artifact_file:
                artifact_file.write(artifact_bytes)
            with manifest_path.open("x", encoding="utf-8") as manifest_file:
                json.dump(manifest_json, manifest_file, sort_keys=True)
                manifest_file.write("\n")
        except FileExistsError as exc:
            raise ArtifactAlreadyExistsError(
                f"Immutable artifact path already exists: {relative_dir.as_posix()}",
            ) from exc
        except OSError as exc:
            shutil.rmtree(absolute_dir, ignore_errors=True)
            raise ArtifactStoreError(
                f"Failed writing immutable artifact: {relative_dir.as_posix()}"
            ) from exc

        relative_artifact_path = (relative_dir / "artifact.bin").as_posix()
        return ArtifactWriteResult(
            relative_path=relative_artifact_path, size_bytes=len(artifact_bytes)
        )

    def read_artifact(self, *, relative_path: str) -> bytes:
        absolute_path = self._root_path / Path(relative_path)
        try:
            return absolute_path.read_bytes()
        except OSError as exc:
            raise ArtifactStoreError(f"Failed reading immutable artifact: {relative_path}") from exc
