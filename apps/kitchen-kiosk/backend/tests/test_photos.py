import requests


SEARCH_METADATA_RESPONSE = {
    'assets': {
        'total': 2,
        'count': 2,
        'items': [
            {'id': 'asset-1'},
            {'id': 'asset-2'},
        ],
    }
}

ASSET_1_DETAIL = {
    'id': 'asset-1',
    'exifInfo': {'dateTimeOriginal': '2025-03-01T10:00:00.000Z', 'city': 'Sydney'},
}

ASSET_2_DETAIL = {
    'id': 'asset-2',
    'exifInfo': {'dateTimeOriginal': None, 'city': None},
}


def _mock_search_and_detail(mocker, detail):
    """POST /api/search/metadata returns the asset id list; GET
    /api/assets/<id> returns exifInfo for whichever one was picked."""
    search_response = mocker.Mock()
    search_response.status_code = 200
    search_response.raise_for_status = mocker.Mock()
    search_response.json.return_value = SEARCH_METADATA_RESPONSE
    mock_post = mocker.patch('photos.requests.post', return_value=search_response)

    detail_response = mocker.Mock()
    detail_response.status_code = 200
    detail_response.raise_for_status = mocker.Mock()
    detail_response.json.return_value = detail
    mock_get = mocker.patch('photos.requests.get', return_value=detail_response)

    return mock_post, mock_get


def test_random_photo_returns_asset_with_metadata(client, mocker):
    _mock_search_and_detail(mocker, ASSET_1_DETAIL)
    mocker.patch('photos.random.choice', side_effect=lambda seq: seq[0])

    response = client.get('/api/photos/random')

    assert response.status_code == 200
    data = response.get_json()
    assert data['asset_id'] == 'asset-1'
    assert data['taken_at'] == '2025-03-01T10:00:00.000Z'
    assert data['place'] == 'Sydney'
    assert data['image_url'] == '/api/photos/asset-1/image'


def test_random_photo_handles_missing_metadata(client, mocker):
    _mock_search_and_detail(mocker, ASSET_2_DETAIL)
    mocker.patch('photos.random.choice', side_effect=lambda seq: seq[1])

    response = client.get('/api/photos/random')

    data = response.get_json()
    assert data['asset_id'] == 'asset-2'
    assert data['taken_at'] is None
    assert data['place'] is None


def test_random_photo_502_when_immich_unreachable(client, mocker):
    mocker.patch('photos.requests.post', side_effect=requests.exceptions.ConnectionError('refused'))

    response = client.get('/api/photos/random')

    assert response.status_code == 502


def test_random_photo_404_when_no_assets(client, mocker):
    search_response = mocker.Mock()
    search_response.status_code = 200
    search_response.raise_for_status = mocker.Mock()
    search_response.json.return_value = {'assets': {'total': 0, 'count': 0, 'items': []}}
    mocker.patch('photos.requests.post', return_value=search_response)

    response = client.get('/api/photos/random')

    assert response.status_code == 404


def test_random_photo_omits_metadata_if_detail_fetch_fails(client, mocker):
    """The list call succeeding but the single-asset detail call failing
    shouldn't 502 the whole endpoint - just omit taken_at/place."""
    search_response = mocker.Mock()
    search_response.status_code = 200
    search_response.raise_for_status = mocker.Mock()
    search_response.json.return_value = SEARCH_METADATA_RESPONSE
    mocker.patch('photos.requests.post', return_value=search_response)
    mocker.patch('photos.requests.get', side_effect=requests.exceptions.ConnectionError('refused'))
    mocker.patch('photos.random.choice', side_effect=lambda seq: seq[0])

    response = client.get('/api/photos/random')

    assert response.status_code == 200
    data = response.get_json()
    assert data['asset_id'] == 'asset-1'
    assert data['taken_at'] is None
    assert data['place'] is None


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


def test_random_photo_collects_asset_ids_once_within_cache_ttl(client, mocker):
    mock_post, _ = _mock_search_and_detail(mocker, ASSET_1_DETAIL)

    client.get('/api/photos/random')
    client.get('/api/photos/random')

    assert mock_post.call_count == 1
