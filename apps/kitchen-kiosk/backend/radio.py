"""Static radio station presets — no auth, no proxying of the stream itself."""
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


@radio_bp.route('/api/radio/stations')
def stations():
    return jsonify({'stations': STATIONS})
