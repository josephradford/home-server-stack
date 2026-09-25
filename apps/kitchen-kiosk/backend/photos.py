"""Queries the Immich API directly for a random photo from configured
album(s), returning an image URL plus date/place metadata."""
import os
import random

import requests
from flask import Blueprint, jsonify

photos_bp = Blueprint('photos', __name__)

IMMICH_URL = os.getenv('KIOSK_IMMICH_URL', 'http://immich-server:2283')
IMMICH_API_KEY = os.getenv('KIOSK_IMMICH_API_KEY', '')
ALBUM_IDS = [a.strip() for a in os.getenv('KIOSK_IMMICH_ALBUM_IDS', '').split(',') if a.strip()]


def _headers():
    return {'x-api-key': IMMICH_API_KEY}


def _collect_assets():
    assets = []
    for album_id in ALBUM_IDS:
        response = requests.get(f'{IMMICH_URL}/api/albums/{album_id}', headers=_headers(), timeout=10)
        response.raise_for_status()
        assets.extend(response.json().get('assets', []))
    return assets


@photos_bp.route('/api/photos/random')
def random_photo():
    try:
        assets = _collect_assets()
    except Exception as e:
        return jsonify({'error': f'immich unreachable: {e}'}), 502

    if not assets:
        return jsonify({'error': 'no photos available in configured albums'}), 404

    asset = random.choice(assets)
    exif = asset.get('exifInfo') or {}

    return jsonify({
        'asset_id': asset['id'],
        'image_url': f'{IMMICH_URL}/api/assets/{asset["id"]}/thumbnail?size=preview',
        'taken_at': exif.get('dateTimeOriginal'),
        'place': exif.get('city'),
    })
