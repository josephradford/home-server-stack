"""
Kitchen Kiosk Backend API
Aggregates weather, calendar, photos, recipes, and radio presets
for the kitchen kiosk frontend.
"""
from flask import Flask, jsonify
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    CORS(app)

    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'healthy'})

    from radio import radio_bp
    app.register_blueprint(radio_bp)

    from weather import weather_bp
    app.register_blueprint(weather_bp)

    from calendar_feed import calendar_bp
    app.register_blueprint(calendar_bp)

    from recipes import recipes_bp
    app.register_blueprint(recipes_bp)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100)
