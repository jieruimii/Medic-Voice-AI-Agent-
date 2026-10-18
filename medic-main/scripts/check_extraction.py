"""Opt-in extraction contract checks against Guava, using synthetic examples."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.agent.controller import Controller
from backend.agent.extraction import GuavaExtractor


def turn(c, text, id):
    c.upsert(id,text)
    c.flush()
    assert not c.errors, (c.last_failure, c.snapshot())
    return c.encounter


def main():
    c=Controller(GuavaExtractor())
    e=turn(c,"Patient complained of difficulty breathing. Gave aspirin.","1")
    assert e.value('medications.0.name').lower()=='aspirin'
    assert e.value('medications.0.dose') is None
    assert e.value('medications.0.units') is None
    assert e.value('medications.0.route') is None
    assert e.value('spo2') is None
    assert e.value('destination') is None
    print('PASS: absent facts stay absent',flush=True)

    c=Controller(GuavaExtractor())
    e=turn(c,"Pressure was 148 over 92 — sorry, 138 over 92.","1")
    assert e.value('systolic_bp')==138, e.model_dump()
    assert any(h['value']==148 and h['status']=='superseded' for h in e.fact('systolic_bp').history),e.model_dump()
    print('PASS: correction preserves superseded pressure',flush=True)

    c=Controller(GuavaExtractor())
    turn(c,"Patient with difficulty breathing. Initial saturation 88 on room air. Put him on four liters by nasal cannula.","1")
    c.advance()
    e=turn(c,"I think his second saturation was around 94 or 95.","2")
    assert e.fact('post_treatment_spo2').status=='uncertain',e.model_dump()
    assert e.value('post_treatment_spo2') is None
    text=c.advance()
    assert 'exact second saturation' in text,text
    e=turn(c,"I don't remember.","3")
    assert e.fact('post_treatment_spo2').explicitly_unknown,e.model_dump()
    assert e.value('post_treatment_spo2') is None
    c.advance()
    assert c.phase=='complete',c.snapshot()
    print('PASS: uncertainty leads to clarification, unknown accepted',flush=True)

    c=Controller(GuavaExtractor())
    turn(c,"Chest pain. Gave 324 milligrams of aspirin.","1")
    e=turn(c,"No medications were given.","2")
    assert e.fact('medications_given').status=='conflicting',e.model_dump()
    c.advance()
    assert c.current_question.code=='CONFLICT_REQUIRES_RECONCILIATION'
    e=turn(c,"No medications were given; that earlier mention of aspirin was wrong.","3")
    assert e.value('medications_given') is False,e.model_dump()
    assert e.value('medications.0.name') is None
    print('PASS: medication contradiction reconciled explicitly',flush=True)

    c=Controller(GuavaExtractor())
    turn(c,"Patient with chest pain. We transported to County.","1")
    c.advance()
    e=turn(c,"Nothing made another form of transportation inappropriate.","2")
    assert e.value('transport_justification'),e.model_dump()
    c.advance()
    assert c.phase=='complete',c.snapshot()
    print('PASS: negative transport rationale accepted',flush=True)


if __name__=='__main__':
    main()
