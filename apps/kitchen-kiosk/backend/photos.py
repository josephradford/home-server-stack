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


def _fetch_assets():
    assets = []
    for album_id in ALBUM_IDS:
        response = requests.get(f'{IMMICH_URL}/api/albums/{album_id}', headers=_headers(), timeout=10)
        response.raise_for_status()
        assets.extend(response.json().get('assets', []))
    return assets


def _collect_assets():
    now = time.time()
    if _assets_cache['data'] is not None and (now - _assets_cache['fetched_at']) < ASSETS_CACHE_TTL_SECONDS:
        return _assets_cache['data']

    assets = _fetch_assets()
    _assets_cache['data'] = assets
    _assets_cache['fetched_at'] = now
    return assets


@photos_bp.route('/api/photos/random')
def random_photo():
    try:
        assets = _collect_assets()
    except requests.RequestException as e:
        return jsonify({'error': f'immich unreachable: {e}'}), 502

    if not assets:
        return jsonify({'error': 'no photos available in configured albums'}), 404

    asset = random.choice(assets)
    exif = asset.get('exifInfo') or {}

    return jsonify({
        'asset_id': asset['id'],
        'image_url': f'/api/photos/{asset["id"]}/image',
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
