import os
import threading
from pathlib import Path
from backend.agent.controller import Controller, now
from backend.agent.extraction import GuavaExtractor
from backend.persistence import EncounterRepository

DEFAULT_DB = Path(__file__).resolve().parents[1] / 'runtime' / 'medic.sqlite3'


class Store:
    def __init__(self, db_path=None, extractor=None):
        self.lock = threading.RLock()
        self.repository = EncounterRepository(db_path or os.getenv('MEDIC_DB_PATH', DEFAULT_DB))
        self.extractor = extractor or GuavaExtractor()
        self.connection, self.connection_error, self.phone_number = 'offline', None, None
        record = self.repository.get(self.repository.current_id())
        if record:
            self.current = Controller.restore(self.extractor, *record)
            self.current.on_change = self._save
            if self.current.call_active:
                # A new process cannot resume an old phone session. Retain every source.
                with self.current.lock:
                    self.current.call_active = False
                    self.current.phase = self.current.encounter.encounter_status = 'incomplete'
                    self.current.ended_at = now()
                    self.current.last_error = 'Backend restarted during this call. Sources are preserved; clinician review is required.'
                    self.current.changed()
        else:
            self.current = self._new()

    def _save(self, controller):
        self.repository.save(controller.snapshot(), controller.persistent_state())

    def _new(self, call_id=None):
        controller = Controller(self.extractor)
        if call_id:
            controller.begin(call_id)
        self.repository.save(controller.snapshot(), controller.persistent_state(), activate=True)
        controller.on_change = self._save
        return controller

    def start_call(self, call_id):
        with self.lock:
            if self.current.call_active or self.repository.has_call(call_id):
                return None
            if self.current.phase == 'waiting' and self.current.call_id is None:
                self.current.begin(call_id)
            else:
                self.current = self._new(call_id)
            return self.current

    def reset(self):
        with self.lock:
            if self.current.call_active:
                raise ValueError('End the active call before starting a new demo.')
            self.current = self._new()
            return self.current

    def _decorate(self, snapshot):
        return {**snapshot, 'connection': self.connection, 'connection_error': self.connection_error,
                'phone_number': self.phone_number, 'current_encounter_id': self.current.encounter.id,
                'is_current': snapshot['encounter']['id'] == self.current.encounter.id,
                'live_call_active': self.current.call_active}

    def snapshot(self, encounter_id=None):
        with self.lock:
            if encounter_id is None or encounter_id == self.current.encounter.id:
                return self._decorate(self.current.snapshot())
            record = self.repository.get(encounter_id)
            if not record:
                raise KeyError(encounter_id)
            return self._decorate(record[0])

    def recent(self):
        with self.lock:
            return [{**row, 'is_current': row['id'] == self.current.encounter.id}
                    for row in self.repository.recent()]


store = Store()
