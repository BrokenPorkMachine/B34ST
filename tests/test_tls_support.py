from __future__ import annotations

import pathlib
import unittest
from unittest import mock

from host import tls_support


class TLSSupportTests(unittest.TestCase):
    def test_find_ca_bundle_skips_missing_candidates(self) -> None:
        existing = pathlib.Path(__file__)
        with mock.patch.object(
            tls_support,
            "_candidate_ca_bundles",
            return_value=iter((pathlib.Path("/missing/ca.pem"), existing)),
        ):
            self.assertEqual(tls_support.find_ca_bundle(), existing.resolve())

    def test_tls_context_loads_verified_certificates(self) -> None:
        ok, path, detail = tls_support.tls_ca_status()
        self.assertTrue(ok, detail)
        self.assertIsNotNone(path)
        self.assertIn("trusted CA certificates loaded", detail)
