"""SQLAlchemy adapters for normalized skill catalog persistence ports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select, text, tuple_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

from app.core.governance import LifecycleStatus, TrustTier
from app.core.ports import (
    CreateSkillVersionRecord,
    ExactSkillCoordinate,
    RelationshipSelectorRecordInput,
    SearchCandidatesRequest,
    SkillRegistryPersistenceError,
    SkillRegistryPort,
    SkillRelationshipReadPort,
    SkillSearchPort,
    SkillVersionReadPort,
    StoredSkillIdentity,
    StoredSkillRelationshipSource,
    StoredSkillSearchCandidate,
    StoredSkillVersion,
    StoredSkillVersionContent,
    StoredSkillVersionStatus,
    StoredSkillVersionSummary,
)
from app.core.skill_registry import DuplicateSkillVersionError
from app.persistence.models.skill import Skill
from app.persistence.models.skill_content import SkillContent
from app.persistence.models.skill_dependency import SkillDependency
from app.persistence.models.skill_metadata import SkillMetadata
from app.persistence.models.skill_relationship_selector import SkillRelationshipSelector
from app.persistence.models.skill_search_document import SkillSearchDocument
from app.persistence.models.skill_version import SkillVersion
from app.persistence.skill_registry_repository_support import (
    SEARCH_CANDIDATES_SQL,
    build_contains_pattern,
    build_search_document,
    ensure_datetime,
    ensure_string_list,
    is_duplicate_skill_version_error,
    sort_relationship_selectors,
    to_stored_selector,
    to_stored_skill_version,
    to_stored_skill_version_summary,
)


class SQLAlchemySkillRegistryRepository(
    SkillRegistryPort,
    SkillVersionReadPort,
    SkillSearchPort,
    SkillRelationshipReadPort,
):
    """SQLAlchemy implementation for normalized immutable skill persistence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def version_exists(self, *, slug: str, version: str) -> bool:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion.id)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .where(Skill.slug == slug, SkillVersion.version == version)
                .limit(1)
            )
            return session.execute(statement).scalar_one_or_none() is not None

    def create_version(self, *, record: CreateSkillVersionRecord) -> StoredSkillVersion:
        with self._session_factory() as session:
            try:
                skill = self._get_or_create_skill(session=session, slug=record.slug)
                content = self._get_or_create_content(session=session, record=record)
                metadata = SkillMetadata(
                    name=record.metadata.name,
                    description=record.metadata.description,
                    tags=list(record.metadata.tags),
                    headers=record.metadata.headers,
                    inputs_schema=record.metadata.inputs_schema,
                    outputs_schema=record.metadata.outputs_schema,
                    token_estimate=record.metadata.token_estimate,
                    maturity_score=record.metadata.maturity_score,
                    security_score=record.metadata.security_score,
                )
                session.add(metadata)
                session.flush()

                skill_version = SkillVersion(
                    skill_fk=skill.id,
                    version=record.version,
                    content_fk=content.id,
                    metadata_fk=metadata.id,
                    checksum_digest=record.version_checksum_digest,
                    lifecycle_status="published",
                    lifecycle_changed_at=datetime.now(UTC),
                    trust_tier=record.governance.trust_tier,
                    provenance_repo_url=(
                        None
                        if record.governance.provenance is None
                        else record.governance.provenance.repo_url
                    ),
                    provenance_commit_sha=(
                        None
                        if record.governance.provenance is None
                        else record.governance.provenance.commit_sha
                    ),
                    provenance_tree_path=(
                        None
                        if record.governance.provenance is None
                        else record.governance.provenance.tree_path
                    ),
                )
                session.add(skill_version)
                session.flush()
                session.refresh(
                    skill_version,
                    attribute_names=["published_at", "created_at", "lifecycle_changed_at"],
                )

                selector_rows = [
                    SkillRelationshipSelector(
                        source_skill_version_fk=skill_version.id,
                        edge_type=item.edge_type,
                        ordinal=item.ordinal,
                        target_slug=item.slug,
                        target_version=item.version,
                        version_constraint=item.version_constraint,
                        optional=item.optional,
                        markers=list(item.markers),
                    )
                    for item in record.relationships
                ]
                session.add_all(selector_rows)
                session.flush()

                self._create_exact_dependencies(
                    session=session,
                    source_version_id=skill_version.id,
                    relationships=record.relationships,
                )
                session.add(
                    build_search_document(
                        skill_version_id=skill_version.id,
                        slug=record.slug,
                        version=record.version,
                        metadata=record.metadata,
                        governance=record.governance,
                        published_at=skill_version.published_at,
                        content_size_bytes=record.content.size_bytes,
                    )
                )

                skill.current_version_id = skill_version.id
                session.commit()

                reloaded = self._get_version_entity(
                    session=session, slug=record.slug, version=record.version
                )
                if reloaded is None:
                    raise SkillRegistryPersistenceError(
                        "Created skill version could not be reloaded."
                    )
                return to_stored_skill_version(reloaded)
            except IntegrityError as exc:
                session.rollback()
                if is_duplicate_skill_version_error(exc):
                    raise DuplicateSkillVersionError(
                        slug=record.slug,
                        version=record.version,
                    ) from exc
                raise SkillRegistryPersistenceError(
                    "Failed to persist immutable skill version."
                ) from exc
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError(
                    "Failed to persist immutable skill version."
                ) from exc

    def get_skill(self, *, slug: str) -> StoredSkillIdentity | None:
        with self._session_factory() as session:
            current_version = SkillVersion
            statement = (
                select(
                    Skill,
                    current_version.version,
                )
                .outerjoin(current_version, current_version.id == Skill.current_version_id)
                .where(Skill.slug == slug)
            )
            row = session.execute(statement).one_or_none()
            if row is None:
                return None

            skill, version = row
            return StoredSkillIdentity(
                slug=skill.slug,
                current_version=cast(str | None, version),
                created_at=skill.created_at,
                updated_at=skill.updated_at,
            )

    def get_version(self, *, slug: str, version: str) -> StoredSkillVersion | None:
        with self._session_factory() as session:
            entity = self._get_version_entity(session=session, slug=slug, version=version)
            if entity is None:
                return None
            return to_stored_skill_version(entity)

    def get_version_content(self, *, slug: str, version: str) -> StoredSkillVersionContent | None:
        with self._session_factory() as session:
            entity = self._get_version_entity(session=session, slug=slug, version=version)
            if entity is None:
                return None
            return StoredSkillVersionContent(
                slug=entity.skill.slug,
                version=entity.version,
                raw_markdown=entity.content.raw_markdown,
                checksum_digest=entity.content.checksum_digest,
                size_bytes=entity.content.storage_size_bytes,
                lifecycle_status=cast(LifecycleStatus, entity.lifecycle_status),
                trust_tier=cast(TrustTier, entity.trust_tier),
            )

    def get_version_summaries_batch(
        self,
        *,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[StoredSkillVersionSummary, ...]:
        if not coordinates:
            return ()

        coordinate_pairs = [(item.slug, item.version) for item in coordinates]
        with self._session_factory() as session:
            statement = (
                select(SkillVersion)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .options(
                    joinedload(SkillVersion.skill),
                    joinedload(SkillVersion.content),
                    joinedload(SkillVersion.metadata_row),
                )
                .where(tuple_(Skill.slug, SkillVersion.version).in_(coordinate_pairs))
            )
            rows = session.execute(statement).scalars().all()
            return tuple(to_stored_skill_version_summary(item) for item in rows)

    def list_versions(self, *, slug: str) -> tuple[StoredSkillVersionSummary, ...]:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .options(
                    joinedload(SkillVersion.skill),
                    joinedload(SkillVersion.content),
                    joinedload(SkillVersion.metadata_row),
                )
                .where(Skill.slug == slug)
                .order_by(SkillVersion.published_at.desc(), SkillVersion.id.desc())
            )
            rows = session.execute(statement).scalars().all()
            return tuple(to_stored_skill_version_summary(item) for item in rows)

    def get_relationship_sources_batch(
        self,
        *,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[StoredSkillRelationshipSource, ...]:
        if not coordinates:
            return ()

        coordinate_pairs = [(item.slug, item.version) for item in coordinates]
        with self._session_factory() as session:
            statement = (
                select(SkillVersion)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .options(
                    joinedload(SkillVersion.skill),
                    selectinload(SkillVersion.relationship_selectors),
                )
                .where(tuple_(Skill.slug, SkillVersion.version).in_(coordinate_pairs))
            )
            rows = session.execute(statement).scalars().all()
            return tuple(
                StoredSkillRelationshipSource(
                    slug=item.skill.slug,
                    version=item.version,
                    lifecycle_status=cast(LifecycleStatus, item.lifecycle_status),
                    trust_tier=cast(TrustTier, item.trust_tier),
                    relationships=tuple(
                        to_stored_selector(selector)
                        for selector in sort_relationship_selectors(item.relationship_selectors)
                    ),
                )
                for item in rows
            )

    def search_candidates(
        self,
        *,
        request: SearchCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        published_after = None
        if request.fresh_within_days is not None:
            published_after = datetime.now(UTC) - timedelta(days=request.fresh_within_days)

        with self._session_factory() as session:
            rows = session.execute(
                SEARCH_CANDIDATES_SQL,
                {
                    "query_text": request.query_text,
                    "query_contains_pattern": build_contains_pattern(request.query_text),
                    "required_tags": list(request.required_tags),
                    "required_tag_count": len(request.required_tags),
                    "published_after": published_after,
                    "max_content_size_bytes": request.max_content_size_bytes,
                    "lifecycle_statuses": list(request.lifecycle_statuses),
                    "trust_tiers": list(request.trust_tiers),
                    "limit": request.limit,
                },
            ).mappings()
            return tuple(
                StoredSkillSearchCandidate(
                    slug=str(row["slug"]),
                    version=str(row["version"]),
                    name=str(row["name"]),
                    description=str(row["description"]) if row["description"] is not None else None,
                    tags=tuple(ensure_string_list(row["tags"])),
                    lifecycle_status=cast(LifecycleStatus, str(row["lifecycle_status"])),
                    trust_tier=cast(TrustTier, str(row["trust_tier"])),
                    published_at=ensure_datetime(row["published_at"]),
                    content_size_bytes=int(row["content_size_bytes"]),
                    usage_count=int(row["usage_count"]),
                    exact_slug_match=bool(row["exact_slug_match"]),
                    exact_name_match=bool(row["exact_name_match"]),
                    lexical_score=float(row["lexical_score"]),
                    tag_overlap_count=int(row["tag_overlap_count"]),
                )
                for row in rows
            )

    def update_version_status(
        self,
        *,
        slug: str,
        version: str,
        lifecycle_status: LifecycleStatus,
    ) -> StoredSkillVersionStatus | None:
        with self._session_factory() as session:
            try:
                entity = self._get_version_entity(session=session, slug=slug, version=version)
                if entity is None:
                    return None
                entity.lifecycle_status = lifecycle_status
                entity.lifecycle_changed_at = datetime.now(UTC)
                session.add(entity)
                session.flush()

                search_document = session.get(SkillSearchDocument, entity.id)
                if search_document is not None:
                    search_document.lifecycle_status = lifecycle_status
                    session.add(search_document)

                skill = session.get(Skill, entity.skill_fk)
                if skill is None:
                    raise SkillRegistryPersistenceError("Skill identity is missing.")
                skill.current_version_id = self._select_current_version_id(
                    session=session,
                    skill_id=entity.skill_fk,
                )
                session.flush()
                session.commit()

                return StoredSkillVersionStatus(
                    slug=slug,
                    version=version,
                    lifecycle_status=cast(LifecycleStatus, entity.lifecycle_status),
                    trust_tier=cast(TrustTier, entity.trust_tier),
                    lifecycle_changed_at=entity.lifecycle_changed_at,
                    is_current_default=skill.current_version_id == entity.id,
                )
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError(
                    "Failed to update immutable skill version status."
                ) from exc

    @staticmethod
    def _get_or_create_skill(*, session: Session, slug: str) -> Skill:
        existing = session.execute(select(Skill).where(Skill.slug == slug)).scalar_one_or_none()
        if existing is not None:
            return existing

        created = Skill(slug=slug)
        session.add(created)
        session.flush()
        return created

    @staticmethod
    def _get_or_create_content(
        *,
        session: Session,
        record: CreateSkillVersionRecord,
    ) -> SkillContent:
        existing = session.execute(
            select(SkillContent).where(
                SkillContent.checksum_digest == record.content.checksum_digest
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        created = SkillContent(
            raw_markdown=record.content.raw_markdown,
            rendered_summary=record.content.rendered_summary,
            storage_size_bytes=record.content.size_bytes,
            checksum_digest=record.content.checksum_digest,
        )
        session.add(created)
        session.flush()
        return created

    @staticmethod
    def _create_exact_dependencies(
        *,
        session: Session,
        source_version_id: int,
        relationships: tuple[RelationshipSelectorRecordInput, ...],
    ) -> None:
        for relationship in relationships:
            if relationship.version is None:
                continue
            target = session.execute(
                select(SkillVersion.id)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .where(
                    Skill.slug == relationship.slug,
                    SkillVersion.version == relationship.version,
                )
            ).scalar_one_or_none()
            if target is None:
                continue
            session.add(
                SkillDependency(
                    from_version_fk=source_version_id,
                    to_version_fk=target,
                    constraint_type=relationship.edge_type,
                    version_constraint=relationship.version_constraint,
                )
            )

    @staticmethod
    def _select_current_version_id(*, session: Session, skill_id: int) -> int | None:
        return session.execute(
            select(SkillVersion.id)
            .where(
                SkillVersion.skill_fk == skill_id,
                SkillVersion.lifecycle_status.in_(("published", "deprecated")),
            )
            .order_by(
                text(
                    "CASE skill_versions.lifecycle_status "
                    "WHEN 'published' THEN 0 WHEN 'deprecated' THEN 1 ELSE 2 END"
                ),
                SkillVersion.published_at.desc(),
                SkillVersion.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    @staticmethod
    def _get_version_entity(
        *,
        session: Session,
        slug: str,
        version: str,
    ) -> SkillVersion | None:
        statement = (
            select(SkillVersion)
            .join(Skill, Skill.id == SkillVersion.skill_fk)
            .options(
                joinedload(SkillVersion.skill),
                joinedload(SkillVersion.content),
                joinedload(SkillVersion.metadata_row),
                selectinload(SkillVersion.relationship_selectors),
            )
            .where(Skill.slug == slug, SkillVersion.version == version)
        )
        return session.execute(statement).scalar_one_or_none()
