"""CLI tool to export OpenAPI JSON schema from the FastAPI application."""

import json
import sys
from pathlib import Path

from app.main import app


def export_openapi(output_path: str) -> None:
    schema = app.openapi()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"OpenAPI schema successfully written to {output_path}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    export_openapi(target)

