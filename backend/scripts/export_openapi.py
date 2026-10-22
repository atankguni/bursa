"""
Print the API's OpenAPI document (JSON) to stdout.

The frontend's API types (frontend/src/api/schema.gen.ts) are generated from
it: `make api-types` at the repo root. Run with BURSA_ENV_FILE="" so local
settings don't leak into the document.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app  # noqa: E402

if __name__ == "__main__":
    json.dump(app.openapi(), sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
