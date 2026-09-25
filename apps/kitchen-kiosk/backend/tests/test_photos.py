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
    assert data['image_url'] == '/api/photos/asset-1/image'


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


def test_photo_image_streams_bytes_from_immich(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = mocker.Mock()
    mock_response.headers = {'Content-Type': 'image/jpeg'}
    mock_response.iter_content.return_value = iter([b'fake', b'-jpeg-bytes'])
    mocker.patch('photos.requests.get', return_value=mock_response)

    response = client.get('/api/photos/asset-1/image')

    assert response.status_code == 200
    assert response.data == b'fake-jpeg-bytes'
    assert response.content_type == 'image/jpeg'


def test_photo_image_502_when_immich_unreachable(client, mocker):
    mocker.patch('photos.requests.get', side_effect=requests.exceptions.ConnectionError('refused'))

    response = client.get('/api/photos/asset-1/image')

    assert response.status_code == 502


def test_random_photo_collects_assets_once_within_cache_ttl(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = IMMICH_ALBUM_RESPONSE
    mock_get = mocker.patch('photos.requests.get', return_value=mock_response)

    client.get('/api/photos/random')
    client.get('/api/photos/random')

    assert mock_get.call_count == 1
