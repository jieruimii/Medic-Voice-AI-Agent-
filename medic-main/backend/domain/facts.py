"""Medic is the authority for facts; each update keeps its source."""
from typing import Literal, Any
import re
from pydantic import BaseModel, Field, ConfigDict

FIELDS = {
    "age": "number", "sex": "text", "dispatch_reason": "text",
    "chief_complaint": "text", "symptom_onset": "text", "mental_status": "text",
    "primary_impression": "text", "systolic_bp": "number", "diastolic_bp": "number",
    "heart_rate": "number", "spo2": "number", "spo2_context": "text",
    "oxygen_given": "boolean", "oxygen_flow_lpm": "number", "oxygen_route": "text",
    "post_treatment_spo2": "number", "treatment_response": "text",
    "transported": "boolean", "destination": "text", "transport_priority": "text",
    "transport_justification": "text", "medications_given": "boolean",
}
for index in range(5):
    for key in ("name", "dose", "units", "route", "response"):
        FIELDS[f"medications.{index}.{key}"] = "number" if key == "dose" else "text"


def equivalent(field, left, right):
    if not isinstance(left, str) or not isinstance(right, str):
        if type(left) in (int,float) and type(right) in (int,float):
            return left == right
        return type(left) is type(right) and left == right
    normalize = lambda v: re.sub(r"[^\w ]", "", v.casefold()).strip()
    a, b = normalize(left), normalize(right)
    if a == b:
        return True
    # Literal language synonyms, not clinical conclusions. No numeric equivalence.
    aliases = {
        "chief_complaint": [{"difficulty breathing", "shortness of breath", "short of breath", "dyspnea"}],
        "oxygen_route": [{"nasal cannula", "nc"}],
    }
    return any(a in group and b in group for group in aliases.get(field, []))


NUMBER_WORDS = dict(zip(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
NUMBER_WORDS.update(dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20,100,10))))


def numeric_mentions(text):
    """Ground numbers in digit or spoken-cardinal source evidence."""
    values={float(n) for n in re.findall(r'(?<!\w)-?\d+(?:\.\d+)?',text)}
    words=re.findall(r'[a-z]+',text.casefold())
    groups=[]
    group=[]
    for word in words+['END']:
        if word in NUMBER_WORDS or word in ('hundred','thousand','and','point'):
            group.append(word)
        elif group:
            groups.append(group)
            group=[]
    for group in groups:
        meaningful=[w for w in group if w!='and']
        if not meaningful:
            continue
        total=current=0
        try:
            if 'point' in meaningful:
                split=meaningful.index('point')
                left=meaningful[:split]
                right=meaningful[split+1:]
                if all(w in NUMBER_WORDS and NUMBER_WORDS[w]<10 for w in right):
                    number=sum(NUMBER_WORDS[w] for w in left)
                    values.add(float(str(number)+'.'+''.join(str(NUMBER_WORDS[w]) for w in right)))
                continue
            for word in meaningful:
                if word=='hundred':
                    current=max(current,1)*100
                elif word=='thousand':
                    total+=max(current,1)*1000
                    current=0
                else:
                    current+=NUMBER_WORDS[word]
            values.add(float(total+current))
            # Common spoken vitals: 'one forty eight' / 'one twelve'.
            if (len(meaningful)>=2 and meaningful[0] in NUMBER_WORDS
                    and 0<NUMBER_WORDS[meaningful[0]]<10
                    and all(w in NUMBER_WORDS for w in meaningful[1:])):
                values.add(float(NUMBER_WORDS[meaningful[0]]*100+sum(NUMBER_WORDS[w] for w in meaningful[1:])))
        except (KeyError,ValueError):
            pass
    return values


class Update(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    value: str | int | float | bool | None
    status: Literal["confirmed", "uncertain", "missing"] = "confirmed"
    evidence: str
    operation: Literal["assert", "correct", "unknown", "reconcile"] = "assert"


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    updates: list[Update] = Field(default_factory=list)


class Fact(BaseModel):
    value: Any = None
    status: Literal["confirmed", "uncertain", "conflicting", "missing"] = "missing"
    source: str = "medic"
    evidence: str = ""
    turn_id: str = ""
    explicitly_unknown: bool = False
    history: list[dict] = Field(default_factory=list)

    @property
    def known(self):
        return self.status == "confirmed" and self.value is not None


def valid_update(update: Update, text: str) -> bool:
    """Reject malformed updates and claims with no literal caller evidence."""
    if update.field not in FIELDS or not update.evidence.strip():
        return False
    if update.evidence.casefold() not in text.casefold():
        return False
    if update.operation == "unknown":
        return update.value is None
    if update.status in ("uncertain", "missing"):
        # Textual hedges remain verbatim. Numeric uncertainty never selects an exact value.
        return update.value is None or (update.status == 'uncertain' and FIELDS[update.field] == 'text'
                                        and isinstance(update.value, str) and bool(update.value.strip()))
    kind = FIELDS[update.field]
    if kind == "boolean":
        return type(update.value) is bool
    if kind == "number":
        return type(update.value) in (int, float) and float(update.value) in numeric_mentions(update.evidence)
    return isinstance(update.value, str) and bool(update.value.strip())
