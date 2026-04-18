"""audit_export/views.py — ISO 45001 Evidence Pack generator."""
import io
import zipfile
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse

from .pdf_sections import (
    generate_cover,
    generate_section_01_org,
    generate_section_02_hira,
    generate_section_03_compliance,
    generate_section_04_training,
    generate_section_05_operations,
    generate_section_06_inspections,
    generate_section_07_performance,
    generate_section_08_incidents,
    generate_section_09_actions,
)


@login_required
def audit_export_view(request):
    today = date.today()
    default_from = date(today.year - 1, today.month, today.day)

    if request.method == "GET":
        return render(request, "audit_export/generate.html", {
            "from_date": default_from.isoformat(),
            "to_date":   today.isoformat(),
        })

    # POST — build the pack
    try:
        from_date = date.fromisoformat(request.POST.get("from_date", ""))
        to_date   = date.fromisoformat(request.POST.get("to_date",   ""))
    except ValueError:
        from_date, to_date = default_from, today

    org = request.organization

    SECTIONS = [
        ("00_Master_Index.pdf",         generate_cover),
        ("01_Clause4_Organisation.pdf", generate_section_01_org),
        ("02_Clause6_HIRA.pdf",         generate_section_02_hira),
        ("03_Clause6_Compliance.pdf",   generate_section_03_compliance),
        ("04_Clause7_Training.pdf",     generate_section_04_training),
        ("05_Clause8_Operations.pdf",   generate_section_05_operations),
        ("06_Clause9_Inspections.pdf",  generate_section_06_inspections),
        ("07_Clause9_Performance.pdf",  generate_section_07_performance),
        ("08_Clause10_Incidents.pdf",   generate_section_08_incidents),
        ("09_Clause10_Actions.pdf",     generate_section_09_actions),
    ]

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, generator in SECTIONS:
            try:
                pdf_bytes = generator(org, from_date, to_date)
                zf.writestr(filename, pdf_bytes)
            except Exception as exc:
                zf.writestr(filename, _error_pdf(filename, exc))

    zip_buf.seek(0)
    safe = "".join(c for c in org.name if c.isalnum() or c in " _-")[:25].strip().replace(" ", "_")
    dl_name = f"ISO45001_Pack_{safe}_{to_date.isoformat()}.zip"
    response = HttpResponse(zip_buf.read(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{dl_name}"'
    return response


def _error_pdf(section_name: str, exc: Exception) -> bytes:
    """Return a minimal PDF stub when a section generator fails."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    story = [
        Spacer(1, 50),
        Paragraph(
            f"Error generating: {section_name}",
            ParagraphStyle("e", fontSize=12, textColor=colors.red, fontName="Helvetica-Bold"),
        ),
        Spacer(1, 10),
        Paragraph(
            str(exc),
            ParagraphStyle("em", fontSize=9, textColor=colors.grey),
        ),
    ]
    doc.build(story)
    buf.seek(0)
    return buf.read()
