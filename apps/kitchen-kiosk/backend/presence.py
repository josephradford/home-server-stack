"""Wi-Fi presence detection via the host's ARP table - checks whether any
known phone MAC is currently associated with the network.

Reads /proc/net/arp directly (mounted read-only into the container) rather
than shelling out to the `arp` CLI, which isn't installed in the
python:3.11-slim base image and would otherwise require network_mode: host
(which conflicts with Traefik's container-name routing)."""
import os

from flask import Blueprint, jsonify

presence_bp = Blueprint('presence', __name__)

KNOWN_MACS = [m.strip().lower() for m in os.getenv('KIOSK_PRESENCE_KNOWN_MACS', '').split(',') if m.strip()]

# Overridable by tests via monkeypatching this module-level constant.
ARP_TABLE_PATH = '/proc/net/arp'


def _run_arp_scan():
    """Read the host's ARP table and return the whitespace-separated HW
    address (column index 3) from each row, one per line."""
    with open(ARP_TABLE_PATH) as f:
        lines = f.readlines()

    macs = []
    for line in lines[1:]:  # skip header row
        fields = line.split()
        if len(fields) > 3:
            macs.append(fields[3])
    return '\n'.join(macs)


@presence_bp.route('/api/presence')
def presence():
    if not KNOWN_MACS:
        # Presence detection is opt-in; unconfigured means never force sleep.
        return jsonify({'anyone_home': True})

    output = _run_arp_scan().lower()
    anyone_home = any(mac in output for mac in KNOWN_MACS)
    return jsonify({'anyone_home': anyone_home})
