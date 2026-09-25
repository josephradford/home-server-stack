def test_radio_stations_returns_four_presets(client):
    response = client.get('/api/radio/stations')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data['stations']) == 4
    names = {s['name'] for s in data['stations']}
    assert names == {'ABC Cricket', 'ABC Classic', 'Double J', 'ABC Jazz'}


def test_radio_station_has_required_fields(client):
    response = client.get('/api/radio/stations')
    station = response.get_json()['stations'][0]
    assert 'id' in station
    assert 'name' in station
    assert 'stream_url' in station


def test_now_playing_returns_artist_and_title(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = mocker.Mock()
    mock_response.json.return_value = {'items': [{'summary': {'artist': 'Skulker', 'title': 'Hej'}}]}
    mocker.patch('radio.requests.get', return_value=mock_response)

    response = client.get('/api/radio/now-playing/double-j')

    assert response.status_code == 200
    assert response.get_json() == {'artist': 'Skulker', 'title': 'Hej'}


def test_now_playing_returns_nulls_for_station_with_no_music_slug(client, mocker):
    # ABC Cricket is sports commentary, not music - no ABC music API slug.
    mock_get = mocker.patch('radio.requests.get')

    response = client.get('/api/radio/now-playing/abc-cricket')

    assert response.status_code == 200
    assert response.get_json() == {'artist': None, 'title': None}
    mock_get.assert_not_called()


def test_now_playing_returns_nulls_when_abc_api_unreachable(client, mocker):
    import requests
    mocker.patch('radio.requests.get', side_effect=requests.exceptions.ConnectionError('refused'))

    response = client.get('/api/radio/now-playing/abc-jazz')

    assert response.status_code == 200
    assert response.get_json() == {'artist': None, 'title': None}


def test_now_playing_caches_within_ttl(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = mocker.Mock()
    mock_response.json.return_value = {'items': [{'summary': {'artist': 'A', 'title': 'B'}}]}
    mock_get = mocker.patch('radio.requests.get', return_value=mock_response)

    client.get('/api/radio/now-playing/abc-classic')
    client.get('/api/radio/now-playing/abc-classic')

    assert mock_get.call_count == 1
