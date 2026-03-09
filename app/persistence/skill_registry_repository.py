"""SQLAlchemy adapters for immutable skill catalog persistence ports."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.ports import (
    ChecksumExpectation,
    SkillRegistryPersistenceError,
    SkillRegistryPort,
    StoredSkillVersion,
    StoredSkillVersionSummary,
)
from app.core.skill_registry import DuplicateSkillVersionError
from app.persistence.models.skill import Skill
from app.persistence.models.skill_relationship_edge import SkillRelationshipEdge
from app.persistence.models.skill_version import SkillVersion
from app.persistence.models.skill_version_checksum import SkillVersionChecksum

_RELATIONSHIP_TYPES = ("depends_on", "extends")


class SQLAlchemySkillRegistryRepository(SkillRegistryPort):
    """SQLAlchemy implementation for immutable skill catalog persistence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def version_exists(self, *, skill_id: str, version: str) -> bool:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion.id)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .where(Skill.skill_id == skill_id, SkillVersion.version == version)
                .limit(1)
            )
            return session.execute(statement).scalar_one_or_none() is not None

    def create_version(
        self,
        *,
        manifest_json: dict[str, Any],
        artifact_relative_path: str,
        artifact_size_bytes: int,
        checksum: ChecksumExpectation,
    ) -> StoredSkillVersion:
        skill_id = str(manifest_json["skill_id"])
        version = str(manifest_json["version"])

        with self._session_factory() as session:
            try:
                skill = self._get_or_create_skill(session=session, skill_id=skill_id)
                skill_version = SkillVersion(
                    skill_fk=skill.id,
                    version=version,
                    manifest_json=manifest_json,
                    artifact_rel_path=artifact_relative_path,
                    artifact_size_bytes=artifact_size_bytes,
                )
                session.add(skill_version)
                session.flush()

                session.add_all(
                    _build_relationship_edges(
                        source_skill_version_id=skill_version.id,
                        manifest_json=manifest_json,
                    )
                )

                checksum_row = SkillVersionChecksum(
                    skill_version_fk=skill_version.id,
                    algorithm=checksum.algorithm,
                    digest=checksum.digest,
                )
                session.add(checksum_row)
                session.commit()

                session.refresh(skill_version)
                session.refresh(checksum_row)
                return _to_stored_skill_version(skill_version=skill_version, checksum=checksum_row)
            except IntegrityError as exc:
                session.rollback()
                if _is_duplicate_skill_version_error(exc):
                    raise DuplicateSkillVersionError(skill_id=skill_id, version=version) from exc
                raise SkillRegistryPersistenceError(
                    "Failed to persist immutable skill version."
                ) from exc
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError(
                    "Failed to persist immutable skill version."
                ) from exc

    def get_version(self, *, skill_id: str, version: str) -> StoredSkillVersion | None:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion, SkillVersionChecksum)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .join(
                    SkillVersionChecksum,
                    SkillVersionChecksum.skill_version_fk == SkillVersion.id,
                )
                .where(Skill.skill_id == skill_id, SkillVersion.version == version)
            )
            row = session.execute(statement).one_or_none()
            if row is None:
                return None

            skill_version, checksum = row
            return _to_stored_skill_version(skill_version=skill_version, checksum=checksum)

    def list_versions(self, *, skill_id: str) -> tuple[StoredSkillVersionSummary, ...]:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion, SkillVersionChecksum)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .join(
                    SkillVersionChecksum,
                    SkillVersionChecksum.skill_version_fk == SkillVersion.id,
                )
                .where(Skill.skill_id == skill_id)
                .order_by(SkillVersion.published_at.desc(), SkillVersion.id.desc())
            )
            rows = session.execute(statement).all()
            return tuple(
                StoredSkillVersionSummary(
                    skill_id=skill_id,
                    version=skill_version.version,
                    manifest_json=_ensure_manifest_dict(skill_version.manifest_json),
                    artifact_relative_path=skill_version.artifact_rel_path,
                    artifact_size_bytes=skill_version.artifact_size_bytes,
                    checksum_algorithm=checksum.algorithm,
                    checksum_digest=checksum.digest,
                    published_at=skill_version.published_at,
                )
                for skill_version, checksum in rows
            )

    @staticmethod
    def _get_or_create_skill(*, session: Session, skill_id: str) -> Skill:
        existing = session.execute(
            select(Skill).where(Skill.skill_id == skill_id),
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        created = Skill(skill_id=skill_id)
        session.add(created)
        session.flush()
        return created


def _to_stored_skill_version(
    *,
    skill_version: SkillVersion,
    checksum: SkillVersionChecksum,
) -> StoredSkillVersion:
    return StoredSkillVersion(
        skill_id=str(skill_version.manifest_json["skill_id"]),
        version=skill_version.version,
        manifest_json=_ensure_manifest_dict(skill_version.manifest_json),
        artifact_relative_path=skill_version.artifact_rel_path,
        artifact_size_bytes=skill_version.artifact_size_bytes,
        checksum_algorithm=checksum.algorithm,
        checksum_digest=checksum.digest,
        published_at=_ensure_datetime(skill_version.published_at),
    )


def _build_relationship_edges(
    *,
    source_skill_version_id: int,
    manifest_json: dict[str, Any],
) -> tuple[SkillRelationshipEdge, ...]:
    relationships: set[tuple[str, str, str]] = set()
    for edge_type in _RELATIONSHIP_TYPES:
        raw_entries = manifest_json.get(edge_type)
        if not isinstance(raw_entries, list):
            continue
        for item in raw_entries:
            if not isinstance(item, dict):
                continue
            target_skill_id = item.get("skill_id")
            target_version_selector = _extract_target_version_selector(
                edge_type=edge_type,
                item=item,
            )
            if not isinstance(target_skill_id, str) or not isinstance(target_version_selector, str):
                continue
            if not target_skill_id or not target_version_selector:
                continue
            relationships.add((edge_type, target_skill_id, target_version_selector))

    return tuple(
        SkillRelationshipEdge(
            source_skill_version_fk=source_skill_version_id,
            edge_type=edge_type,
            target_skill_id=target_skill_id,
            target_version_selector=target_version_selector,
        )
        for edge_type, target_skill_id, target_version_selector in sorted(relationships)
    )


def _extract_target_version_selector(*, edge_type: str, item: dict[str, Any]) -> str | None:
    raw_version = item.get("version")
    if isinstance(raw_version, str):
        return raw_version

    if edge_type != "depends_on":
        return None

    raw_constraint = item.get("version_constraint")
    if isinstance(raw_constraint, str):
        return raw_constraint

    return None


def _is_duplicate_skill_version_error(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return (
        "uq_skill_versions_skill_fk_version" in message
        or "unique constraint" in message
        or "duplicate key value" in message
    )


def _ensure_manifest_dict(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    raise SkillRegistryPersistenceError("Skill manifest payload is not a dictionary.")


def _ensure_datetime(value: datetime | None) -> datetime:
    if value is None:
        raise SkillRegistryPersistenceError("Published timestamp is missing.")
    return value
