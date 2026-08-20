import unittest

import grpc

from app.checks.aperture_txstream import (
    SIMULATION_PLAN_DENIAL,
    TXSTREAM_ACCOUNT_INCLUDE,
    build_subscribe_request,
    classify_simulation_health,
    is_simulation_plan_denial,
)


class FakeRpcError:
    def __init__(self, code, details):
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


class ApertureSimulationTests(unittest.TestCase):
    def test_account_include_is_a_solana_pubkey(self):
        import base58

        self.assertEqual(len(base58.b58decode(TXSTREAM_ACCOUNT_INCLUDE)), 32)

    def test_base_and_simulation_requests_use_the_same_account_filter(self):
        base_request = build_subscribe_request(False)
        simulation_request = build_subscribe_request(True)

        self.assertEqual(base_request.account_include, simulation_request.account_include)
        self.assertTrue(base_request.signatures_only)
        self.assertFalse(base_request.include_simulation)
        self.assertTrue(simulation_request.include_simulation)

    def test_transaction_failure_still_proves_simulation_is_operational(self):
        status, reason, message, service_errors = classify_simulation_health(
            1,
            1,
            {"SIMULATION_STATUS_FAILED": 1},
        )
        self.assertEqual((status, reason, message, service_errors), ("ok", None, None, 0))

    def test_all_service_failures_report_simulation_as_unhealthy(self):
        status, reason, _, service_errors = classify_simulation_health(
            2,
            2,
            {"SIMULATION_STATUS_INTERNAL_ERROR": 2},
        )
        self.assertEqual(status, "error")
        self.assertEqual(reason, "simulation_unhealthy")
        self.assertEqual(service_errors, 2)

    def test_mixed_service_results_report_partial_failure(self):
        status, reason, _, service_errors = classify_simulation_health(
            2,
            2,
            {
                "SIMULATION_STATUS_SUCCEEDED": 1,
                "SIMULATION_STATUS_SERVER_OVERLOADED": 1,
            },
        )
        self.assertEqual(status, "warning")
        self.assertEqual(reason, "simulation_partially_unhealthy")
        self.assertEqual(service_errors, 1)

    def test_exact_plan_denial_is_classified_as_auth_not_service_failure(self):
        error = FakeRpcError(grpc.StatusCode.PERMISSION_DENIED, SIMULATION_PLAN_DENIAL)
        self.assertTrue(is_simulation_plan_denial(error))

    def test_other_permission_denial_is_not_misclassified(self):
        error = FakeRpcError(
            grpc.StatusCode.PERMISSION_DENIED,
            "TxStream is not available for your plan",
        )
        self.assertFalse(is_simulation_plan_denial(error))
