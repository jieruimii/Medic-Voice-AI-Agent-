"""Tests must never read or modify the demo's real encounter database."""
import os
import tempfile
from pathlib import Path

_database_dir = tempfile.TemporaryDirectory(prefix='medic-tests-')
os.environ['MEDIC_DB_PATH'] = str(Path(_database_dir.name) / 'test.sqlite3')


def pytest_unconfigure(config):
    _database_dir.cleanup()
