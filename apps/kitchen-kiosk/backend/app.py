"""
Kitchen Kiosk Backend API
Aggregates weather, calendar, photos, recipes, and radio presets
for the kitchen kiosk frontend.
"""
import os

from flask import Flask, jsonify


def create_app():
    app = Flask(__name__)

    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'healthy'})

    @app.route('/api/config')
    def config():
        return jsonify({
            'sleep_start': os.getenv('KIOSK_SLEEP_START', '23:00'),
            'sleep_end': os.getenv('KIOSK_SLEEP_END', '07:00'),
        })

    from radio import radio_bp
    app.register_blueprint(radio_bp)

    from weather import weather_bp
    app.register_blueprint(weather_bp)

    from calendar_feed import calendar_bp
    app.register_blueprint(calendar_bp)

    from recipes import recipes_bp
    app.register_blueprint(recipes_bp)

    from photos import photos_bp
    app.register_blueprint(photos_bp)

    from presence import presence_bp
    app.register_blueprint(presence_bp)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100)
