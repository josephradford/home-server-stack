"""Queries the Immich API directly for a random photo from configured
album(s), returning an image URL plus date/place metadata."""
import os
import random
import time

import requests
from flask import Blueprint, Response, jsonify

photos_bp = Blueprint('photos', __name__)

IMMICH_URL = os.getenv('KIOSK_IMMICH_URL', 'http://immich-server:2283')
IMMICH_API_KEY = os.getenv('KIOSK_IMMICH_API_KEY', '')
ALBUM_IDS = [a.strip() for a in os.getenv('KIOSK_IMMICH_ALBUM_IDS', '').split(',') if a.strip()]

ASSETS_CACHE_TTL_SECONDS = 300
_assets_cache = {'data': None, 'fetched_at': 0}


def _headers():
    return {'x-api-key': IMMICH_API_KEY}


def _fetch_asset_ids():
    """GET /api/albums/{id} no longer returns an `assets` array (Immich API
    change since this was first written) - use the search endpoint instead,
    which returns lightweight asset entries (id only, no exifInfo)."""
    ids = []
    for album_id in ALBUM_IDS:
        response = requests.post(
            f'{IMMICH_URL}/api/search/metadata',
            headers=_headers(),
            json={'albumIds': [album_id]},
            timeout=10,
        )
        response.raise_for_status()
        ids.extend(item['id'] for item in response.json().get('assets', {}).get('items', []))
    return ids


def _collect_asset_ids():
    now = time.time()
    if _assets_cache['data'] is not None and (now - _assets_cache['fetched_at']) < ASSETS_CACHE_TTL_SECONDS:
        return _assets_cache['data']

    ids = _fetch_asset_ids()
    _assets_cache['data'] = ids
    _assets_cache['fetched_at'] = now
    return ids


@photos_bp.route('/api/photos/random')
def random_photo():
    try:
        asset_ids = _collect_asset_ids()
    except requests.RequestException as e:
        return jsonify({'error': f'immich unreachable: {e}'}), 502

    if not asset_ids:
        return jsonify({'error': 'no photos available in configured albums'}), 404

    asset_id = random.choice(asset_ids)

    # exifInfo (date/place) is only present on the single-asset detail
    # endpoint, not the list/search response - fetch it for just the one
    # asset we picked, not the whole album.
    try:
        detail = requests.get(f'{IMMICH_URL}/api/assets/{asset_id}', headers=_headers(), timeout=10)
        detail.raise_for_status()
        exif = detail.json().get('exifInfo') or {}
    except requests.RequestException:
        exif = {}

    return jsonify({
        'asset_id': asset_id,
        'image_url': f'/api/photos/{asset_id}/image',
        'taken_at': exif.get('dateTimeOriginal'),
        'place': exif.get('city'),
    })


@photos_bp.route('/api/photos/<asset_id>/image')
def photo_image(asset_id):
    try:
        response = requests.get(
            f'{IMMICH_URL}/api/assets/{asset_id}/thumbnail?size=preview',
            headers=_headers(),
            timeout=10,
            stream=True,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        return jsonify({'error': f'immich unreachable: {e}'}), 502

    return Response(
        response.iter_content(chunk_size=8192),
        content_type=response.headers.get('Content-Type', 'image/jpeg'),
    )
