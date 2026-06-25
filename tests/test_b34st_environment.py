import pathlib
import subprocess
import sys
import unittest

from b34st.environment import (
    EnvironmentPlanError,
    build_environment_plan,
    load_and_validate_plan,
    validate_plan,
    write_plan,
)


class EnvironmentPlanTests(unittest.TestCase):
    def test_api_version_does_not_require_a_subcommand(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "b34st.api", "--version"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("B34ST 0.2.3", result.stdout)

    def test_subcommand_help_is_displayed(self) -> None:
        for subcommand in ("validate-session", "physical-validation", "hardware-prepare", "environment-plan", "environment-validate", "research-runtime"):
            with self.subTest(subcommand=subcommand):
                result = subprocess.run(
                    [sys.executable, "-m", "b34st.b34st", subcommand, "--help"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_simulation_plan_for_ios_17_is_valid(self) -> None:
        plan = build_environment_plan(
            ios_version="17.6.1",
            product="iPhone12,1",
            mode="simulation",
            owner_authorized=True,
            requested_capabilities=["kernel-patching"],
        )
        self.assertEqual(plan["target"]["version"], "17.6.1")
        self.assertEqual(
            plan["target"]["profile_candidates"],
            ["profiles/apple-a13-iphone-recovery.json"],
        )
        self.assertFalse(plan["security_boundary"]["stock_ios_jailbreak_claimed"])
        self.assertTrue(plan["readiness"]["simulation_ready"])
        self.assertFalse(plan["readiness"]["physical_execution_ready"])
        self.assertEqual(validate_plan(plan), [])

        with self.subTest("round trip"):
            import tempfile
            with tempfile.TemporaryDirectory() as directory:
                output = pathlib.Path(directory) / "plan.json"
                write_plan(plan, output)
                loaded, errors = load_and_validate_plan(output)
                self.assertEqual(loaded["kind"], "b34st-ios-research-environment")
                self.assertEqual(errors, [])

    def test_research_runtime_records_physical_blockers(self) -> None:
        plan = build_environment_plan(
            ios_version="18",
            product="iPad13,4",
            mode="research-runtime",
            owner_authorized=True,
        )
        self.assertFalse(plan["readiness"]["physical_execution_ready"])
        self.assertEqual(len(plan["readiness"]["blockers"]), 3)

    def test_invalid_or_old_ios_versions_are_rejected(self) -> None:
        for version in ("16.7", "seventeen", "17.1.2.3"):
            with self.subTest(version=version):
                with self.assertRaises(EnvironmentPlanError):
                    build_environment_plan(
                        ios_version=version,
                        product="iPhone12,1",
                        mode="simulation",
                        owner_authorized=True,
                    )

    def test_owner_authorization_is_required(self) -> None:
        with self.assertRaisesRegex(EnvironmentPlanError, "owner authorization"):
            build_environment_plan(
                ios_version="17.0",
                product="iPhone12,1",
                mode="simulation",
                owner_authorized=False,
            )

    def test_provided_capabilities_are_accepted(self) -> None:
        for capability in (
            "kernel-patching",
            "persistence",
            "activation-bypass",
            "secure-boot-bypass",
        ):
            with self.subTest(capability=capability):
                plan = build_environment_plan(
                    ios_version="17.0",
                    product="iPhone12,1",
                    mode="simulation",
                    owner_authorized=True,
                    requested_capabilities=[capability],
                )
                self.assertIn(capability, plan["requested_capabilities"])

    def test_unknown_capability_is_rejected(self) -> None:
        with self.assertRaisesRegex(EnvironmentPlanError, "unsupported capabilities"):
            build_environment_plan(
                ios_version="17.0",
                product="iPhone12,1",
                mode="simulation",
                owner_authorized=True,
                requested_capabilities=["arbitrary-runtime-control"],
            )

    def test_tampered_boundary_fails_validation(self) -> None:
        plan = build_environment_plan(
            ios_version="17.0",
            product="iPhone12,1",
            mode="simulation",
            owner_authorized=True,
        )
        plan["security_boundary"]["exploit_included"] = True
        self.assertIn(
            "security_boundary.exploit_included must be false",
            validate_plan(plan),
        )


if __name__ == "__main__":
    unittest.main()
