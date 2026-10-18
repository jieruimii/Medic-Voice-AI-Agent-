"""Sourced state with a fresh-validation barrier before every spoken question."""
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from backend.domain.encounter import Encounter
from backend.domain.facts import Extraction, valid_update
from backend.validation.rules import validate, Issue
from backend.validation.engine import ready_for_review
from .question_planner import plan, Question

OPENING = "Medic here. Whenever you're ready, walk me through the call."
FINISH = "I've got what I need. I've prepared the encounter for your review."


def now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Turn:
    id: str
    text: str
    target: Question | None = None
    extraction: Extraction | None = None
    extracted_text: str = ""
    group: int = 0


@dataclass
class Decision:
    text: str
    phase: str
    version: int
    question: Question | None = None


class Controller:
    def __init__(self, extractor, on_change=None):
        self.extractor, self.on_change = extractor, on_change
        self.lock = threading.RLock()
        self.speech_changed = threading.Condition(self.lock)
        self.work_lock, self.decision_lock = threading.Lock(), threading.Lock()
        self.encounter = Encounter()
        self.turns, self.groups = {}, {}
        self.speech_group = self.speech_version = 0
        self.last_speech_at = 0.0
        self.phase, self.call_id, self.call_active = 'waiting', None, False
        self.current_question, self.question_history = None, []
        self.errors, self.processing = {}, False
        self.last_agent_speech, self.last_error, self.last_failure = '', None, None
        self.revision, self.updated_at, self.ended_at = 0, self.encounter.started_at, None

    def changed(self):
        """Caller holds state lock. Mutations are durable before returning."""
        self.revision += 1
        self.updated_at = now()
        if self.on_change:
            self.on_change(self)

    def begin(self, call_id, live=True):
        with self.lock:
            self.call_id, self.call_active, self.phase = call_id, live, 'narrative'
            self.encounter.encounter_status = 'listening'
            self.changed()

    def upsert(self, turn_id, text):
        with self.speech_changed:
            if turn_id in self.turns:
                if self.turns[turn_id].text == text:
                    return
                self.turns[turn_id].text = text
            else:
                self.turns[turn_id] = Turn(turn_id, text, self.current_question, group=self.speech_group)
            self.speech_version += 1
            self.last_speech_at = time.monotonic()
            if self.phase == 'complete':
                self.phase = self.encounter.encounter_status = 'reconciling'
            self.changed()
            self.speech_changed.notify_all()

    def _checked_extraction(self, text, context, target):
        result = self.extractor.extract(text, context, target)
        invalid = [u.field for u in result.updates if not valid_update(u, text)]
        if invalid:
            raise ValueError('Source evidence validation failed for ' + ', '.join(invalid))
        return result

    def flush(self):
        """Drain every received revision, including arrivals during extraction."""
        with self.work_lock:
            attempted = set()
            while True:
                with self.lock:
                    pending = [(t.id, t.text, t.target) for t in self.turns.values()
                               if t.text != t.extracted_text and (t.id, t.text) not in attempted]
                    self.processing = bool(pending)
                if not pending:
                    break
                for turn_id, text, target in pending:
                    attempted.add((turn_id, text))
                    with self.lock:
                        context = self.encounter.model_copy(deep=True)
                    try:
                        result = self._checked_extraction(text, context, target)
                        with self.lock:
                            turn = self.turns[turn_id]
                            if turn.text != text:
                                continue
                            turn.extraction, turn.extracted_text = result, text
                            self.errors.pop(turn_id, None)
                            self._rebuild()
                            self.changed()
                    except Exception as exc:
                        with self.lock:
                            self.last_failure = f'{type(exc).__name__}: {exc}'
                            self.errors[turn_id] = 'Could not process caller speech. Retry before clinician review.'
                with self.lock:
                    self.last_error = next(iter(self.errors.values()), None)
            with self.lock:
                self.processing = False
                self.changed()

    def _group_turns(self, group):
        return [t for t in self.turns.values() if t.group == group]

    @staticmethod
    def _signature(turns):
        return [(t.id, t.text) for t in turns]

    def _rebuild(self, skip_group=None):
        """A complete speech-window parse replaces its partial chunk parses."""
        e = Encounter(id=self.encounter.id, started_at=self.encounter.started_at)
        used = set()
        for turn in self.turns.values():
            if turn.group == skip_group:
                continue
            group, members = self.groups.get(turn.group), self._group_turns(turn.group)
            batch = group and group['signature'] == self._signature(members)
            if batch:
                if turn.group in used:
                    continue
                used.add(turn.group)
                result, source = group['extraction'], group['text']
            elif turn.extraction:
                result, source = turn.extraction, turn.extracted_text
            else:
                continue
            for update in result.updates:
                source_id = turn.id
                if batch:
                    source_id = next((t.id for t in members if update.evidence.casefold() in t.text.casefold()),
                                     '+'.join(t.id for t in members))
                e.apply(update, source, source_id)
            if e.value('medications_given') is False:
                denial = e.fact('medications_given')
                e.retire_medications(denial.evidence, denial.turn_id)
        e.raw_narrative = '\n'.join(t.text for t in self.turns.values() if t.target is None)
        e.encounter_status = self.encounter.encounter_status
        if skip_group is None:
            self.encounter = e
        return e

    def reconcile_speech_window(self):
        """Interpret fragmented HUMAN speech together before a follow-up."""
        with self.work_lock:
            with self.lock:
                group_id = self.speech_group
                turns = self._group_turns(group_id)
                signature, cached = self._signature(turns), self.groups.get(group_id)
                if len(turns) < 2 or (cached and cached['signature'] == signature):
                    return
                text, target = '\n'.join(t.text for t in turns), turns[0].target
                context = self._rebuild(skip_group=group_id)
                self.processing = True
            try:
                result = self._checked_extraction(text, context, target)
                with self.lock:
                    if signature != self._signature(self._group_turns(group_id)):
                        return
                    self.groups[group_id] = {'signature': signature, 'text': text, 'extraction': result}
                    for turn in turns:
                        turn.extracted_text = turn.text
                        self.errors.pop(turn.id, None)
                    self.errors.pop(f'group:{group_id}', None)
                    self._rebuild()
            except Exception as exc:
                with self.lock:
                    self.last_failure = f'{type(exc).__name__}: {exc}'
                    self.errors[f'group:{group_id}'] = 'Could not reconcile the complete speech window. Review is blocked.'
            finally:
                with self.lock:
                    self.processing = False
                    self.last_error = next(iter(self.errors.values()), None)
                    self.changed()

    def issues(self):
        issues = validate(self.encounter)
        if self.errors or any(t.text != t.extracted_text for t in self.turns.values()):
            issues.insert(0, Issue('EXTRACTION_PENDING', 'required', 'raw_narrative',
                                  'Caller speech is still awaiting successful extraction.', 'SYS'))
        return issues

    def _prepare_decision(self):
        while True:
            with self.lock:
                version = self.speech_version
            self.flush()
            self.reconcile_speech_window()
            with self.lock:
                if version != self.speech_version:
                    continue
                blockers = [i for i in self.issues() if i.blocking]
                if not blockers and ready_for_review(self.encounter):
                    return Decision(FINISH, 'complete', version)
                if blockers and blockers[0].code == 'EXTRACTION_PENDING':
                    return Decision("I'm having trouble processing that. Please repeat the last part.", 'reconciling', version)
                if not blockers:
                    return Decision(OPENING, 'narrative', version)
                issue = blockers[0]
                if self.encounter.fact(issue.field).explicitly_unknown:
                    return Decision("I've recorded that as unspecified. The encounter still has a required documentation gap, so I've left it open for review.", 'incomplete', version)
                question = plan(issue, self.encounter)
                return Decision(question.text, 'reconciling', version, question)

    def _decision_is_current(self, decision):
        if decision.version != self.speech_version:
            return False
        if decision.question:
            return any(i.blocking and i.code == decision.question.code and i.field == decision.question.field
                       for i in self.issues())
        return decision.phase != 'complete' or (not self.errors and ready_for_review(self.encounter))

    def _commit_decision(self, decision):
        self.phase = decision.phase
        self.encounter.encounter_status = 'ready_for_clinician_review' if self.phase == 'complete' else self.phase
        if decision.phase == 'reconciling' and decision.question is None:
            self.changed()
            return
        self.current_question = decision.question
        if decision.question:
            self.question_history.append({**asdict(decision.question), 'turn_count': len(self.turns)})
        self.speech_group += 1
        self.changed()

    def advance(self):
        """Synchronous domain entry point retained for existing tests."""
        with self.decision_lock:
            while True:
                decision = self._prepare_decision()
                with self.lock:
                    if self._decision_is_current(decision):
                        self._commit_decision(decision)
                        return decision.text

    def dispatch_next(self, send):
        """Off Guava's dispatcher: drain, parse, validate, then re-check at enqueue."""
        with self.decision_lock:
            with self.speech_changed:
                # Drain already-queued callbacks. This is not a voice endpointing setting.
                earliest = time.monotonic() + 0.2
                while time.monotonic() < max(earliest, self.last_speech_at + 0.25):
                    self.speech_changed.wait(0.25)
            while True:
                decision = self._prepare_decision()
                with self.lock:
                    if not self._decision_is_current(decision):
                        continue
                    if not self.call_active:
                        return
                    send(decision)
                    self._commit_decision(decision)
                    return

    def end(self, interrupted=False):
        self.flush()
        self.reconcile_speech_window()
        with self.lock:
            self.call_active, self.ended_at = False, now()
            if interrupted or self.phase != 'complete':
                self.phase = self.encounter.encounter_status = 'incomplete'
            if interrupted:
                self.last_error = 'Backend restarted during this call. Sources are preserved; clinician review is required.'
            self.changed()

    def snapshot(self):
        with self.lock:
            issues = [i.serialize() for i in self.issues()]
            payload = self.encounter.model_dump()
            payload['unresolved_issues'] = issues
            return {
                'call_status': self.phase, 'call_active': self.call_active,
                'call_id': self.call_id, 'encounter': payload, 'issues': issues,
                'history': list(self.question_history), 'processing': self.processing,
                'last_agent_speech': self.last_agent_speech, 'error': self.last_error,
                'revision': self.revision, 'updated_at': self.updated_at, 'ended_at': self.ended_at,
                'current_question': asdict(self.current_question) if self.current_question else None,
                'turns': [{'id': t.id, 'text': t.text, 'group': t.group} for t in self.turns.values()],
            }

    def persistent_state(self):
        return {
            'turns': [{**asdict(t), 'extraction': t.extraction.model_dump() if t.extraction else None} for t in self.turns.values()],
            'groups': {str(k): {**g, 'extraction': g['extraction'].model_dump()} for k, g in self.groups.items()},
            'speech_group': self.speech_group, 'speech_version': self.speech_version, 'errors': self.errors,
        }

    @classmethod
    def restore(cls, extractor, payload, state):
        c = cls(extractor)
        c.encounter = Encounter.model_validate(payload['encounter'])
        c.phase, c.call_id, c.call_active = payload['call_status'], payload['call_id'], payload['call_active']
        c.current_question = Question(**payload['current_question']) if payload.get('current_question') else None
        c.question_history = payload.get('history', [])
        c.last_agent_speech, c.last_error = payload.get('last_agent_speech', ''), payload.get('error')
        c.revision, c.updated_at, c.ended_at = payload.get('revision', 0), payload.get('updated_at', c.encounter.started_at), payload.get('ended_at')
        for raw in state.get('turns', []):
            raw = dict(raw)
            raw['target'] = Question(**raw['target']) if raw.get('target') else None
            raw['extraction'] = Extraction.model_validate(raw['extraction']) if raw.get('extraction') else None
            c.turns[raw['id']] = Turn(**raw)
        c.groups = {int(k): {**g, 'signature': [tuple(s) for s in g['signature']],
                             'extraction': Extraction.model_validate(g['extraction'])} for k, g in state.get('groups', {}).items()}
        c.speech_group, c.speech_version, c.errors = state.get('speech_group', 0), state.get('speech_version', 0), state.get('errors', {})
        return c
