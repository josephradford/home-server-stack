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
