"""Export the pinned OpenAPI schema for the public repository API contract."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import create_app

OUTPUT_PATH = Path("docs/openapi/repository-api-v1.json")


def main() -> None:
    """Generate the OpenAPI schema and write it to the committed artifact path."""
    schema = create_app().openapi()
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
