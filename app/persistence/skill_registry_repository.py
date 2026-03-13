"""SQLAlchemy adapters for normalized skill catalog persistence ports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import BigInteger, DateTime, Integer, Text, bindparam, select, text, tuple_
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

from app.core.governance import LifecycleStatus, ProvenanceMetadata, TrustTier
from app.core.ports import (
    CreateSkillVersionRecord,
    ExactSkillCoordinate,
    GovernanceRecordInput,
    MetadataRecordInput,
    RelationshipEdgeType,
    RelationshipSelectorRecordInput,
    SearchCandidatesRequest,
    SkillRegistryPersistenceError,
    SkillRegistryPort,
    SkillRelationshipReadPort,
    SkillSearchPort,
    SkillVersionReadPort,
    StoredRelationshipSelector,
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

_RELATIONSHIP_EDGE_ORDER: dict[RelationshipEdgeType, int] = {
    "depends_on": 0,
    "extends": 1,
    "conflicts_with": 2,
    "overlaps_with": 3,
}

_SEARCH_CANDIDATES_SQL = text(
    """
    WITH filtered AS (
        SELECT
            doc.skill_version_fk,
            doc.slug,
            doc.version,
            doc.name,
            doc.description,
            doc.tags,
            doc.lifecycle_status,
            doc.trust_tier,
            doc.published_at,
            doc.content_size_bytes,
            doc.usage_count,
            CASE
                WHEN :query_text IS NOT NULL AND doc.normalized_slug = :query_text THEN TRUE
                ELSE FALSE
            END AS exact_slug_match,
            CASE
                WHEN :query_text IS NOT NULL AND doc.normalized_name = :query_text THEN TRUE
                ELSE FALSE
            END AS exact_name_match,
            CASE
                WHEN :query_text IS NOT NULL THEN ts_rank_cd(
                    doc.search_vector,
                    plainto_tsquery('simple'::regconfig, :query_text)
                )
                ELSE 0.0
            END AS lexical_score,
            CASE
                WHEN :required_tag_count > 0 THEN (
                    SELECT COUNT(*)
                    FROM unnest(doc.normalized_tags) AS tag
                    WHERE tag = ANY(:required_tags)
                )
                ELSE 0
            END AS tag_overlap_count
        FROM skill_search_documents AS doc
        WHERE (
            :query_text IS NULL
            OR doc.search_vector @@ plainto_tsquery('simple'::regconfig, :query_text)
            OR doc.normalized_slug = :query_text
            OR doc.normalized_name = :query_text
            OR (
                :query_contains_pattern IS NOT NULL
                AND (
                    doc.normalized_slug LIKE :query_contains_pattern ESCAPE '\\'
                    OR doc.normalized_name LIKE :query_contains_pattern ESCAPE '\\'
                )
            )
        )
          AND (
            :required_tag_count = 0
            OR doc.normalized_tags @> :required_tags
          )
          AND (
            :published_after IS NULL
            OR doc.published_at >= :published_after
          )
          AND (
            :max_content_size_bytes IS NULL
            OR doc.content_size_bytes <= :max_content_size_bytes
          )
          AND doc.lifecycle_status = ANY(:lifecycle_statuses)
          AND doc.trust_tier = ANY(:trust_tiers)
    ),
    ranked AS (
        SELECT
            filtered.*,
            ROW_NUMBER() OVER (
                PARTITION BY filtered.slug
                ORDER BY
                    filtered.exact_slug_match DESC,
                    filtered.exact_name_match DESC,
                    filtered.lexical_score DESC,
                    filtered.tag_overlap_count DESC,
                    filtered.usage_count DESC,
                    filtered.published_at DESC,
                    filtered.content_size_bytes ASC,
                    filtered.slug ASC,
                    filtered.skill_version_fk DESC
            ) AS skill_rank
        FROM filtered
    )
    SELECT
        skill_version_fk,
        slug,
        version,
        name,
        description,
        tags,
        lifecycle_status,
        trust_tier,
        published_at,
        content_size_bytes,
        usage_count,
        exact_slug_match,
        exact_name_match,
        lexical_score,
        tag_overlap_count
    FROM ranked
    WHERE skill_rank = 1
    ORDER BY
        exact_slug_match DESC,
        exact_name_match DESC,
        lexical_score DESC,
        tag_overlap_count DESC,
        usage_count DESC,
        published_at DESC,
        content_size_bytes ASC,
        slug ASC,
        skill_version_fk DESC
    LIMIT :limit
    """
).bindparams(
    bindparam("query_text", type_=Text()),
    bindparam("query_contains_pattern", type_=Text()),
    bindparam("required_tags", type_=ARRAY(Text())),
    bindparam("required_tag_count", type_=Integer()),
    bindparam("published_after", type_=DateTime(timezone=True)),
    bindparam("max_content_size_bytes", type_=BigInteger()),
    bindparam("lifecycle_statuses", type_=ARRAY(Text())),
    bindparam("trust_tiers", type_=ARRAY(Text())),
    bindparam("limit", type_=Integer()),
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
                    _build_search_document(
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
                return _to_stored_skill_version(reloaded)
            except IntegrityError as exc:
                session.rollback()
                if _is_duplicate_skill_version_error(exc):
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
                    current_version.published_at,
                    current_version.lifecycle_status,
                    current_version.trust_tier,
                )
                .outerjoin(current_version, current_version.id == Skill.current_version_id)
                .where(Skill.slug == slug)
            )
            row = session.execute(statement).one_or_none()
            if row is None:
                return None

            skill, version, published_at, lifecycle_status, trust_tier = row
            return StoredSkillIdentity(
                slug=skill.slug,
                status=cast(LifecycleStatus, lifecycle_status or "published"),
                current_version=cast(str | None, version),
                current_version_published_at=published_at,
                current_version_status=cast(LifecycleStatus | None, lifecycle_status),
                current_version_trust_tier=cast(TrustTier | None, trust_tier),
                created_at=skill.created_at,
                updated_at=skill.updated_at,
            )

    def get_version(self, *, slug: str, version: str) -> StoredSkillVersion | None:
        with self._session_factory() as session:
            entity = self._get_version_entity(session=session, slug=slug, version=version)
            if entity is None:
                return None
            return _to_stored_skill_version(entity)

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
                published_at=entity.published_at,
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
            return tuple(_to_stored_skill_version_summary(item) for item in rows)

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
            return tuple(_to_stored_skill_version_summary(item) for item in rows)

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
                        _to_stored_selector(selector)
                        for selector in _sort_relationship_selectors(item.relationship_selectors)
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
                _SEARCH_CANDIDATES_SQL,
                {
                    "query_text": request.query_text,
                    "query_contains_pattern": _build_contains_pattern(request.query_text),
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
                    skill_version_fk=int(row["skill_version_fk"]),
                    slug=str(row["slug"]),
                    version=str(row["version"]),
                    name=str(row["name"]),
                    description=str(row["description"]) if row["description"] is not None else None,
                    tags=tuple(_ensure_string_list(row["tags"])),
                    lifecycle_status=cast(LifecycleStatus, str(row["lifecycle_status"])),
                    trust_tier=cast(TrustTier, str(row["trust_tier"])),
                    published_at=_ensure_datetime(row["published_at"]),
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


def _to_stored_selector(selector: SkillRelationshipSelector) -> StoredRelationshipSelector:
    return StoredRelationshipSelector(
        edge_type=cast(RelationshipEdgeType, selector.edge_type),
        ordinal=selector.ordinal,
        slug=selector.target_slug,
        version=selector.target_version,
        version_constraint=selector.version_constraint,
        optional=selector.optional,
        markers=tuple(selector.markers),
    )


def _to_stored_skill_version(entity: SkillVersion) -> StoredSkillVersion:
    return StoredSkillVersion(
        slug=entity.skill.slug,
        version=entity.version,
        version_checksum_digest=entity.checksum_digest,
        content_checksum_digest=entity.content.checksum_digest,
        content_size_bytes=entity.content.storage_size_bytes,
        rendered_summary=entity.content.rendered_summary,
        name=entity.metadata_row.name,
        description=entity.metadata_row.description,
        tags=tuple(entity.metadata_row.tags),
        headers=entity.metadata_row.headers,
        inputs_schema=entity.metadata_row.inputs_schema,
        outputs_schema=entity.metadata_row.outputs_schema,
        token_estimate=entity.metadata_row.token_estimate,
        maturity_score=entity.metadata_row.maturity_score,
        security_score=entity.metadata_row.security_score,
        lifecycle_status=cast(LifecycleStatus, entity.lifecycle_status),
        trust_tier=cast(TrustTier, entity.trust_tier),
        provenance=_to_provenance(entity),
        lifecycle_changed_at=entity.lifecycle_changed_at,
        published_at=entity.published_at,
        relationships=tuple(
            _to_stored_selector(selector)
            for selector in _sort_relationship_selectors(entity.relationship_selectors)
        ),
    )


def _to_stored_skill_version_summary(entity: SkillVersion) -> StoredSkillVersionSummary:
    return StoredSkillVersionSummary(
        slug=entity.skill.slug,
        version=entity.version,
        version_checksum_digest=entity.checksum_digest,
        content_checksum_digest=entity.content.checksum_digest,
        content_size_bytes=entity.content.storage_size_bytes,
        rendered_summary=entity.content.rendered_summary,
        name=entity.metadata_row.name,
        description=entity.metadata_row.description,
        tags=tuple(entity.metadata_row.tags),
        lifecycle_status=cast(LifecycleStatus, entity.lifecycle_status),
        trust_tier=cast(TrustTier, entity.trust_tier),
        published_at=entity.published_at,
    )


def _sort_relationship_selectors(
    selectors: list[SkillRelationshipSelector],
) -> list[SkillRelationshipSelector]:
    return sorted(
        selectors,
        key=lambda row: (
            _RELATIONSHIP_EDGE_ORDER[cast(RelationshipEdgeType, row.edge_type)],
            row.ordinal,
        ),
    )


def _build_search_document(
    *,
    skill_version_id: int,
    slug: str,
    version: str,
    metadata: MetadataRecordInput,
    governance: GovernanceRecordInput,
    published_at: datetime | None,
    content_size_bytes: int,
) -> SkillSearchDocument:
    return SkillSearchDocument(
        skill_version_fk=skill_version_id,
        slug=slug,
        normalized_slug=_normalize_text(slug),
        version=version,
        name=metadata.name,
        normalized_name=_normalize_text(metadata.name),
        description=metadata.description,
        tags=list(metadata.tags),
        normalized_tags=sorted({_normalize_text(tag) for tag in metadata.tags if tag.strip()}),
        lifecycle_status="published",
        trust_tier=governance.trust_tier,
        published_at=_ensure_datetime(published_at),
        content_size_bytes=content_size_bytes,
        usage_count=0,
    )


def _is_duplicate_skill_version_error(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return (
        "uq_skill_versions_skill_fk_version" in message
        or "unique constraint" in message
        or "duplicate key value" in message
    )


def _ensure_string_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        raise SkillRegistryPersistenceError("Expected a list of strings.")
    if not all(isinstance(item, str) for item in raw):
        raise SkillRegistryPersistenceError("Expected a list of strings.")
    return [str(item) for item in raw]


def _ensure_datetime(value: datetime | None) -> datetime:
    if value is None:
        raise SkillRegistryPersistenceError("Published timestamp is missing.")
    return value


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def _build_contains_pattern(value: str | None) -> str | None:
    if value is None:
        return None
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _to_provenance(entity: SkillVersion) -> ProvenanceMetadata | None:
    if entity.provenance_repo_url is None or entity.provenance_commit_sha is None:
        return None
    return ProvenanceMetadata(
        repo_url=entity.provenance_repo_url,
        commit_sha=entity.provenance_commit_sha,
        tree_path=entity.provenance_tree_path,
    )
