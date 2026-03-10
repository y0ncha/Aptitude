"""Shared OpenAPI request and response examples for the public API."""

from __future__ import annotations

import json

PUBLISH_MANIFEST_EXAMPLE = {
    "schema_version": "1.0",
    "skill_id": "python.lint",
    "version": "1.2.3",
    "name": "Python Lint",
    "description": "Linting skill",
    "tags": ["python", "lint"],
    "depends_on": [
        {
            "skill_id": "python.base",
            "version_constraint": ">=1.0.0,<2.0.0",
            "optional": True,
            "markers": ["linux", "gpu"],
        }
    ],
    "extends": [{"skill_id": "python.base", "version": "1.0.0"}],
    "conflicts_with": [],
    "overlaps_with": [],
}

PUBLISH_MULTIPART_FORM_EXAMPLE = {
    "manifest": json.dumps(PUBLISH_MANIFEST_EXAMPLE),
    "artifact": "(binary artifact upload)",
}

PUBLISH_SUCCESS_EXAMPLE = {
    "skill_id": "python.lint",
    "version": "1.2.3",
    "manifest": PUBLISH_MANIFEST_EXAMPLE,
    "checksum": {
        "algorithm": "sha256",
        "digest": "c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2",
    },
    "artifact_metadata": {
        "relative_path": "python.lint/1.2.3/artifact.bin",
        "size_bytes": 123,
    },
    "published_at": "2026-03-10T08:30:00Z",
}

FETCH_SUCCESS_EXAMPLE = {
    **PUBLISH_SUCCESS_EXAMPLE,
    "artifact_base64": "YmluYXJ5LWFydGlmYWN0",
}

LIST_SUCCESS_EXAMPLE = {
    "skill_id": "python.lint",
    "versions": [
        {
            "skill_id": "python.lint",
            "version": "1.2.3",
            "manifest": PUBLISH_MANIFEST_EXAMPLE,
            "checksum": PUBLISH_SUCCESS_EXAMPLE["checksum"],
            "artifact_metadata": PUBLISH_SUCCESS_EXAMPLE["artifact_metadata"],
            "published_at": "2026-03-10T08:30:00Z",
        },
        {
            "skill_id": "python.lint",
            "version": "1.0.0",
            "manifest": {
                **PUBLISH_MANIFEST_EXAMPLE,
                "version": "1.0.0",
                "depends_on": [],
                "extends": [],
            },
            "checksum": {
                "algorithm": "sha256",
                "digest": "2d711642b726b04401627ca9fbac32f5da7e5a3d4f2e9ce1d49f6b2e5f3b1f9d",
            },
            "artifact_metadata": {
                "relative_path": "python.lint/1.0.0/artifact.bin",
                "size_bytes": 98,
            },
            "published_at": "2026-02-10T08:30:00Z",
        },
    ],
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

INVALID_MANIFEST_ERROR_EXAMPLE = {
    "error": {
        "code": "INVALID_MANIFEST",
        "message": "Manifest validation failed.",
        "details": {
            "errors": [
                {
                    "type": "json_invalid",
                    "loc": [],
                    "msg": "Invalid JSON: expected value at line 1 column 1",
                    "input": "not-json",
                }
            ]
        },
    }
}

DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE = {
    "error": {
        "code": "DUPLICATE_SKILL_VERSION",
        "message": "Skill version already exists: python.lint@1.2.3",
        "details": {"skill_id": "python.lint", "version": "1.2.3"},
    }
}

SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE = {
    "error": {
        "code": "SKILL_VERSION_NOT_FOUND",
        "message": "Skill version not found: python.lint@9.9.9",
        "details": {"skill_id": "python.lint", "version": "9.9.9"},
    }
}

INTEGRITY_CHECK_FAILED_ERROR_EXAMPLE = {
    "error": {
        "code": "INTEGRITY_CHECK_FAILED",
        "message": "Integrity check failed for skill version: python.lint@1.2.3",
        "details": {"skill_id": "python.lint", "version": "1.2.3"},
    }
}

ARTIFACT_STORAGE_FAILURE_ERROR_EXAMPLE = {
    "error": {
        "code": "ARTIFACT_STORAGE_FAILURE",
        "message": "Artifact storage failed during publish.",
    }
}
