"""Opt-in Guava runtime test. Synthetic encounter only; no telephone call placed."""
import json
import sys
import threading
import argparse
import os
from pathlib import Path
os.environ.setdefault('MEDIC_DB_PATH', str(Path(__file__).resolve().parents[1] / 'runtime' / 'synthetic.sqlite3'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.agent.conversation import build_agent
from backend.store import store

NARRATIVE = ("68-year-old male, called for difficulty breathing. We found him sitting upright on the couch, "
             "alert and oriented. Initial oxygen saturation was 88 percent on room air, pressure 148 over 92, "
             "pulse 112. We put him on four liters by nasal cannula and transported him to County.")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dashboard', action='store_true', help='Serve this synthetic test on port 8001 for visual QA')
    args=parser.parse_args()
    if args.dashboard:
        import uvicorn
        store.connection='test session'
        threading.Thread(target=lambda:uvicorn.run('backend.api.server:app',host='127.0.0.1',port=8001,log_level='warning'),daemon=True).start()
    # Bound the remote test even if the hosted runtime never completes a turn.
    watchdog = threading.Timer(150, lambda: __import__('os')._exit(2))
    watchdog.daemon = True
    watchdog.start()
    agent = build_agent()
    with agent.test() as session:
        session.wait_for_turn()
        print(session.get_transcript(), flush=True)
        session.say(NARRATIVE)
        session.wait_for_turn()
        print(session.get_transcript(), flush=True)
        assert store.current.current_question is not None, store.snapshot()
        assert store.current.current_question.code == 'TREATMENT_RESPONSE_MISSING', store.snapshot()
        session.say("It came up to 95.")
        session.wait_for_turn()
        print(session.get_transcript(), flush=True)
        assert store.current.current_question.code == 'TRANSPORT_JUSTIFICATION_MISSING', store.snapshot()
        session.say("He remained short of breath and needed continuous oxygen during transport.")
        session.wait_for_end()
        print(session.get_transcript(), flush=True)
    result = store.snapshot()
    Path('runtime').mkdir(exist_ok=True)
    Path('runtime/golden-result.json').write_text(json.dumps(result, indent=2))
    Path('runtime/golden-transcript.txt').write_text(session.get_transcript(), encoding='utf-8')
    assert result['call_status'] == 'complete', result
    assert not any(i['blocking'] for i in result['issues']), result
    assert result['encounter']['facts']['post_treatment_spo2']['value'] == 95
    watchdog.cancel()
    print('PASS: Guava runtime golden encounter reached clinician review.', flush=True)
    if args.dashboard:
        print('Synthetic test dashboard available on http://127.0.0.1:8001. Ctrl+C to stop.',flush=True)
        threading.Event().wait()


if __name__ == '__main__':
    main()
