"""Targeted regressions for split spoken input, hedging, and durable repeat demos."""
import json
import threading
import pytest
from fastapi.testclient import TestClient

from backend.agent.controller import Controller, FINISH
from backend.agent.extraction import GuavaExtractor
from backend.agent.question_planner import Question
from backend.domain.facts import Extraction, Update
from backend.store import Store


NARRATIVE = 'Patient with difficulty breathing was transported to County. Nothing made other transportation inappropriate.'


class FixtureExtractor:
    """Fixture responses, not a replacement language extractor."""
    def extract(self, text, encounter, target=None):
        updates = []
        for phrase, field, value in [
            ('difficulty breathing', 'chief_complaint', 'difficulty breathing'),
            ('transported to County', 'transported', True),
            ('County', 'destination', 'County'),
            ('Nothing made other transportation inappropriate', 'transport_justification', 'Nothing made other transportation inappropriate'),
        ]:
            if phrase in text:
                updates.append(Update(field=field, value=value, evidence=phrase))
        return Extraction(updates=updates)


def test_rough_spoken_narrative_is_reconciled_across_human_chunks():
    # Reconstructed from the reported failure; no private call transcript is checked in.
    chunks = ['68-year-old male, called for', 'difficulty breathing',
              'We gave four liters by nasal cannula and transported to County.']

    class SplitNarrative(FixtureExtractor):
        def extract(self, text, encounter, target=None):
            # Isolated fragments can be missed by language extraction; the full
            # narrative parse must recover the actual supplied chief complaint.
            if '\n' not in text:
                return Extraction()
            return super().extract(text, encounter, target)

    c = Controller(SplitNarrative())
    c.begin('rough-call')
    for index, chunk in enumerate(chunks):
        c.upsert(f'HUMAN-{index}', chunk)
        c.flush()
    c.advance()
    assert c.encounter.value('chief_complaint') == 'difficulty breathing'
    assert c.encounter.fact('chief_complaint').turn_id == 'HUMAN-1'
    assert c.current_question.code == 'TRANSPORT_JUSTIFICATION_MISSING'
    assert not any(q['code'] == 'CHIEF_COMPLAINT_MISSING' for q in c.question_history)


def test_speech_arriving_during_extraction_is_applied_before_followup():
    entered, release = threading.Event(), threading.Event()

    class Slow(FixtureExtractor):
        def extract(self, text, encounter, target=None):
            if text == 'We transported to County.':
                entered.set()
                assert release.wait(3)
            return super().extract(text, encounter, target)

    c = Controller(Slow())
    c.begin('race-call')
    c.upsert('HUMAN-1', 'We transported to County.')
    queued = []
    worker = threading.Thread(target=c.dispatch_next, args=(queued.append,))
    worker.start()
    assert entered.wait(3)
    c.upsert('HUMAN-2', 'The chief complaint was difficulty breathing.')
    release.set()
    worker.join(3)
    assert not worker.is_alive()
    assert queued[0].question.code == 'TRANSPORT_JUSTIFICATION_MISSING'
    assert c.encounter.value('chief_complaint') == 'difficulty breathing'


def test_stale_planned_question_is_rechecked_before_enqueue(monkeypatch):
    import backend.agent.controller as module
    original = module.plan
    c = Controller(FixtureExtractor())
    c.begin('planner-race')
    c.upsert('HUMAN-1', 'We transported to County.')
    injected = False

    def late_speech(issue, encounter):
        nonlocal injected
        if issue.code == 'CHIEF_COMPLAINT_MISSING' and not injected:
            injected = True
            c.upsert('HUMAN-2', 'difficulty breathing')
        return original(issue, encounter)

    monkeypatch.setattr(module, 'plan', late_speech)
    queued = []
    c.dispatch_next(queued.append)
    assert len(queued) == 1
    assert queued[0].question.code == 'TRANSPORT_JUSTIFICATION_MISSING'


@pytest.mark.parametrize('hedge', ['I guess', 'I think', 'maybe', 'not sure'])
def test_hedged_rationale_is_uncertain_and_unknown_is_not_reasked(hedge):
    target = Question('TRANSPORT_JUSTIFICATION_MISSING', 'transport_justification', 'What made other transportation inappropriate?')
    speech = f'they were just not feeling well, {hedge}.'

    def overconfident(*args, **kwargs):
        return json.dumps({'updates': [{'field': 'transport_justification', 'value': 'not feeling well',
                         'status': 'confirmed', 'evidence': 'not feeling well'}]})

    c = Controller(GuavaExtractor(overconfident))
    c.begin('hedge-call')
    c.current_question = target
    c.upsert('answer', speech)
    c.flush()
    fact = c.encounter.fact('transport_justification')
    assert fact.status == 'uncertain' and fact.value == speech and fact.evidence == speech
    assert any(i.code == 'UNCERTAIN_VALUE_REQUIRES_CLARIFICATION' and i.blocking for i in c.issues())
    # A plain unknown bypasses generation and cannot turn into an invented rationale.
    c.current_question = Question('UNCERTAIN_VALUE_REQUIRES_CLARIFICATION', 'transport_justification', 'Clarify or leave unspecified?')
    c.speech_group += 1
    c.upsert('unknown', "I don't remember.")
    c.flush()
    assert c.encounter.fact('transport_justification').explicitly_unknown
    assert not any(i.field == 'transport_justification' and i.blocking for i in c.issues())


def test_hedge_in_separate_human_chunk_cannot_leave_confirmed_rationale():
    target = Question('TRANSPORT_JUSTIFICATION_MISSING', 'transport_justification', 'Why transport?')
    def overconfident(*a, **kw):
        return json.dumps({'updates':[{'field':'transport_justification','value':'not feeling well','evidence':'not feeling well'}]})
    c = Controller(GuavaExtractor(overconfident))
    c.current_question = target
    c.upsert('H1', 'they were just not feeling well,')
    c.flush()
    c.upsert('H2', 'I guess.')
    c.reconcile_speech_window()
    assert c.encounter.fact('transport_justification').status == 'uncertain'
    assert 'I guess' in c.encounter.fact('transport_justification').evidence


def completed_store(path):
    s = Store(path, FixtureExtractor())
    c = s.start_call('completed-test-call')
    c.upsert('source', NARRATIVE)
    assert c.advance() == FINISH
    c.end()
    return s


def test_restart_reset_and_reopen_preserve_complete_record(tmp_path):
    path = tmp_path / 'encounters.sqlite3'
    first = completed_store(path)
    original = first.snapshot()
    reopened = Store(path, FixtureExtractor())
    assert reopened.snapshot()['encounter'] == original['encounter']
    assert reopened.snapshot()['history'] == original['history']
    assert reopened.snapshot()['ended_at'] == original['ended_at']
    old_id = original['encounter']['id']
    new_id = reopened.reset().encounter.id
    again = Store(path, FixtureExtractor())
    assert again.current.encounter.id == new_id and new_id != old_id
    assert again.snapshot(old_id)['encounter'] == original['encounter']
    assert not again.snapshot(old_id)['is_current']
    assert len(again.recent()) == 2
    # The next call fills the prepared new demo, rather than creating a spare blank run.
    assert again.start_call('next-test-call').encounter.id == new_id


def test_restart_preserves_partial_sources_and_marks_interrupted_call(tmp_path):
    path = tmp_path / 'interrupted.sqlite3'
    s = Store(path, FixtureExtractor())
    c = s.start_call('interrupted-call')
    c.upsert('HUMAN-1', 'difficulty breathing')  # Persist before extraction finishes.
    restored = Store(path, FixtureExtractor())
    snapshot = restored.snapshot()
    assert snapshot['encounter']['id'] == c.encounter.id
    assert snapshot['turns'][0]['text'] == 'difficulty breathing'
    assert snapshot['call_status'] == 'incomplete' and not snapshot['call_active']
    assert 'restarted' in snapshot['error']
    assert snapshot['ended_at']


def test_historical_routes_and_downloads_do_not_switch_current_encounter(tmp_path, monkeypatch):
    from backend.api import server
    s = completed_store(tmp_path / 'api.sqlite3')
    old_id = s.current.encounter.id
    current_id = s.reset().encounter.id
    monkeypatch.setattr(server, 'store', s)
    client = TestClient(server.app)
    assert client.get(f'/encounters/{old_id}').status_code == 200
    history = client.get(f'/api/encounters/{old_id}').json()
    assert not history['is_current'] and history['call_status'] == 'complete'
    assert client.get(f'/api/encounters/{old_id}/report').json()['encounter']['id'] == old_id
    assert old_id in client.get(f'/api/encounters/{old_id}/draft').text
    assert client.get('/api/encounter/current').json()['encounter']['id'] == current_id
    assert len(client.get('/api/encounters').json()['encounters']) == 2
    assert client.get('/api/encounters/not-a-record').status_code == 404
