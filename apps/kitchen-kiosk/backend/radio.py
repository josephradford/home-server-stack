"""Static radio station presets — no auth, no proxying of the stream itself."""
from flask import Blueprint, jsonify

radio_bp = Blueprint('radio', __name__)

# Stream URLs are ABC/Double J's public HLS/MP3 endpoints - no account needed.
STATIONS = [
    {'id': 'abc-cricket', 'name': 'ABC Cricket', 'stream_url': 'https://live-radio01.mediahubaustralia.com/2LRW/mp3/'},
    {'id': 'abc-classic', 'name': 'ABC Classic', 'stream_url': 'https://live-radio01.mediahubaustralia.com/2FMW/mp3/'},
    {'id': 'double-j', 'name': 'Double J', 'stream_url': 'https://live-radio01.mediahubaustralia.com/2DJW/mp3/'},
    {'id': 'abc-jazz', 'name': 'ABC Jazz', 'stream_url': 'https://live-radio01.mediahubaustralia.com/2JZW/mp3/'},
]


@radio_bp.route('/api/radio/stations')
def stations():
    return jsonify({'stations': STATIONS})
