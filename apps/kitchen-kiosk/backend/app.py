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

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100)
