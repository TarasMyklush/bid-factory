"""Response sections and which clause categories each one answers."""
from __future__ import annotations

SECTIONS: list[tuple[str, str, tuple[str, ...]]] = [
    ("company", "Company profile and eligibility",
     ("eligibility", "legal_registration", "financial", "local_content", "nationalisation")),
    ("solution", "Technical solution", ("technical_requirement", "data_residency", "security_compliance")),
    ("methodology", "Methodology and implementation plan", ("methodology",)),
    ("team", "Team and key personnel", ("team",)),
    ("experience", "Past performance", ("past_performance",)),
    ("certifications", "Certifications and accreditations", ("certification",)),
    ("service-levels", "Service levels and support", ("sla",)),
    ("commercial", "Commercial response", ("commercial", "contract_term")),
    ("forms", "Forms and declarations", ("form",)),
    ("general", "General", ("other",)),
]
SUBMISSION_CHECKLIST = "Submission checklist"

SECTION_FOR_CATEGORY: dict[str, str] = {cat: title for _, title, cats in SECTIONS for cat in cats}
SECTION_FOR_CATEGORY["submission_format"] = SUBMISSION_CHECKLIST
