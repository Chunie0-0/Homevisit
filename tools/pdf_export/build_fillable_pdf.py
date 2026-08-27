#!/usr/bin/env python3
"""Build a computer-fillable PDF from the HTML print view and field manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

A4_W, A4_H = 595.2756, 841.8898


def add_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--base", type=Path, default=Path("dist/homevisit_form_base.pdf"))
    p.add_argument("--manifest", type=Path, default=Path("dist/homevisit_form_manifest.json"))
    p.add_argument("--output", type=Path, default=Path("dist/homevisit_form_fillable.pdf"))
    return p.parse_args()


def pdf_rect(field: dict, manifest: dict) -> tuple[float, float, float, float, int]:
    r = field["labelRect"] if field["type"] in {"checkbox", "radio"} else field["rect"]
    scale_x = A4_W / manifest["cssPageWidth"]
    scale_y = A4_H / manifest["cssPageHeight"]
    x = r["x"] * scale_x
    y_top = r["y"] * scale_y
    w = max(r["width"] * scale_x, 12)
    h = max(r["height"] * scale_y, 14)
    page_no = int(y_top // A4_H)
    y = A4_H - (y_top - page_no * A4_H) - h
    return x, y, w, h, page_no


def main() -> None:
    args = add_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    reader = PdfReader(str(args.base))
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # ReportLab AcroForm widgets accept only the standard PDF 14 fonts.
    # The static HTML background still renders Thai correctly in Chromium;
    # text entered into widgets should therefore be Latin/number-safe here.
    font_name = "Helvetica"

    overlays = []
    for page_no in range(len(reader.pages)):
        overlay_path = args.output.with_name(f"._overlay_{page_no}.pdf")
        c = canvas.Canvas(str(overlay_path), pagesize=(A4_W, A4_H))
        form = c.acroForm
        for field in manifest["fields"]:
            x, y, w, h, target_page = pdf_rect(field, manifest)
            if target_page != page_no:
                continue
            typ = field["type"]
            if typ == "checkbox":
                # Cover the visible tick box, while keeping the label text readable.
                size = min(max(h * 0.72, 11), 16)
                form.checkbox(
                    name=field["field"], x=x + 2, y=y + (h - size) / 2,
                    size=size, checked=field["checked"], buttonStyle="check",
                    borderWidth=0, borderColor=None, fillColor=None,
                    textColor=None, forceBorder=False,
                )
            elif typ == "radio":
                group = f"{field['key'].replace('.', '_')}_radio"
                form.radio(
                    name=group, value=field["value"] or "option",
                    selected=field["checked"], x=x + 2, y=y + (h - 13) / 2,
                    buttonStyle="circle", size=13, borderWidth=0,
                    borderColor=None, fillColor=None, textColor=None,
                    forceBorder=False,
                )
            elif typ == "select":
                form.choice(
                    name=field["field"], value=field["value"], options=[],
                    x=x, y=y, width=w, height=h, borderWidth=0,
                    fillColor=None, textColor=None, fontName=font_name,
                    fontSize=8,
                )
            else:
                form.textfield(
                    name=field["field"], value=field["value"], x=x, y=y,
                    width=w, height=h, borderWidth=0, fillColor=None,
                    textColor=None, fontName=font_name, fontSize=8,
                    forceBorder=False, fieldFlags="multiline" if typ == "textarea" else "",
                )
        c.showPage()
        c.save()
        overlays.append(overlay_path)

    writer = PdfWriter()
    field_refs = []
    for index, page in enumerate(reader.pages):
        overlay_reader = PdfReader(str(overlays[index]))
        writer.add_page(page)
        for annotation in overlay_reader.pages[0].get("/Annots", []):
            added = writer.add_annotation(index, annotation.get_object())
            field_refs.append(added.indirect_reference)
    # Copy the AcroForm catalog from the first overlay after its widgets have
    # been copied to the output pages.
    overlay_reader = PdfReader(str(overlays[0]))
    acroform = overlay_reader.root_object.get("/AcroForm")
    if acroform:
        copied_acroform = acroform.get_object()
        copied_acroform[NameObject("/Fields")] = ArrayObject(field_refs)
        writer._root_object[NameObject("/AcroForm")] = writer._add_object(copied_acroform)
        writer.set_need_appearances_writer()
    with args.output.open("wb") as stream:
        writer.write(stream)
    for overlay_path in overlays:
        overlay_path.unlink(missing_ok=True)
    print(json.dumps({"pages": len(reader.pages), "fields": len(manifest["fields"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
