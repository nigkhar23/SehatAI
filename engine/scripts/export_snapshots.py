"""Export static UI snapshots — the bulletproof-deploy data layer.

Dumps the exact /assess, /personas, /portfolio and /validation payloads the API
serves into JSON files the Next.js app bundles. The Vercel demo then renders a
fully working card+portfolio with ZERO backend dependency (a dead API link can't
kill the demo — the build plan's "dead link is worse than fewer features" rule).
The live FastAPI backend remains the source of truth for Round 2 / the "real API"
story; these snapshots are the frozen-persona demo path.

Run after any engine/weights/narration change:
  python scripts/export_snapshots.py
Writes -> web/lib/data/{personas,portfolio,validation}.json and
          web/lib/data/assess/{ID}.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from sehat.api import app

OUT = Path(__file__).resolve().parent.parent.parent / "web" / "lib" / "data"


def _write(rel: str, payload) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {path.relative_to(OUT.parent.parent)}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)

    personas = client.get("/personas").json()
    _write("personas.json", personas)
    _write("portfolio.json", client.get("/portfolio").json())
    _write("validation.json", client.get("/validation").json())

    for p in personas["personas"]:
        eid = p["id"]
        _write(f"assess/{eid}.json", client.get(f"/assess/{eid}").json())

    print(f"\nSnapshots exported -> {OUT}")
    print("The web app reads these statically; the live API is an enhancement.")


if __name__ == "__main__":
    main()
