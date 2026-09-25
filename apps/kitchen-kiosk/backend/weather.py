"""Proxies the existing homepage-api BOM weather endpoint so the kiosk
doesn't need its own BOM integration."""
import os
import requests
from flask import Blueprint, jsonify

weather_bp = Blueprint('weather', __name__)

HOMEPAGE_API_URL = os.getenv('HOMEPAGE_API_URL', 'http://homepage-api:5000')


@weather_bp.route('/api/weather')
def weather():
    try:
        response = requests.get(f'{HOMEPAGE_API_URL}/api/bom/weather', timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except (requests.RequestException, ConnectionError) as e:
        return jsonify({'error': f'weather backend unreachable: {e}'}), 502
