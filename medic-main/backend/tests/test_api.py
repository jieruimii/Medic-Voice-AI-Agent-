from fastapi.testclient import TestClient
from backend.api.server import app
from backend.store import store

client = TestClient(app)


def test_current_endpoint_and_dashboard_are_available():
    response = client.get('/api/encounter/current')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert {'encounter','issues','history','call_status'} <= response.json().keys()
    assert 'MEDIC' in client.get('/').text


def test_reset_refuses_to_discard_active_call():
    store.current.call_active = True
    try:
        assert client.post('/api/encounter/reset').status_code == 409
    finally:
        store.current.call_active = False


def test_reset_creates_new_empty_encounter():
    old = store.current.encounter.id
    result = client.post('/api/encounter/reset').json()
    assert result['encounter']['id'] != old
    assert not result['encounter']['facts']


def test_cross_origin_reset_is_refused():
    assert client.post('/api/encounter/reset', headers={'Origin':'https://unrelated.example'}).status_code == 403


def test_readable_draft_and_provenance_export():
    draft=client.get('/api/encounter/draft')
    assert draft.status_code==200
    assert 'clinician review required' in draft.text
    assert 'medic-review-draft.txt' in draft.headers['content-disposition']
    report=client.get('/api/encounter/report')
    assert 'facts' in report.json()['encounter']
