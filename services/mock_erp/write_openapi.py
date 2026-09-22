"""Write the mock ERP's OpenAPI document to services/mock_erp/openapi.json.

    python -m services.mock_erp.write_openapi

The same document the server shows at /docs, saved as a file: for
anyone who cannot open /docs (a Colab runtime has no browser on
localhost) and for tools that generate clients or MCP tools from it.
tests/test_mock_erp.py fails if the file and the app disagree - rerun
this after any change to models.py or main.py.
"""

import json
from pathlib import Path

from .main import create_app

OUT = Path(__file__).resolve().parent / "openapi.json"


def main():
    spec = create_app(api_key="").openapi()
    OUT.write_bytes((json.dumps(spec, indent=1, ensure_ascii=True) + "\n").encode("ascii"))
    print(f"wrote {OUT} ({len(spec['paths'])} paths)")


if __name__ == "__main__":
    main()
