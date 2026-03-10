from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer


def build_pdf(source_path: Path, output_path: Path) -> None:
    styles = get_styles()
    story = []

    lines = source_path.read_text(encoding="utf-8").splitlines()
    bullet_buffer: list[str] = []
    numbered_buffer: list[str] = []

    def flush_bullets() -> None:
        nonlocal bullet_buffer
        if not bullet_buffer:
            return
        items = [
            ListItem(Paragraph(item, styles["BulletText"]))
            for item in bullet_buffer
        ]
        story.append(
            ListFlowable(
                items,
                bulletType="bullet",
                leftIndent=0.7 * cm,
                bulletFontName="Helvetica",
                bulletFontSize=10,
            )
        )
        story.append(Spacer(1, 0.18 * cm))
        bullet_buffer = []

    def flush_numbered() -> None:
        nonlocal numbered_buffer
        if not numbered_buffer:
            return
        items = [
            ListItem(Paragraph(item, styles["Body"]))
            for item in numbered_buffer
        ]
        story.append(
            ListFlowable(
                items,
                bulletType="1",
                leftIndent=0.7 * cm,
            )
        )
        story.append(Spacer(1, 0.18 * cm))
        numbered_buffer = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            flush_bullets()
            flush_numbered()
            story.append(Spacer(1, 0.18 * cm))
            continue

        if line.startswith("# "):
            flush_bullets()
            flush_numbered()
            story.append(Paragraph(line[2:].strip(), styles["DocTitle"]))
            story.append(Spacer(1, 0.35 * cm))
            continue

        if line.startswith("## "):
            flush_bullets()
            flush_numbered()
            story.append(Paragraph(line[3:].strip(), styles["DocHeading"]))
            story.append(Spacer(1, 0.2 * cm))
            continue

        if line.startswith("### "):
            flush_bullets()
            flush_numbered()
            story.append(Paragraph(line[4:].strip(), styles["DocSubheading"]))
            story.append(Spacer(1, 0.15 * cm))
            continue

        if line.startswith("- "):
            flush_numbered()
            bullet_buffer.append(_escape(line[2:].strip()))
            continue

        if _is_numbered_item(line):
            flush_bullets()
            numbered_buffer.append(_escape(_strip_number_prefix(line)))
            continue

        flush_bullets()
        flush_numbered()
        story.append(Paragraph(_escape(line), styles["Body"]))
        story.append(Spacer(1, 0.14 * cm))

    flush_bullets()
    flush_numbered()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title="Matt - Project Overview and MVP",
        author="Codex",
    )
    doc.build(story)


def get_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="DocTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=HexColor("#0F172A"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=HexColor("#1D4ED8"),
            spaceBefore=6,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocSubheading",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=HexColor("#0F172A"),
            spaceBefore=4,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.2,
            leading=14,
            alignment=TA_JUSTIFY,
            textColor=HexColor("#111827"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletText",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.2,
            leading=13.5,
            textColor=HexColor("#111827"),
        )
    )
    return styles


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _is_numbered_item(line: str) -> bool:
    parts = line.split(".", 1)
    return len(parts) == 2 and parts[0].isdigit()


def _strip_number_prefix(line: str) -> str:
    return line.split(".", 1)[1].strip()


def main() -> int:
    base_dir = Path(__file__).resolve().parents[1]
    source_path = base_dir / "docs" / "projeto-e-mvp.md"
    output_path = base_dir / "docs" / "projeto-e-mvp.pdf"

    if len(sys.argv) > 1:
        source_path = Path(sys.argv[1]).resolve()
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2]).resolve()

    build_pdf(source_path, output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
