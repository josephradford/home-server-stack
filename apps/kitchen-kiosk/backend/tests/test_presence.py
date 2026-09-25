ARP_OUTPUT = """IP address       HW type     Flags       HW address            Mask     Device
192.168.1.10     0x1         0x2         aa:bb:cc:dd:ee:01     *        eth0
192.168.1.11     0x1         0x2         aa:bb:cc:dd:ee:02     *        eth0
"""


def test_presence_true_when_known_mac_present(client, mocker):
    mocker.patch('presence.KNOWN_MACS', ['aa:bb:cc:dd:ee:01'])
    mocker.patch('presence._run_arp_scan', return_value=ARP_OUTPUT)

    response = client.get('/api/presence')

    assert response.status_code == 200
    assert response.get_json() == {'anyone_home': True}


def test_presence_false_when_no_known_mac_present(client, mocker):
    mocker.patch('presence.KNOWN_MACS', ['aa:bb:cc:dd:ee:99'])
    mocker.patch('presence._run_arp_scan', return_value=ARP_OUTPUT)

    response = client.get('/api/presence')

    assert response.get_json() == {'anyone_home': False}


def test_presence_defaults_to_home_when_unconfigured(client, mocker):
    # No MACs configured means presence detection is off - never force sleep.
    mocker.patch('presence.KNOWN_MACS', [])

    response = client.get('/api/presence')

    assert response.get_json() == {'anyone_home': True}


def test_run_arp_scan_parses_proc_net_arp(tmp_path, mocker):
    import presence

    arp_file = tmp_path / 'arp'
    arp_file.write_text(ARP_OUTPUT)
    mocker.patch('presence.ARP_TABLE_PATH', str(arp_file))

    result = presence._run_arp_scan()

    assert 'aa:bb:cc:dd:ee:01' in result
    assert 'aa:bb:cc:dd:ee:02' in result
    assert 'IP address' not in result
