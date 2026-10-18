from .rules import validate


def ready_for_review(encounter):
    return bool(encounter.raw_narrative.strip()) and not any(i.blocking for i in validate(encounter))
