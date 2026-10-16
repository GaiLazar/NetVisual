"""Unit and regression tests for NetVisual A+ v6 mega features suite."""
from __future__ import annotations

import unittest
from netvisual import probes, portscan, firewall, history, export, netprofiles


class TestV6MegaFeatures(unittest.TestCase):
    def test_process_bandwidth_probe(self):
        res = probes.probe_process_bandwidth()
        self.assertIn("processes", res)
        self.assertIn("total_rx_bps", res)
        self.assertIn("total_tx_bps", res)
        self.assertIsInstance(res["processes"], list)
        if res["processes"]:
            p = res["processes"][0]
            self.assertIn("process", p)
            self.assertIn("pct", p)
            self.assertIn("total_bps", p)

    def test_portscan_risk_evaluation(self):
        res = portscan.portscan("127.0.0.1", [80, 443, 8730])
        self.assertIn("ports", res)
        self.assertIn("risk_summary", res)
        self.assertIn(res["risk_summary"], ("CRITICAL", "HIGH", "MEDIUM", "SAFE"))
        for p in res["ports"]:
            self.assertIn("service", p)
            self.assertIn("risk", p)
            self.assertIn("open", p)

    def test_firewall_rule_helpers(self):
        blocked = firewall.list_blocked_programs()
        self.assertIsInstance(blocked, list)
        # Verify validation error on empty path
        err_res = firewall.block_application("")
        self.assertFalse(err_res["ok"])

    def test_export_csv_generators(self):
        # Devices CSV
        devs = [{"ip": "192.168.1.1", "mac": "00:11:22:33:44:55", "vendor": "Router Inc", "reach": True}]
        csv_devs = export.export_devices_csv(devs)
        self.assertIn("192.168.1.1", csv_devs)
        self.assertIn("Router Inc", csv_devs)
        
        # Connections CSV
        conns = [{"proto": "TCP", "local": "127.0.0.1:8730", "remote": "0.0.0.0:0", "state": "LISTENING", "pid": 1234, "process": "netvisual.exe"}]
        csv_conns = export.export_connections_csv(conns)
        self.assertIn("127.0.0.1:8730", csv_conns)
        self.assertIn("netvisual.exe", csv_conns)

        # Packets CSV
        pkts = [{"id": 1, "src_ip": "10.0.0.1", "dst_ip": "1.1.1.1", "proto": "DNS", "length": 64, "summary": "Query google.com"}]
        csv_pkts = export.export_packets_csv(pkts)
        self.assertIn("10.0.0.1", csv_pkts)
        self.assertIn("google.com", csv_pkts)

    def test_history_known_devices_tracking(self):
        history.init()
        devs = [{"ip": "192.168.1.99", "mac": "AA:BB:CC:DD:EE:FF", "vendor": "TestLab"}]
        enriched, new_devs = history.track_known_devices(devs)
        self.assertEqual(len(enriched), 1)
        self.assertIn("is_new", enriched[0])
        
        # Acknowledge device
        ack = history.acknowledge_device("AA:BB:CC:DD:EE:FF")
        self.assertTrue(ack)

    def test_profile_ssid_structure(self):
        profs = netprofiles.load_profiles()
        self.assertGreaterEqual(len(profs), 1)
        self.assertIn("associated_ssid", profs[0])


if __name__ == "__main__":
    unittest.main()
