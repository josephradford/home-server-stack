"""
Kitchen Kiosk Backend API
Aggregates weather, calendar, photos, recipes, and radio presets
for the kitchen kiosk frontend.

Feature request (not built): shopping list
------------------------------------------
We currently track "what to buy next shop" in Google Keep and would like it on
the kiosk. Considered 2026-10, deferred because of:

- Google Keep has no usable API for personal accounts. The official Keep API
  is Workspace-enterprise/admin only (OAuth requests fail with invalid_scope).
  The only route is the unofficial, reverse-engineered `gkeepapi`, which needs
  a master token with full access to the Google account and can break without
  notice. Not worth the security and fragility trade-off.
- Google Tasks has an official API that works with personal accounts (OAuth
  refresh token in .env), but it is a separate store: the Keep list would have
  to be migrated and everyone would switch to the Tasks app.
- A self-hosted list avoids Google entirely but needs writable storage (this
  service has none; the only volume is the read-only recipes mount) and a
  phone-friendly page for use in the shop (reachable over the UDR7 VPN).

Open decision: stay on Keep (no kiosk integration), move to Google Tasks, or
self-host. Revisit once that is decided.
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
