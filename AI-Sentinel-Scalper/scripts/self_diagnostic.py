#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
from pathlib import Path


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    files = [
        base / "src" / "guardian.py",
        base / "src" / "execution.py",
        base / "src" / "exchange_client.py",
        base / "dashboard.py",
    ]

    results = []
    ok = True
    for f in files:
        try:
            py_compile.compile(str(f), doraise=True)
            results.append({"file": str(f), "ok": True})
        except Exception as exc:  # noqa: BLE001
            ok = False
            results.append({"file": str(f), "ok": False, "error": str(exc)})

    status = "READY" if ok else "NOT_READY"
    payload = {"status": status, "checks": results}
    (base / "reports" / "self_diagnostic.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
