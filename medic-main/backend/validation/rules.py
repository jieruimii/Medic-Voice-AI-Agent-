"""Twelve inspectable prototype rules, not a complete EMS standard."""
from dataclasses import dataclass, field as dc_field, asdict
from backend.domain.encounter import Encounter


@dataclass
class Issue:
    code: str
    severity: str
    field: str
    reason: str
    rule: str
    context: dict = dc_field(default_factory=dict)

    @property
    def blocking(self):
        return self.severity != "advisory"

    def serialize(self):
        return {**asdict(self), "blocking": self.blocking}


def validate(e: Encounter) -> list[Issue]:
    issues = []

    def add(rule, code, severity, key, reason, context=None):
        # Honest unknowns resolve contextual follow-up, but stay visible for review.
        if e.fact(key).explicitly_unknown and severity == "contextual":
            severity = "advisory"
            reason = "Medic explicitly left this unspecified; clinician review required."
        issues.append(Issue(code, severity, key, reason, rule, context or {}))

    def absent(key):
        f = e.fact(key)
        return not f.known and f.status not in ("uncertain", "conflicting")

    if e.value("transported") is True and absent("destination"):
        add("R01", "DESTINATION_MISSING", "required", "destination", "Transport destination is not documented.")
    if e.value("oxygen_given") is True and absent("oxygen_route"):
        add("R02", "OXYGEN_ROUTE_MISSING", "contextual", "oxygen_route", "Oxygen route is not documented.")
    if e.value("oxygen_given") is True:
        if absent("post_treatment_spo2") and absent("treatment_response"):
            key = "post_treatment_spo2" if e.fact("post_treatment_spo2").explicitly_unknown else "treatment_response"
            add("R03", "TREATMENT_RESPONSE_MISSING", "contextual", key,
                "No response or reassessment after oxygen is documented.",
                {"intervention": "oxygen", "flow": e.value("oxygen_flow_lpm"), "initial_spo2": e.value("spo2")})
    if e.value("transported") is True and absent("transport_justification"):
        add("R04", "TRANSPORT_JUSTIFICATION_MISSING", "contextual", "transport_justification",
            "The medic's transport rationale has not been documented.")
    medication_keys = {int(k.split(".")[1]) for k, f in e.facts.items()
                       if k.startswith("medications.") and (f.value is not None or f.explicitly_unknown)}
    if e.value("medications_given") is True and not medication_keys:
        add("R05", "MEDICATION_NAME_MISSING", "required", "medications.0.name",
            "Medication administration was reported without identifying the medication.")
    for i in sorted(medication_keys):
        prefix = f"medications.{i}."
        context = {"medication": e.value(prefix + "name"), "index": i}
        if absent(prefix + "name"):
            add("R05", "MEDICATION_NAME_MISSING", "required", prefix + "name", "An administered medication has no name.", context)
        if absent(prefix + "dose"):
            add("R06", "MEDICATION_DOSE_MISSING", "contextual", prefix + "dose", "Medication dose is not documented.", context)
        if absent(prefix + "route"):
            add("R07", "MEDICATION_ROUTE_MISSING", "contextual", prefix + "route", "Medication route is not documented.", context)
        # R03 applies to medication reassessment as well as oxygen.
        if absent(prefix + "response") and absent("treatment_response"):
            add("R03", "TREATMENT_RESPONSE_MISSING", "contextual", prefix + "response", "No response to medication is documented.", context)
        if e.value(prefix + "dose") is not None and absent(prefix + "units"):
            add("R06", "MEDICATION_UNITS_MISSING", "contextual", prefix + "units", "Medication dose units are not documented.", context)
    for key, fact in e.facts.items():
        if fact.status == "conflicting":
            add("R08", "CONFLICT_REQUIRES_RECONCILIATION", "required", key,
                "Conflicting statements require explicit reconciliation.", {"evidence": fact.evidence, "history": fact.history})
        elif fact.status == "uncertain":
            add("R09", "UNCERTAIN_VALUE_REQUIRES_CLARIFICATION", "contextual", key,
                "The stated value is uncertain; no exact value has been selected.")
    if e.value("transported") is True and absent("transport_priority"):
        add("R10", "TRANSPORT_PRIORITY_MISSING", "advisory", "transport_priority", "Transport priority is not documented.")
    if absent("chief_complaint"):
        add("R11", "CHIEF_COMPLAINT_MISSING", "required", "chief_complaint", "Chief complaint is not documented.")
    if any(e.value(k) is not None for k in ("mental_status", "spo2", "systolic_bp", "primary_impression")) and len(e.raw_narrative.split()) < 8:
        add("R12", "NARRATIVE_INCOMPLETE", "advisory", "raw_narrative", "The clinical assessment needs a meaningful supporting narrative.")
    return sorted(issues, key=priority)


def priority(issue: Issue):
    if issue.code == "CONFLICT_REQUIRES_RECONCILIATION":
        return 0
    if issue.severity == "required":
        return 1
    if issue.severity == "advisory":
        return 6
    if issue.code == "UNCERTAIN_VALUE_REQUIRES_CLARIFICATION":
        return 2
    if issue.code == "TRANSPORT_JUSTIFICATION_MISSING":
        return 4
    return 3
