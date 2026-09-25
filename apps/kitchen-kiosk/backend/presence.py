"""Wi-Fi presence detection via the host's ARP table - checks whether any
known phone MAC is currently associated with the network.

Reads /host/proc/net/arp (the host's whole /proc tree, mounted read-only at
/host/proc) rather than shelling out to the `arp` CLI, which isn't installed
in the python:3.11-slim base image and would otherwise require
network_mode: host (which conflicts with Traefik's container-name routing).

Note: the mount target is /host/proc, not /proc itself - modern Docker/runc
refuses to bind-mount anything directly into a container's own /proc."""
import os

from flask import Blueprint, jsonify

presence_bp = Blueprint('presence', __name__)

KNOWN_MACS = [m.strip().lower() for m in os.getenv('KIOSK_PRESENCE_KNOWN_MACS', '').split(',') if m.strip()]

# Overridable by tests via monkeypatching this module-level constant.
ARP_TABLE_PATH = '/host/proc/net/arp'


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

    try:
        output = _run_arp_scan().lower()
    except OSError:
        # ARP table unreadable (mount missing, permissions, etc.) - fail
        # open rather than wrongly forcing the kiosk to sleep.
        return jsonify({'anyone_home': True})

    anyone_home = any(mac in output for mac in KNOWN_MACS)
    return jsonify({'anyone_home': anyone_home})
