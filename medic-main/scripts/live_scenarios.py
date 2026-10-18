"""Opt-in synthetic Guava runtime checks beyond the golden respiratory case."""
import argparse
import json
import os
import sys
import threading
from pathlib import Path
os.environ.setdefault('MEDIC_DB_PATH', str(Path(__file__).resolve().parents[1] / 'runtime' / 'synthetic.sqlite3'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.agent.conversation import build_agent
from backend.store import store
from scripts.live_golden import NARRATIVE

CASES={
    'uncertainty': (NARRATIVE,[
        ('TREATMENT_RESPONSE_MISSING','I think his second saturation was around 94 or 95.'),
        ('UNCERTAIN_VALUE_REQUIRES_CLARIFICATION',"I don't remember."),
        ('TRANSPORT_JUSTIFICATION_MISSING','He needed continuous oxygen during transport.'),
    ]),
    'correction':(NARRATIVE.replace('pressure 148 over 92','pressure 148 over 92 — sorry, 138 over 92'),[
        ('TREATMENT_RESPONSE_MISSING','It came up to 95.'),
        ('TRANSPORT_JUSTIFICATION_MISSING','He needed continuous oxygen during transport.'),
    ]),
    'chest':('52-year-old male with chest pain starting about thirty minutes before arrival. Alert and oriented, pressure 162 over 94, pulse 108. Gave 324 milligrams of aspirin and transported to County.',[
        ('MEDICATION_ROUTE_MISSING','By mouth.'),
        ('TREATMENT_RESPONSE_MISSING','There was no change in his chest pain after the aspirin.'),
        ('TRANSPORT_JUSTIFICATION_MISSING','Nothing made another form of transportation inappropriate.'),
    ]),
    'contradiction':('52-year-old male with chest pain. Gave 324 milligrams of aspirin and transported to County.',[
        ('MEDICATION_ROUTE_MISSING','No medications were given.'),
        ('CONFLICT_REQUIRES_RECONCILIATION','I did give 324 milligrams of aspirin by mouth. The statement about no medications was wrong.'),
        ('TREATMENT_RESPONSE_MISSING','There was no change in his chest pain after aspirin.'),
        ('TRANSPORT_JUSTIFICATION_MISSING','Nothing made another form of transportation inappropriate.'),
    ]),
}


def run(case):
    watchdog=threading.Timer(150,lambda:os._exit(2))
    watchdog.daemon=True
    watchdog.start()
    narrative,steps=CASES[case]
    with build_agent().test() as session:
        session.wait_for_turn()
        session.say(narrative)
        for code,answer in steps:
            session.wait_for_turn()
            question=store.current.current_question
            assert question and question.code==code,(case,code,store.snapshot(),session.get_transcript())
            print(f'{case}: {question.text}',flush=True)
            session.say(answer)
        session.wait_for_end()
    result=store.snapshot()
    assert result['call_status']=='complete',(case,result,session.get_transcript())
    if case=='uncertainty':
        fact=store.current.encounter.fact('post_treatment_spo2')
        assert fact.explicitly_unknown and fact.value is None
    if case=='correction':
        fact=store.current.encounter.fact('systolic_bp')
        assert fact.value==138 and any(h['value']==148 and h['status']=='superseded' for h in fact.history)
    Path('runtime').mkdir(exist_ok=True)
    Path(f'runtime/{case}-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    Path(f'runtime/{case}-transcript.txt').write_text(session.get_transcript(),encoding='utf-8')
    watchdog.cancel()
    print(f'PASS: {case} reached clinician review.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('case',choices=[*CASES,'all'],default='all',nargs='?')
    args=parser.parse_args()
    for case in CASES if args.case=='all' else [args.case]:
        run(case)
