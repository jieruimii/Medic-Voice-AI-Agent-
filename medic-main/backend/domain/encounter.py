from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field
from .facts import Fact, Update, valid_update, equivalent


class Encounter(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8].upper())
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    facts: dict[str, Fact] = Field(default_factory=dict)
    raw_narrative: str = ""
    encounter_status: str = "waiting"
    unresolved_issues: list[dict] = Field(default_factory=list)

    def fact(self, key: str) -> Fact:
        return self.facts.get(key, Fact())

    def value(self, key: str):
        f = self.fact(key)
        return f.value if f.known else None

    def apply(self, update: Update, text: str, turn_id: str) -> bool:
        if not valid_update(update, text):
            return False
        old = self.facts.get(update.field)
        unknown = update.operation == "unknown"
        status = "missing" if unknown else update.status
        history = list(old.history) if old else []
        if old:
            if (equivalent(update.field, old.value, update.value) and old.status == status
                    and old.explicitly_unknown == unknown):
                return True
            entry = old.model_dump(exclude={"history"})
            entry["status"] = "superseded" if update.operation in ("correct", "reconcile", "unknown") else old.status
            history.append(entry)
            if (old.known and status == "confirmed" and not equivalent(update.field, old.value, update.value)
                    and update.operation == "assert"):
                status = "conflicting"
            if old.status == "conflicting" and update.operation == "assert":
                status = "conflicting"  # Repetition alone cannot reconcile a contradiction.
        self.facts[update.field] = Fact(
            value=update.value, status=status, evidence=update.evidence,
            turn_id=turn_id, explicitly_unknown=unknown, history=history,
        )
        # A reconciled denial retains earlier administrations in history only.
        if update.field == "medications_given" and update.value is False and status == "confirmed":
            self.retire_medications(update.evidence, turn_id)
        return True

    def retire_medications(self, evidence, turn_id):
        for key, fact in list(self.facts.items()):
            if key.startswith("medications.") and fact.status != "missing":
                prior = fact.model_dump(exclude={"history"})
                prior["status"] = "superseded"
                self.facts[key] = Fact(evidence=evidence, turn_id=turn_id,
                                       history=fact.history + [prior])
