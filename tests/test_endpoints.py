import unittest

from app.endpoints import resolve_endpoints


class EndpointTests(unittest.TestCase):
    def test_mainnet_saas_includes_aperture_and_beam(self):
        endpoints = resolve_endpoints("saas")

        self.assertEqual(
            endpoints.aperture_txstream_grpc,
            "aperture-txstream.rpcfast.com:443",
        )
        self.assertEqual(endpoints.beam_http, "https://beam.rpcfast.com")
        self.assertEqual(endpoints.beam_quic, "beam.rpcfast.com:9900")

    def test_unsupported_endpoint_types_skip_aperture_and_beam(self):
        for endpoint_type, client_id in (
            ("saas-devnet", None),
            ("dedicated", "client"),
        ):
            with self.subTest(endpoint_type=endpoint_type):
                endpoints = resolve_endpoints(endpoint_type, client_id)
                self.assertEqual(endpoints.aperture_txstream_grpc, "")
                self.assertEqual(endpoints.beam_http, "")
                self.assertEqual(endpoints.beam_quic, "")
