import json
import pytest
from backend.domain.encounter import Encounter
from backend.domain.facts import Update, Extraction
from backend.validation.rules import validate
from backend.validation.engine import ready_for_review
from backend.agent.controller import Controller, FINISH
from backend.agent.extraction import GuavaExtractor
from backend.agent.question_planner import plan


def put(e, key, value, text=None, **kwargs):
    text = text or str(value)
    assert e.apply(Update(field=key, value=value, evidence=text, **kwargs), text, "turn-1")
    return e


def codes(e):
    return {i.code for i in validate(e)}


def encounter():
    e = Encounter(raw_narrative="We found a patient sitting upright reporting difficulty breathing.")
    put(e, "chief_complaint", "difficulty breathing")
    return e


def oxygen():
    e = encounter()
    put(e, "oxygen_given", True)
    put(e, "oxygen_flow_lpm", 4)
    put(e, "oxygen_route", "nasal cannula")
    return e


def test_no_absent_fields_are_invented():
    e = encounter()
    assert e.value("spo2") is None
    assert e.value("destination") is None
    assert e.value("oxygen_given") is None


def test_evidence_is_required_and_must_be_in_caller_speech():
    e = encounter()
    u = Update(field="spo2", value=95, evidence="sat 95")
    assert not e.apply(u, "Patient short of breath", "turn")
    assert "spo2" not in e.facts


def test_explicit_correction_supersedes_and_retains_history():
    e = encounter()
    put(e, "systolic_bp", 148, "Pressure 148 over 92")
    put(e, "systolic_bp", 138, "Sorry, 138 over 92", operation="correct")
    assert e.value("systolic_bp") == 138
    assert e.fact("systolic_bp").history[0]["value"] == 148
    assert e.fact("systolic_bp").history[0]["status"] == "superseded"


def test_uncertain_values_are_not_exact_values():
    e = oxygen()
    put(e, "post_treatment_spo2", None, "I think 94 or 95", status="uncertain")
    assert e.value("post_treatment_spo2") is None
    assert e.fact("post_treatment_spo2").status == "uncertain"
    issue = next(i for i in validate(e) if i.code.startswith("UNCERTAIN"))
    assert "exact second saturation" in plan(issue, e).text


def test_numeric_uncertainty_guard_rejects_exact_model_guess():
    def generated(*args, **kwargs):
        return json.dumps({"updates":[{"field":"post_treatment_spo2","value":95,"status":"confirmed","evidence":"I think 94 or 95","operation":"assert"}]})
    update = GuavaExtractor(generated).extract("I think 94 or 95", encounter()).updates[0]
    assert update.value is None and update.status == "uncertain"


def test_unknown_does_not_fabricate_a_value_and_contextual_becomes_advisory():
    e = oxygen()
    put(e, "post_treatment_spo2", None, "I don't remember", operation="unknown", status="missing")
    assert e.value("post_treatment_spo2") is None
    assert e.fact("post_treatment_spo2").explicitly_unknown
    assert ready_for_review(e)
    assert any(i.code == "TREATMENT_RESPONSE_MISSING" and not i.blocking for i in validate(e))


def test_oxygen_without_response_triggers_gap():
    assert "TREATMENT_RESPONSE_MISSING" in codes(oxygen())


def test_reassessment_resolves_response_gap():
    e = oxygen()
    put(e, "post_treatment_spo2", 95)
    assert "TREATMENT_RESPONSE_MISSING" not in codes(e)


def test_transport_without_destination_triggers_required_issue():
    e = encounter()
    put(e, "transported", True)
    assert any(i.code == "DESTINATION_MISSING" and i.severity == "required" for i in validate(e))


def test_transport_without_justification_triggers_gap():
    e = encounter()
    put(e, "transported", True)
    assert "TRANSPORT_JUSTIFICATION_MISSING" in codes(e)


@pytest.mark.parametrize("negative", ["Nothing", "No reason", "Another form of transport would have been appropriate"])
def test_negative_transport_answer_is_accepted(negative):
    e = encounter()
    put(e, "transported", True)
    put(e, "destination", "County")
    put(e, "transport_justification", negative)
    assert "TRANSPORT_JUSTIFICATION_MISSING" not in codes(e)
    assert ready_for_review(e)


def test_medication_without_route_triggers_gap_and_never_defaults_to_oral():
    e = encounter()
    put(e, "medications.0.name", "aspirin")
    put(e, "medications.0.dose", 324)
    assert "MEDICATION_ROUTE_MISSING" in codes(e)
    assert e.value("medications.0.route") is None
    assert e.value("medications.0.units") is None
    assert "MEDICATION_UNITS_MISSING" in codes(e)


def test_medication_requires_response():
    e = encounter()
    put(e, "medications.0.name", "aspirin")
    assert any(i.code == "TREATMENT_RESPONSE_MISSING" and i.field == "medications.0.response" for i in validate(e))


def test_contradiction_produces_reconciliation_requirement():
    e = encounter()
    put(e, "medications_given", True, "Gave aspirin")
    put(e, "medications.0.name", "aspirin")
    put(e, "medications_given", False, "No medications were given")
    assert e.fact("medications_given").status == "conflicting"
    assert e.value("medications.0.name") == "aspirin"
    assert validate(e)[0].code == "CONFLICT_REQUIRES_RECONCILIATION"
    put(e, "medications_given", False, "No, I did not give any medication", operation="reconcile")
    assert e.value("medications.0.name") is None
    assert e.fact("medications.0.name").history[0]["value"] == "aspirin"
    assert ready_for_review(e)


def test_advisory_does_not_block_review():
    e = encounter()
    put(e, "transported", True)
    put(e, "destination", "County")
    put(e, "transport_justification", "Needed continuous oxygen")
    assert "TRANSPORT_PRIORITY_MISSING" in codes(e)
    assert ready_for_review(e)


class ScriptedExtractor:
    def __init__(self, scripts):
        self.scripts = scripts

    def extract(self, text, encounter, target=None):
        return Extraction(updates=[Update(field=k, value=v, evidence=text, **kw) for k, v, kw in self.scripts[text]])


def test_resolved_question_is_not_asked_again_and_golden_flow():
    narrative = "A 68 year old with difficulty breathing received 4 liters of oxygen via nasal cannula and was transported to County."
    response = "It came up to 95."
    reason = "He needed continuous oxygen during transport."
    c = Controller(ScriptedExtractor({
        narrative: [("chief_complaint","difficulty breathing",{}),("oxygen_given",True,{}),("oxygen_flow_lpm",4,{}),("oxygen_route","nasal cannula",{}),("transported",True,{}),("destination","County",{})],
        response: [("post_treatment_spo2",95,{})], reason: [("transport_justification",reason,{})],
    }))
    c.begin("test")
    c.upsert("a", narrative)
    assert "saturation" in c.advance()
    c.upsert("b", response)
    assert "another form" in c.advance()
    assert c.current_question.code == "TRANSPORT_JUSTIFICATION_MISSING"
    c.upsert("c", reason)
    assert c.advance() == FINISH
    assert c.phase == "complete"
    assert [q["code"] for q in c.question_history] == ["TREATMENT_RESPONSE_MISSING", "TRANSPORT_JUSTIFICATION_MISSING"]


def test_required_issue_prevents_complete_transition():
    c = Controller(ScriptedExtractor({"Patient transported to hospital": [("transported",True,{})]}))
    c.begin("test")
    c.upsert("a", "Patient transported to hospital")
    assert c.advance() != FINISH
    assert c.phase != "complete"


def test_unknown_required_fact_remains_blocking_without_pressuring():
    c = Controller(ScriptedExtractor({"No idea where": [("destination",None,{"operation":"unknown","status":"missing"})]}))
    c.encounter = encounter()
    put(c.encounter,"transported",True)
    c.upsert("a", "No idea where")
    # Test raw required unknown directly; advance must never mark it ready.
    c.flush()
    put(c.encounter,"transported",True)
    put(c.encounter,"chief_complaint","difficulty breathing")
    c.advance()
    assert c.phase == "incomplete"


def test_asr_revisions_do_not_create_false_clinical_history():
    c = Controller(ScriptedExtractor({"sat 8": [("spo2",8,{})],"sat 88": [("spo2",88,{})]}))
    c.upsert("same-utterance", "sat 8")
    c.flush()
    c.upsert("same-utterance", "sat 88")
    c.flush()
    assert c.encounter.value("spo2") == 88
    assert c.encounter.fact("spo2").history == []


def test_extraction_error_cannot_complete():
    class Broken:
        def extract(self,*args):
            raise RuntimeError("offline")
    c = Controller(Broken())
    c.encounter = encounter()
    c.upsert("turn", "Initial encounter account")
    c.advance()
    assert c.phase != "complete"
    assert c.issues()[0].code == "EXTRACTION_PENDING"


def test_unknown_field_and_wrong_numeric_types_are_rejected():
    e = encounter()
    assert not e.apply(Update(field="spo2",value=True,evidence="yes"),"yes","turn")
    assert not e.apply(Update(field="claim_approved",value=True,evidence="yes"),"yes","turn")


def test_out_of_order_facts_do_not_require_a_form_sequence():
    e = encounter()
    put(e,"post_treatment_spo2",95)
    put(e,"oxygen_given",True)
    put(e,"oxygen_route","nasal cannula")
    assert "TREATMENT_RESPONSE_MISSING" not in codes(e)


def test_unrelated_uncertainty_does_not_resolve_response():
    e = oxygen()
    put(e,"age",None,"maybe 68",status="uncertain")
    assert "TREATMENT_RESPONSE_MISSING" in codes(e)


def test_new_evidence_revokes_completion_pending_extraction():
    c = Controller(ScriptedExtractor({}))
    c.phase="complete"
    c.upsert("new", "Actually a new fact")
    assert c.phase != "complete"


def test_repeated_conflicting_candidate_does_not_silently_resolve_conflict():
    e=encounter()
    put(e,"systolic_bp",148)
    put(e,"systolic_bp",138)
    put(e,"systolic_bp",138)
    assert e.fact("systolic_bp").status == "conflicting"
    assert "CONFLICT_REQUIRES_RECONCILIATION" in codes(e)


def test_unidentified_medication_is_a_required_gap():
    e=encounter()
    put(e,"medications_given",True,"We gave a medication")
    assert "MEDICATION_NAME_MISSING" in codes(e)
    assert not ready_for_review(e)


def test_one_uncertain_saturation_does_not_create_two_followups():
    def generate(*a,**kw):
        return json.dumps({'updates':[
            {'field':'post_treatment_spo2','value':None,'status':'uncertain','evidence':'94 or 95'},
            {'field':'treatment_response','value':None,'status':'uncertain','evidence':'I think 94 or 95'},
        ]})
    result=GuavaExtractor(generate).extract('I think 94 or 95',encounter())
    assert [u.field for u in result.updates]==['post_treatment_spo2']


def test_reconciled_denial_cannot_resurrect_a_negated_medication_name():
    c=Controller(ScriptedExtractor({
        'Gave aspirin': [('medications_given',True,{}),('medications.0.name','aspirin',{})],
        'Aspirin was wrong, no medications were given': [
            ('medications_given',False,{'operation':'reconcile'}),
            ('medications.0.name','aspirin',{}),
        ],
    }))
    c.upsert('1','Gave aspirin')
    c.flush()
    c.upsert('2','Aspirin was wrong, no medications were given')
    c.flush()
    assert c.encounter.value('medications.0.name') is None
    assert c.encounter.fact('medications.0.name').history[0]['value']=='aspirin'


def test_synonymous_breathing_complaint_does_not_create_a_false_conflict():
    e=encounter()
    put(e,'chief_complaint','shortness of breath')
    assert e.fact('chief_complaint').status=='confirmed'
    assert e.value('chief_complaint')=='difficulty breathing'


def test_incorrect_model_deletion_cannot_remove_medications_before_reconciliation():
    def generate(*a,**kw):
        return json.dumps({'updates':[
            {'field':'medications_given','value':False,'status':'confirmed','operation':'correct','evidence':'No medications'},
            {'field':'medications.0.name','value':None,'status':'missing','operation':'assert','evidence':'No medications'},
        ]})
    e=encounter()
    put(e,'medications_given',True)
    put(e,'medications.0.name','aspirin')
    result=GuavaExtractor(generate).extract('No medications',e)
    for u in result.updates:
        e.apply(u,'No medications','new-turn')
    assert e.fact('medications_given').status=='conflicting'
    assert e.value('medications.0.name')=='aspirin'


@pytest.mark.parametrize('value,evidence',[(88,'eighty-eight'),(4,'four liters'),(138,'one hundred thirty-eight'),(148,'one forty eight'),(4.5,'four point five'),(12,'sat was 12')])
def test_numeric_facts_are_grounded_in_spoken_or_digit_evidence(value,evidence):
    e=encounter()
    assert e.apply(Update(field='spo2',value=value,evidence=evidence),evidence,'1')


def test_number_not_present_in_source_is_rejected_even_with_a_valid_quote():
    e=encounter()
    assert not e.apply(Update(field='spo2',value=95,evidence='sat was 88'),'sat was 88','1')


def test_explicit_pressure_correction_history_survives_model_omission():
    def generate(*a,**kw):
        return json.dumps({'updates':[{'field':'systolic_bp','value':138,'evidence':'138 over 92','operation':'correct'}]})
    text='Pressure was 148 over 92 — sorry, 138 over 92.'
    e=encounter()
    for u in GuavaExtractor(generate).extract(text,e).updates:
        assert e.apply(u,text,'turn')
    assert e.value('systolic_bp')==138
    assert e.fact('systolic_bp').history[0]['value']==148
    assert e.fact('systolic_bp').history[0]['status']=='superseded'


def test_source_punctuation_is_anchored_to_original_not_fabricated():
    from backend.agent.extraction import anchor_evidence
    speech='No medications were given; the earlier mention was wrong.'
    assert anchor_evidence('No medications were given.',speech)=='No medications were given'
    assert anchor_evidence('Gave aspirin',speech)=='Gave aspirin'


def test_model_null_deletions_are_deferred_to_medication_reconciliation():
    def generate(*a,**kw):
        return json.dumps({'updates':[
            {'field':'medications_given','value':False,'status':'confirmed','operation':'reconcile','evidence':'No medications were given'},
            {'field':'medications.0.dose','value':None,'status':'confirmed','operation':'correct','evidence':'aspirin was wrong'},
        ]})
    from backend.agent.question_planner import Question
    q=Question('CONFLICT_REQUIRES_RECONCILIATION','medications_given','Which should I document?')
    result=GuavaExtractor(generate).extract('No medications were given; aspirin was wrong',encounter(),q)
    assert [u.field for u in result.updates]==['medications_given']


def test_numeric_representation_does_not_create_false_conflict():
    e=encounter()
    put(e,'systolic_bp',148)
    put(e,'systolic_bp',148.0,'Pressure 148')
    assert e.fact('systolic_bp').status=='confirmed'
    assert not e.fact('systolic_bp').history
