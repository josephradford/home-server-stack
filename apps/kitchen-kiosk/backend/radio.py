"""Static radio station presets — no auth, no proxying of the stream itself.

Also proxies ABC's public "now playing" track-metadata API. This is a
separate service from the audio stream itself (the same way a DAB+ car
radio or the ABC Listen app gets track info from a broadcast metadata
channel / the app's own backend, not by parsing the audio) — verified live
against https://music.abcradio.net.au/api/v1/plays/search.json, which
returns real, current, publicly accessible track data with no auth needed.
"""
import time

import requests
from flask import Blueprint, jsonify

radio_bp = Blueprint('radio', __name__)

# Stream URLs are ABC's public HLS endpoints on Akamai's CDN - no account
# needed. The numeric path segment is not meaningful (verified by testing -
# only the station-name segment selects the actual stream); these were found
# via web search and each verified live with current segment timestamps.
STATIONS = [
    {'id': 'abc-cricket', 'name': 'ABC Cricket', 'stream_url': 'https://mediaserviceslive.akamaized.net/hls/live/2038320/grandstand/index.m3u8'},
    {'id': 'abc-classic', 'name': 'ABC Classic', 'stream_url': 'https://mediaserviceslive.akamaized.net/hls/live/2038316/classicfmnsw/masterhq.m3u8'},
    {'id': 'double-j', 'name': 'Double J', 'stream_url': 'https://mediaserviceslive.akamaized.net/hls/live/2038315/doublejnsw/index.m3u8'},
    {'id': 'abc-jazz', 'name': 'ABC Jazz', 'stream_url': 'https://mediaserviceslive.akamaized.net/hls/live/2038319/abcjazz/masterhq.m3u8'},
]

# ABC's music API uses its own station slugs, distinct from our station ids.
# ABC Cricket has no entry - it's sports commentary, not music, so "now
# playing" track metadata doesn't apply to it.
ABC_MUSIC_API = 'https://music.abcradio.net.au/api/v1/plays/search.json'
STATION_MUSIC_SLUGS = {
    'abc-classic': 'classic',
    'double-j': 'doublej',
    'abc-jazz': 'jazz',
}

NOW_PLAYING_CACHE_TTL_SECONDS = 15
_now_playing_cache = {}  # station_id -> {'data': ..., 'fetched_at': ...}


@radio_bp.route('/api/radio/stations')
def stations():
    return jsonify({'stations': STATIONS})


@radio_bp.route('/api/radio/now-playing/<station_id>')
def now_playing(station_id):
    slug = STATION_MUSIC_SLUGS.get(station_id)
    if not slug:
        return jsonify({'artist': None, 'title': None})

    cached = _now_playing_cache.get(station_id)
    now = time.time()
    if cached and (now - cached['fetched_at']) < NOW_PLAYING_CACHE_TTL_SECONDS:
        return jsonify(cached['data'])

    try:
        response = requests.get(ABC_MUSIC_API, params={'station': slug, 'limit': 1}, timeout=10)
        response.raise_for_status()
        items = response.json().get('items', [])
        summary = items[0]['summary'] if items else {}
        data = {'artist': summary.get('artist'), 'title': summary.get('title')}
    except (requests.RequestException, ValueError, KeyError, IndexError):
        data = {'artist': None, 'title': None}

    _now_playing_cache[station_id] = {'data': data, 'fetched_at': now}
    return jsonify(data)
