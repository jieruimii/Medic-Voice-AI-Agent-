from dataclasses import dataclass
from backend.validation.rules import Issue


@dataclass
class Question:
    code: str
    field: str
    text: str


def plan(issue: Issue, encounter) -> Question:
    code, key = issue.code, issue.field
    label = key.replace("_", " ")
    med = issue.context.get("medication") or "medication"
    if code == "CONFLICT_REQUIRES_RECONCILIATION":
        if key == "medications_given":
            names = [f.value for k, f in encounter.facts.items() if k.endswith(".name") and f.value]
            text = f"Just to make sure I have this right — you mentioned giving {' and '.join(names) or 'medication'} earlier, but later gave a different account. Were any medications given, and which should I document?"
        else:
            fact = encounter.fact(key)
            prior = fact.history[-1].get("value") if fact.history else "a different value"
            text = f"You mentioned {prior} for {label} earlier, and then {fact.value}. Which should I document?"
    elif code == "UNCERTAIN_VALUE_REQUIRES_CLARIFICATION":
        subject = "second saturation" if key == "post_treatment_spo2" else label
        text = f"Do you remember the exact {subject}, or should I leave it unspecified?"
        if key == 'transport_justification':
            text = "Is there anything more specific you can document about the transport rationale, or should I leave it unspecified?"
    elif code == "TREATMENT_RESPONSE_MISSING":
        if issue.context.get("intervention") == "oxygen":
            flow = encounter.value("oxygen_flow_lpm")
            amount = "four liters" if flow == 4 else f"{flow:g} liters" if flow else "oxygen"
            text = f"What happened to the patient's oxygen saturation after you put them on {amount}?"
        else:
            text = f"How did the patient respond after the {med}?"
    else:
        text = {
            "DESTINATION_MISSING": "Where did you transport the patient?",
            "OXYGEN_ROUTE_MISSING": "How was the oxygen delivered?",
            "TRANSPORT_JUSTIFICATION_MISSING": "What about the patient's condition, if anything, made another form of transportation inappropriate?",
            "MEDICATION_NAME_MISSING": "Which medication was given?",
            "MEDICATION_DOSE_MISSING": f"What dose of {med} was given?",
            "MEDICATION_UNITS_MISSING": f"What units was that dose of {med} measured in?",
            "MEDICATION_ROUTE_MISSING": f"How was the {med} given?",
            "CHIEF_COMPLAINT_MISSING": "What was the patient's chief complaint?",
        }.get(code, f"What can you tell me about {label}?")
    return Question(code, key, text)
