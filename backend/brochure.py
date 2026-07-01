"""
brochure.py
-----------
Generates a one-page summary "brochure" PDF for a given policy, built
from the structured data we parsed out of the master spreadsheet.

The source spreadsheet does not include actual insurer brochure PDFs, so
this module produces a clean, readable PDF summary on demand (and caches
it to disk) so the product still has a genuine "View Brochure" experience
for every policy. Each generated PDF carries a disclaimer pointing users
to the insurer's official document for legal/binding terms.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

BROCHURE_DIR = os.path.join(os.path.dirname(__file__), "brochures")
os.makedirs(BROCHURE_DIR, exist_ok=True)

PRIMARY = colors.HexColor("#2563eb")
MUTED = colors.HexColor("#64748b")
GREEN = colors.HexColor("#16a34a")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("BrochTitle", parent=ss["Title"], textColor=PRIMARY, fontSize=20))
    ss.add(ParagraphStyle("BrochSub", parent=ss["Normal"], textColor=MUTED, fontSize=11))
    ss.add(ParagraphStyle("SectionHead", parent=ss["Heading2"], textColor=PRIMARY, fontSize=13, spaceBefore=14))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=10, leading=14))
    ss.add(ParagraphStyle("Disclaimer", parent=ss["Normal"], fontSize=8, textColor=MUTED))
    return ss


def _flag_row(label, value):
    pretty = {"yes": "Included", "no": "Not Included", "unknown": "Not Specified"}.get(value, value)
    return [label, pretty]


def brochure_path(policy_id):
    return os.path.join(BROCHURE_DIR, f"{policy_id}.pdf")


def generate_brochure(policy):
    path = brochure_path(policy["id"])
    if os.path.exists(path):
        return path

    ss = _styles()
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        topMargin=20 * mm, bottomMargin=15 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )
    story = []

    story.append(Paragraph(policy["policy_name"], ss["BrochTitle"]))
    sub = policy["insurance_company"]
    if policy.get("policy_variant"):
        sub += f" &nbsp;|&nbsp; Variant: {policy['policy_variant']}"
    story.append(Paragraph(sub, ss["BrochSub"]))
    story.append(HRFlowable(width="100%", color=PRIMARY, thickness=1, spaceBefore=8, spaceAfter=12))

    if policy.get("best_for"):
        story.append(Paragraph(f"<b>Best for:</b> {policy['best_for']}", ss["Body"]))
        story.append(Spacer(1, 8))

    # Key facts table
    key_facts = [
        ["Policy Type", policy.get("policy_type") or "N/A"],
        ["Sum Insured", policy.get("sum_insured_raw") or "N/A"],
        ["Indicative Premium", policy.get("premium_raw") or "Refer insurer rate chart"],
        ["Premium Frequency", policy.get("premium_frequency") or "N/A"],
        ["Entry Age", f"{int(policy['min_age'])} - {int(policy['max_age'])} years"],
        ["Renewal", policy.get("renewal_age_raw") or "N/A"],
        ["Pre-existing Disease Wait", policy.get("ped_waiting_period_raw") or "N/A"],
        ["Room Rent", policy.get("room_rent_limit_raw") or "N/A"],
        ["Cashless Hospitals", policy.get("cashless_hospital_count_raw") or "N/A"],
        ["Rating", f"{policy.get('rating', 'N/A')} / 5"],
    ]
    t = Table(key_facts, colWidths=[55 * mm, 105 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)

    story.append(Paragraph("Coverage Highlights", ss["SectionHead"]))
    coverage_rows = [
        _flag_row("OPD Cover", policy.get("opd_cover")),
        _flag_row("Maternity Cover", policy.get("maternity_cover")),
        _flag_row("Critical Illness Cover", policy.get("critical_illness_cover")),
        _flag_row("Accident Cover", policy.get("accident_cover")),
        _flag_row("AYUSH / Alt. Treatment", policy.get("ayush_cover")),
        _flag_row("Mental Illness Cover", policy.get("mental_illness_cover")),
        _flag_row("International Treatment", policy.get("international_cover")),
        _flag_row("Annual Health Checkup", policy.get("annual_health_checkup")),
        _flag_row("Chronic Disease Care", policy.get("chronic_care_cover")),
        _flag_row("No-Claim Bonus", policy.get("no_claim_bonus")),
        _flag_row("Restoration Benefit", policy.get("restoration_benefit")),
        _flag_row("Co-pay Applicable", policy.get("co_pay")),
        _flag_row("Deductible Applicable", policy.get("deductible")),
        _flag_row("Ambulance Cover", policy.get("ambulance_cover")),
        _flag_row("Daycare Treatments", policy.get("daycare_treatments")),
        _flag_row("Organ Donor Cover", policy.get("organ_donor_cover")),
        _flag_row("Domiciliary Treatment", policy.get("domiciliary_treatment")),
    ]
    ct = Table(coverage_rows, colWidths=[80 * mm, 80 * mm])
    ct.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("TEXTCOLOR", (1, 0), (1, -1), GREEN),
    ]))
    story.append(ct)

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#e2e8f0"), thickness=0.6))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Disclaimer: This is an auto-generated summary brochure created from publicly "
        "available policy information for comparison purposes only. It is not an "
        "official insurer document and does not constitute a policy contract. Please "
        "refer to the insurer's official prospectus/policy wording, available on the "
        "insurer's website, before purchasing.",
        ss["Disclaimer"]
    ))

    doc.build(story)
    return path
