import requests


IMMICH_ALBUM_RESPONSE = {
    'assets': [
        {
            'id': 'asset-1',
            'exifInfo': {'dateTimeOriginal': '2025-03-01T10:00:00.000Z', 'city': 'Sydney'},
        },
        {
            'id': 'asset-2',
            'exifInfo': {'dateTimeOriginal': None, 'city': None},
        },
    ]
}


def test_random_photo_returns_asset_with_metadata(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = IMMICH_ALBUM_RESPONSE
    mocker.patch('photos.requests.get', return_value=mock_response)
    mocker.patch('photos.random.choice', side_effect=lambda seq: seq[0])

    response = client.get('/api/photos/random')

    assert response.status_code == 200
    data = response.get_json()
    assert data['asset_id'] == 'asset-1'
    assert data['taken_at'] == '2025-03-01T10:00:00.000Z'
    assert data['place'] == 'Sydney'
    assert data['image_url'].endswith('/api/assets/asset-1/thumbnail?size=preview')


def test_random_photo_handles_missing_metadata(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = IMMICH_ALBUM_RESPONSE
    mocker.patch('photos.requests.get', return_value=mock_response)
    mocker.patch('photos.random.choice', side_effect=lambda seq: seq[1])

    response = client.get('/api/photos/random')

    data = response.get_json()
    assert data['asset_id'] == 'asset-2'
    assert data['taken_at'] is None
    assert data['place'] is None


def test_random_photo_502_when_immich_unreachable(client, mocker):
    mocker.patch('photos.requests.get', side_effect=requests.exceptions.ConnectionError('refused'))

    response = client.get('/api/photos/random')

    assert response.status_code == 502


def test_random_photo_404_when_no_assets(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'assets': []}
    mocker.patch('photos.requests.get', return_value=mock_response)

    response = client.get('/api/photos/random')

    assert response.status_code == 404
