#!/usr/bin/env python3
"""Extract values from the Home Visit AcroForm into a JSON hand-off file."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("dist/homevisit_form_manifest.json"))
    parser.add_argument("-o", "--output", type=Path, default=Path("dist/homevisit_data.json"))
    args = parser.parse_args()

    reader = PdfReader(str(args.pdf))
    fields = reader.get_fields() or {}
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    by_field = defaultdict(list)
    for item in manifest["fields"]:
        by_field[item["field"]].append(item["key"])

    flat = {}
    data = defaultdict(list)
    for field_name, field in fields.items():
        value = field.get("/V", "")
        if value in (None, "/Off"):
            value = False if field.get("/FT") == "/Btn" else ""
        elif isinstance(value, str) and value.startswith("/"):
            value = value[1:]
        flat[field_name] = value
        for key in by_field.get(field_name, [field_name]):
            data[key].append(value)

    result = {
        "source": args.pdf.name,
        "fields": flat,
        "by_data_key": {key: values[0] if len(values) == 1 else values for key, values in sorted(data.items())},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"fields": len(flat), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
