import unittest
from pathlib import Path


class StaticUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).parents[1] / "app/static/index.html").read_text()

    def test_requested_check_labels_are_used(self):
        self.assertIn("beam_http: 'Beam HTTP'", self.html)
        self.assertIn("beam_quic: 'Beam QUIC'", self.html)
        self.assertIn("aperture_txstream_grpc: 'Aperture TxStream'", self.html)
        self.assertNotIn("Aperture TxStream gRPC", self.html)

    def test_simulation_is_summarized_in_the_aperture_card(self):
        self.assertNotIn("class=\"nested-check\"", self.html)
        self.assertNotIn("<span class=\"check-name\">Simulation</span>", self.html)
        self.assertIn("simulationSummaryData(simulation)", self.html)
        self.assertIn("['Simulations'", self.html)
        self.assertIn("['Simulation Service Errors'", self.html)
        self.assertIn("renderApertureCard()", self.html)

    def test_beam_transports_share_one_card(self):
        self.assertIn("ensureCard('beam')", self.html)
        self.assertIn("renderBeamCard()", self.html)
        self.assertNotIn("renderStandardCard(name, checkStates[name]);\n  } else if (name === 'beam_http'", self.html)
