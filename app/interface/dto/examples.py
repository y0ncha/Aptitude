"""Shared OpenAPI request and response examples for the public API."""

from __future__ import annotations

PUBLISH_REQUEST_EXAMPLE = {
    "slug": "python.lint",
    "version": "1.2.3",
    "content": {
        "raw_markdown": "# Python Lint\n\nLint Python files consistently.\n",
        "rendered_summary": "Lint Python files consistently.",
    },
    "metadata": {
        "name": "Python Lint",
        "description": "Linting skill",
        "tags": ["python", "lint"],
        "headers": {"runtime": "python"},
        "inputs_schema": {"type": "object"},
        "outputs_schema": {"type": "object"},
        "token_estimate": 128,
        "maturity_score": 0.9,
        "security_score": 0.95,
    },
    "governance": {
        "trust_tier": "internal",
        "provenance": {
            "repo_url": "https://github.com/example/skills",
            "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
            "tree_path": "skills/python.lint",
        },
    },
    "relationships": {
        "depends_on": [
            {
                "slug": "python.base",
                "version_constraint": ">=1.0.0,<2.0.0",
                "optional": True,
                "markers": ["linux", "gpu"],
            }
        ],
        "extends": [{"slug": "python.base", "version": "1.0.0"}],
        "conflicts_with": [],
        "overlaps_with": [{"slug": "python.format", "version": "1.0.0"}],
    },
}

CHECKSUM_EXAMPLE = {
    "algorithm": "sha256",
    "digest": "c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2",
}

SKILL_VERSION_RESPONSE_EXAMPLE = {
    "slug": "python.lint",
    "version": "1.2.3",
    "version_checksum": CHECKSUM_EXAMPLE,
    "content": {
        "checksum": CHECKSUM_EXAMPLE,
        "size_bytes": 123,
        "rendered_summary": "Lint Python files consistently.",
    },
    "metadata": {
        "name": "Python Lint",
        "description": "Linting skill",
        "tags": ["python", "lint"],
        "headers": {"runtime": "python"},
        "inputs_schema": {"type": "object"},
        "outputs_schema": {"type": "object"},
        "token_estimate": 128,
        "maturity_score": 0.9,
        "security_score": 0.95,
    },
    "lifecycle_status": "published",
    "trust_tier": "internal",
    "provenance": {
        "repo_url": "https://github.com/example/skills",
        "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
        "tree_path": "skills/python.lint",
    },
    "relationships": {
        "depends_on": [
            {
                "selector": {
                    "slug": "python.base",
                    "version_constraint": ">=1.0.0,<2.0.0",
                    "optional": True,
                    "markers": ["linux", "gpu"],
                },
                "target_version": None,
            }
        ],
        "extends": [
            {
                "selector": {"slug": "python.base", "version": "1.0.0", "markers": []},
                "target_version": {
                    "slug": "python.base",
                    "version": "1.0.0",
                    "name": "Python Base",
                    "description": "Base runtime skill",
                    "tags": ["python", "runtime"],
                    "lifecycle_status": "published",
                    "trust_tier": "verified",
                    "published_at": "2026-03-01T08:30:00Z",
                },
            }
        ],
        "conflicts_with": [],
        "overlaps_with": [
            {
                "selector": {"slug": "python.format", "version": "1.0.0", "markers": []},
                "target_version": None,
            }
        ],
    },
    "published_at": "2026-03-10T08:30:00Z",
    "content_download_path": "/skills/python.lint/versions/1.2.3/content",
}

SKILL_IDENTITY_SUCCESS_EXAMPLE = {
    "slug": "python.lint",
    "status": "published",
    "current_version": {
        "version": "1.2.3",
        "lifecycle_status": "published",
        "trust_tier": "internal",
        "published_at": "2026-03-10T08:30:00Z",
    },
    "created_at": "2026-02-10T08:30:00Z",
    "updated_at": "2026-03-10T08:30:00Z",
}

LIST_SUCCESS_EXAMPLE = {
    "slug": "python.lint",
    "versions": [
        {
            "slug": "python.lint",
            "version": "1.2.3",
            "version_checksum": CHECKSUM_EXAMPLE,
            "content": {
                "checksum": CHECKSUM_EXAMPLE,
                "size_bytes": 123,
                "rendered_summary": "Lint Python files consistently.",
            },
            "metadata": {
                "name": "Python Lint",
                "description": "Linting skill",
                "tags": ["python", "lint"],
            },
            "lifecycle_status": "published",
            "trust_tier": "internal",
            "published_at": "2026-03-10T08:30:00Z",
        }
    ],
}

SEARCH_SUCCESS_EXAMPLE = {
    "results": [
        {
            "slug": "python.lint",
            "version": "1.2.3",
            "name": "Python Lint",
            "description": "Linting skill",
            "tags": ["python", "lint"],
            "lifecycle_status": "published",
            "trust_tier": "internal",
            "published_at": "2026-03-10T08:30:00Z",
            "freshness_days": 0,
            "content_size_bytes": 123,
            "usage_count": 0,
            "matched_fields": ["name", "tags"],
            "matched_tags": ["python"],
            "reasons": ["text_match", "tag_filter_match"],
        }
    ]
}

RELATIONSHIP_BATCH_SUCCESS_EXAMPLE = {
    "results": [
        {
            "status": "found",
            "coordinate": {"slug": "python.lint", "version": "1.2.3"},
            "relationships": [
                {
                    "edge_type": "depends_on",
                    "selector": {
                        "slug": "python.base",
                        "version_constraint": ">=1.0.0,<2.0.0",
                        "optional": True,
                        "markers": ["linux", "gpu"],
                    },
                    "target_version": None,
                },
                {
                    "edge_type": "extends",
                    "selector": {"slug": "python.base", "version": "1.0.0", "markers": []},
                    "target_version": {
                        "slug": "python.base",
                        "version": "1.0.0",
                        "name": "Python Base",
                        "description": "Base runtime skill",
                        "tags": ["python", "runtime"],
                        "lifecycle_status": "published",
                        "trust_tier": "verified",
                        "published_at": "2026-03-01T08:30:00Z",
                    },
                },
            ],
        },
        {
            "status": "not_found",
            "coordinate": {"slug": "python.missing", "version": "9.9.9"},
            "relationships": None,
        },
    ]
}

INVALID_REQUEST_ERROR_EXAMPLE = {
    "error": {
        "code": "INVALID_REQUEST",
        "message": "Request validation failed.",
        "details": {
            "errors": [
                {
                    "type": "string_pattern_mismatch",
                    "loc": ["path", "version"],
                    "msg": "String should match pattern",
                    "input": "latest",
                }
            ]
        },
    }
}

SEARCH_INVALID_REQUEST_ERROR_EXAMPLE = {
    "error": {
        "code": "INVALID_REQUEST",
        "message": "Search request validation failed.",
        "details": {
            "errors": [
                {
                    "type": "value_error",
                    "loc": [],
                    "msg": "Value error, At least one search selector must be provided.",
                    "input": {
                        "q": None,
                        "tags": [],
                        "language": None,
                        "fresh_within_days": None,
                        "max_content_size_bytes": None,
                        "status": [],
                        "trust_tier": [],
                        "limit": 20,
                    },
                }
            ]
        },
    }
}

DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE = {
    "error": {
        "code": "DUPLICATE_SKILL_VERSION",
        "message": "Skill version already exists: python.lint@1.2.3",
        "details": {"slug": "python.lint", "version": "1.2.3"},
    }
}

SKILL_NOT_FOUND_ERROR_EXAMPLE = {
    "error": {
        "code": "SKILL_NOT_FOUND",
        "message": "Skill not found: python.lint",
        "details": {"slug": "python.lint"},
    }
}

SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE = {
    "error": {
        "code": "SKILL_VERSION_NOT_FOUND",
        "message": "Skill version not found: python.lint@9.9.9",
        "details": {"slug": "python.lint", "version": "9.9.9"},
    }
}

CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE = {
    "error": {
        "code": "CONTENT_STORAGE_FAILURE",
        "message": "Failed to persist immutable skill version.",
    }
}

SKILL_VERSION_STATUS_RESPONSE_EXAMPLE = {
    "slug": "python.lint",
    "version": "1.2.3",
    "status": "deprecated",
    "trust_tier": "internal",
    "lifecycle_changed_at": "2026-03-11T09:15:00Z",
    "is_current_default": True,
}
