def test_health_check_returns_200(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'healthy'


def test_config_returns_sleep_window(client, monkeypatch):
    monkeypatch.setenv('KIOSK_SLEEP_START', '23:00')
    monkeypatch.setenv('KIOSK_SLEEP_END', '07:00')

    response = client.get('/api/config')

    assert response.status_code == 200
    assert response.get_json() == {'sleep_start': '23:00', 'sleep_end': '07:00'}
