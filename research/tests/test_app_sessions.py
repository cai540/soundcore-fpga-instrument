import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from score_api.app_sessions import AppSessions
from score_api.jobs import Jobs
from score_api.protocol import ApiError
from score_api.server import make_server


def test_installation_sessions_are_signed_expiring_and_do_not_expose_server_key(tmp_path):
    now = [100000.0]
    sessions = AppSessions(tmp_path, clock=lambda: now[0])
    first = sessions.issue('a' * 32, 'phone')['access_token']
    second = sessions.issue('b' * 32, 'phone')['access_token']
    assert sessions.verify(first) != sessions.verify(second)
    assert sessions.key.hex() not in json.dumps(first)
    with pytest.raises(ApiError):
        sessions.verify(first[:-2] + 'xx')
    now[0] += 86401
    with pytest.raises(ApiError):
        sessions.verify(first)


def test_quotas_are_durable_and_ip_limit_survives_installation_rotation(tmp_path):
    sessions = AppSessions(tmp_path, clock=lambda: 100000)
    for index in range(12):
        sessions.before_job(f'owner-{index}', 'same-phone-network')
    restarted = AppSessions(tmp_path, clock=lambda: 100000)
    with pytest.raises(ApiError) as error:
        restarted.before_job('fresh-installation', 'same-phone-network')
    assert error.value.status == 429


def test_jobs_deduplicate_within_owner_and_are_not_readable_or_cancellable_by_another_installation(tmp_path):
    config = tmp_path / 'config.json'
    config.write_text('{}')
    jobs = Jobs(config, tmp_path / 'work')
    jobs._run = lambda job: None
    source = {'request_id': 'request-1234567890', 'source_sha256': 'digest'}
    try:
        first = jobs.submit(b'audio', source, owner='first')
        repeated = jobs.submit(b'audio', source, owner='first')
        second = jobs.submit(b'audio', source, owner='second')
        assert first['job_id'] == repeated['job_id']
        assert first['job_id'] != second['job_id']
        for action in [jobs.get, jobs.cancel]:
            with pytest.raises(ApiError) as error:
                action(first['job_id'], owner='second')
            assert error.value.status == 404
        assert jobs.get(first['job_id'], owner='first')['status'] == 'queued'
    finally:
        jobs.close()


def test_actual_http_session_bootstrap_allows_health_without_a_manual_service_token(tmp_path):
    sessions = AppSessions(tmp_path / 'sessions')
    server = make_server(('127.0.0.1', 0), 'server-only-secret-token-1234567', None,
                         sheet_ready=lambda: True, app_sessions=sessions)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        body = json.dumps({'installation_id': 'a' * 32}).encode()
        session = json.load(urlopen(Request(base + '/v1/session', data=body, headers={'Content-Type': 'application/json'})))
        health = json.load(urlopen(Request(base + '/v1/sheet-health', headers={'Authorization': 'Bearer ' + session['access_token']})))
        assert health['ready'] is True
        with pytest.raises(HTTPError) as error:
            urlopen(base + '/v1/sheet-health')
        assert error.value.code == 401
        assert b'server-only-secret-token' not in error.value.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
