def test_weather_proxies_homepage_api(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'current': {'temp': 21.5}}
    mocker.patch('weather.requests.get', return_value=mock_response)

    response = client.get('/api/weather')

    assert response.status_code == 200
    assert response.get_json() == {'current': {'temp': 21.5}}


def test_weather_returns_502_when_homepage_api_unreachable(client, mocker):
    mocker.patch('weather.requests.get', side_effect=ConnectionError('refused'))

    response = client.get('/api/weather')

    assert response.status_code == 502
    assert 'error' in response.get_json()
