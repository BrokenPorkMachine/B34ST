#!/usr/bin/env python3
"""Tests for B34ST CVE database, exploit chain planner, and fuzzer modules."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CVE_DATA = ROOT / "host" / "cve" / "data" / "cve_database.json"


# =============================================================================
# VersionRange tests
# =============================================================================

class TestVersionRange(unittest.TestCase):
    def test_contains_exact_match(self):
        from host.cve.cve_db import VersionRange
        vr = VersionRange(start="14.0", end="14.8")
        self.assertTrue(vr.contains("14.0"))
        self.assertTrue(vr.contains("14.8"))

    def test_contains_inside_range(self):
        from host.cve.cve_db import VersionRange
        vr = VersionRange(start="14.0", end="14.8")
        self.assertTrue(vr.contains("14.4"))
        self.assertTrue(vr.contains("14.8"))

    def test_contains_below_start(self):
        from host.cve.cve_db import VersionRange
        vr = VersionRange(start="14.0", end="14.8")
        self.assertFalse(vr.contains("13.4"))
        self.assertFalse(vr.contains("9.0"))

    def test_contains_above_end(self):
        from host.cve.cve_db import VersionRange
        vr = VersionRange(start="14.0", end="14.8")
        self.assertFalse(vr.contains("15.0"))
        self.assertFalse(vr.contains("14.9"))

    def test_contains_no_end(self):
        from host.cve.cve_db import VersionRange
        vr = VersionRange(start="14.0")
        self.assertTrue(vr.contains("14.0"))
        self.assertTrue(vr.contains("16.0"))
        self.assertTrue(vr.contains("99.0"))
        self.assertFalse(vr.contains("13.0"))

    def test_contains_single_version(self):
        from host.cve.cve_db import VersionRange
        vr = VersionRange(start="16.5", end="16.5")
        self.assertTrue(vr.contains("16.5"))
        self.assertFalse(vr.contains("16.5.1"))
        self.assertFalse(vr.contains("16.4"))

    def test_contains_three_part_versions(self):
        from host.cve.cve_db import VersionRange
        vr = VersionRange(start="14.0", end="14.8.1")
        self.assertTrue(vr.contains("14.8.1"))
        self.assertTrue(vr.contains("14.4"))
        self.assertTrue(vr.contains("14.0"))
        self.assertFalse(vr.contains("14.9"))

    def test_contains_very_long_version_string(self):
        from host.cve.cve_db import VersionRange
        vr = VersionRange(start="10.0")
        self.assertTrue(vr.contains("10.0.0.0"))
        self.assertTrue(vr.contains("11.0.0.1"))


# =============================================================================
# CVE dataclass tests
# =============================================================================

class TestCVEDataclass(unittest.TestCase):
    def test_create_minimal_cve(self):
        from host.cve.cve_db import CVE, VersionRange
        cve = CVE(
            id="CVE-2024-0001",
            description="Test vulnerability",
            affected_versions=(VersionRange(start="14.0", end="14.8"),),
            affected_components=("kernel",),
            exploit_type=("local",),
            exploit_available=True,
            goals=("kernel-rw", "root-privesc"),
        )
        self.assertEqual(cve.id, "CVE-2024-0001")
        self.assertEqual(cve.severity, "high")
        self.assertEqual(cve.published, "")
        self.assertEqual(cve.mitigations, ())
        self.assertTrue(cve.exploit_available)

    def test_create_full_cve(self):
        from host.cve.cve_db import CVE, VersionRange
        cve = CVE(
            id="CVE-2024-0002",
            description="Full test CVE",
            affected_versions=(
                VersionRange(start="15.0", end="15.7"),
                VersionRange(start="16.0", end="16.5"),
            ),
            affected_components=("kernel", "iokit"),
            exploit_type=("local", "lpe"),
            exploit_available=False,
            goals=("codesign-bypass", "kernel-rw", "root-privesc"),
            chainable_with=("CVE-2024-0001",),
            mitigations=("pac",),
            patch_version="16.5.1",
            severity="critical",
            published="2024-01-15",
            references=("https://example.com",),
            credits=("researcher",),
            exploit_path="exploits/kernel/test.c",
        )
        self.assertEqual(cve.severity, "critical")
        self.assertEqual(cve.patch_version, "16.5.1")
        self.assertFalse(cve.exploit_available)
        self.assertEqual(len(cve.affected_versions), 2)


# =============================================================================
# CVEDatabase tests
# =============================================================================

class TestCVEDatabase(unittest.TestCase):
    def setUp(self):
        from host.cve.cve_db import CVEDatabase
        self.db = CVEDatabase()

    def test_empty_database(self):
        from host.cve.cve_db import CVE, VersionRange
        self.assertEqual(self.db.count, 0)
        self.assertEqual(self.db.all_cves, ())
        self.assertEqual(self.db.query_by_version("16.0"), ())
        self.assertEqual(self.db.query_by_goal("kernel-rw"), ())
        self.assertEqual(self.db.query_by_component("webkit"), ())
        self.assertEqual(self.db.query_by_severity("critical"), ())
        self.assertEqual(self.db.query_exploit_available(), ())
        self.assertEqual(self.db.search("test"), ())
        self.assertEqual(self.db.filter(), ())
        stats = self.db.compute_stats()
        self.assertEqual(stats["total_cves"], 0)
        self.assertEqual(stats["exploit_available"], 0)

    def test_add_and_count(self):
        from host.cve.cve_db import CVE, VersionRange
        cve = CVE(
            id="CVE-2024-TEST",
            description="test",
            affected_versions=(VersionRange(start="14.0"),),
            affected_components=("kernel",),
            exploit_type=("local",),
            exploit_available=False,
            goals=("kernel-rw",),
        )
        self.db.add(cve)
        self.assertEqual(self.db.count, 1)
        self.assertEqual(len(self.db.all_cves), 1)

    def test_add_duplicate_id_overwrites(self):
        from host.cve.cve_db import CVE, VersionRange
        cve1 = CVE(
            id="CVE-2024-TEST",
            description="first",
            affected_versions=(VersionRange(start="14.0"),),
            affected_components=("kernel",),
            exploit_type=("local",),
            exploit_available=False,
            goals=("kernel-rw",),
        )
        cve2 = CVE(
            id="CVE-2024-TEST",
            description="second",
            affected_versions=(VersionRange(start="15.0"),),
            affected_components=("webkit",),
            exploit_type=("remote",),
            exploit_available=True,
            goals=("initial-access",),
        )
        self.db.add(cve1)
        self.db.add(cve2)
        self.assertEqual(self.db.count, 1)
        self.assertEqual(self.db.all_cves[0].description, "second")

    def test_add_from_dict(self):
        data = {
            "id": "CVE-2024-FROMDICT",
            "description": "added from dict",
            "affected_versions": [{"start": "14.0", "end": "14.8"}],
            "affected_components": ["kernel"],
            "exploit_type": ["local", "lpe"],
            "exploit_available": True,
            "goals": ["kernel-rw", "root-privesc"],
            "chainable_with": [],
            "mitigations": [],
            "patch_version": "14.8",
            "severity": "critical",
            "published": "2024-01-01",
            "references": [],
            "credits": [],
            "exploit_path": None,
        }
        self.db.add_from_dict(data)
        self.assertEqual(self.db.count, 1)
        cve = self.db.all_cves[0]
        self.assertEqual(cve.id, "CVE-2024-FROMDICT")
        self.assertEqual(cve.severity, "critical")
        self.assertTrue(cve.exploit_available)

    def test_add_from_dict_minimal(self):
        data = {
            "id": "CVE-2024-MIN",
            "affected_versions": [{"start": "14.0"}],
            "affected_components": ["kernel"],
            "exploit_type": ["local"],
            "goals": ["kernel-rw"],
        }
        self.db.add_from_dict(data)
        cve = self.db.all_cves[0]
        self.assertEqual(cve.description, "")
        self.assertEqual(cve.severity, "high")
        self.assertFalse(cve.exploit_available)

    def test_load_json_from_real_file(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        self.assertGreater(db.count, 100)
        self.assertEqual(len(db.all_cves), db.count)

    def test_save_json_roundtrip(self):
        from host.cve.cve_db import CVEDatabase, CVE, VersionRange
        cve = CVE(
            id="CVE-2024-ROUNDTRIP",
            description="roundtrip test",
            affected_versions=(VersionRange(start="16.0", end="16.5"),),
            affected_components=("webkit",),
            exploit_type=("remote", "rce"),
            exploit_available=True,
            goals=("web-content-rce",),
            severity="critical",
        )
        self.db.add(cve)
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "cves.json"
            self.db.save_json(p)
            self.assertTrue(p.is_file())
            loaded = CVEDatabase.load_json(p)
            self.assertEqual(loaded.count, 1)
            self.assertEqual(loaded.all_cves[0].id, "CVE-2024-ROUNDTRIP")
            self.assertTrue(loaded.all_cves[0].exploit_available)

    def test_save_json_roundtrip_with_multiple(self):
        from host.cve.cve_db import CVEDatabase, CVE, VersionRange
        cve1 = CVE(
            id="CVE-2024-A",
            description="A",
            affected_versions=(VersionRange(start="14.0"),),
            affected_components=("kernel",),
            exploit_type=("local",),
            exploit_available=False,
            goals=("kernel-rw",),
            severity="high",
        )
        cve2 = CVE(
            id="CVE-2024-B",
            description="B",
            affected_versions=(VersionRange(start="15.0", end="15.5"),),
            affected_components=("webkit",),
            exploit_type=("remote",),
            exploit_available=True,
            goals=("initial-access",),
            severity="critical",
        )
        self.db.add(cve1)
        self.db.add(cve2)
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "cves.json"
            self.db.save_json(p)
            data = json.loads(p.read_text())
            self.assertEqual(data["schema"], "cve-database-v1")
            self.assertEqual(data["cve_count"], 2)
            loaded = CVEDatabase.load_json(p)
            self.assertEqual(loaded.count, 2)
            ids = {c.id for c in loaded.all_cves}
            self.assertIn("CVE-2024-A", ids)
            self.assertIn("CVE-2024-B", ids)

    def test_query_by_version_real_data(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_version("16.5")
        self.assertGreater(len(results), 0)
        for cve in results:
            found = any(vr.contains("16.5") for vr in cve.affected_versions)
            self.assertTrue(found, f"{cve.id} should affect 16.5")

    def test_query_by_version_no_results(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_version("0.1")
        self.assertEqual(len(results), 0)

    def test_query_by_goal_without_version(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_goal("kernel-rw")
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn("kernel-rw", cve.goals)

    def test_query_by_goal_with_version(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_goal("kernel-rw", version="16.5")
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn("kernel-rw", cve.goals)

    def test_query_by_goal_no_match(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_goal("nonexistent-goal-xyz")
        self.assertEqual(len(results), 0)

    def test_query_by_component(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_component("webkit")
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn("webkit", cve.affected_components)

    def test_query_by_component_with_version(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_component("webkit", version="16.5")
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn("webkit", cve.affected_components)

    def test_query_by_component_no_match(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_component("nonexistent-component")
        self.assertEqual(len(results), 0)

    def test_query_by_severity(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_severity("critical")
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertEqual(cve.severity, "critical")

    def test_query_by_severity_no_match(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_by_severity("nonexistent-severity")
        self.assertEqual(len(results), 0)

    def test_query_exploit_available(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_exploit_available()
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertTrue(cve.exploit_available)

    def test_query_exploit_available_with_version(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.query_exploit_available(version="16.5")
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertTrue(cve.exploit_available)

    def test_search_by_id(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.search("CVE-2023-32364")
        self.assertGreater(len(results), 0)
        self.assertTrue(any("CVE-2023-32364" in c.id for c in results))

    def test_search_by_description_keyword(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.search("webkit")
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertTrue(
                "webkit" in cve.id.lower() or "webkit" in cve.description.lower()
            )

    def test_search_no_match(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.search("XYZZYX_NOMATCH_12345")
        self.assertEqual(len(results), 0)

    def test_filter_by_version(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.filter(version="16.5")
        self.assertGreater(len(results), 0)

    def test_filter_by_goals(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.filter(goals={"kernel-rw"})
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn("kernel-rw", cve.goals)

    def test_filter_by_components(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.filter(components={"webkit"})
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn("webkit", cve.affected_components)

    def test_filter_by_exploit_types(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.filter(exploit_types={"lpe"})
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn("lpe", cve.exploit_type)

    def test_filter_exploit_available(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.filter(exploit_available=True)
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertTrue(cve.exploit_available)
        results_false = db.filter(exploit_available=False)
        self.assertEqual(len(results_false), 0)

    def test_filter_min_severity_critical(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.filter(min_severity="critical")
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn(cve.severity, ("critical",))

    def test_filter_min_severity_high_includes_critical(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.filter(min_severity="high")
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn(cve.severity, ("critical", "high"))

    def test_filter_multiple_criteria(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.filter(
            version="16.5",
            goals={"kernel-rw"},
            components={"kernel"},
            exploit_available=True,
            min_severity="high",
        )
        self.assertGreater(len(results), 0)
        for cve in results:
            self.assertIn("kernel-rw", cve.goals)
            self.assertIn("kernel", cve.affected_components)
            self.assertTrue(cve.exploit_available)
            self.assertIn(cve.severity, ("critical", "high"))
            found = any(vr.contains("16.5") for vr in cve.affected_versions)
            self.assertTrue(found)

    def test_filter_no_match(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        results = db.filter(components={"nonexistent"})
        self.assertEqual(len(results), 0)

    def test_compute_stats_structure(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase.load_json(CVE_DATA)
        stats = db.compute_stats()
        self.assertIn("total_cves", stats)
        self.assertIn("exploit_available", stats)
        self.assertIn("by_severity", stats)
        self.assertIn("by_component", stats)
        self.assertIn("by_goal", stats)
        self.assertIn("by_exploit_type", stats)
        self.assertEqual(stats["total_cves"], db.count)
        self.assertGreater(stats["total_cves"], 0)
        self.assertGreater(stats["exploit_available"], 0)
        total_from_severity = sum(stats["by_severity"].values())
        self.assertEqual(total_from_severity, stats["total_cves"])

    def test_to_dict_roundtrip(self):
        from host.cve.cve_db import CVEDatabase, CVE, VersionRange
        cve = CVE(
            id="CVE-2024-TODICT",
            description="to_dict test",
            affected_versions=(VersionRange(start="16.0", end="16.5"),),
            affected_components=("webkit",),
            exploit_type=("remote",),
            exploit_available=True,
            goals=("initial-access",),
        )
        self.db.add(cve)
        d = self.db.to_dict()
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["id"], "CVE-2024-TODICT")
        self.assertEqual(d[0]["affected_versions"][0]["start"], "16.0")
        self.assertEqual(d[0]["affected_versions"][0]["end"], "16.5")


# =============================================================================
# ExploitGoal tests
# =============================================================================

class TestExploitGoal(unittest.TestCase):
    def test_is_achieved_by_exact_match(self):
        from host.cve.exploit_chain import ExploitGoal
        goal = ExploitGoal(
            name="test-goal",
            description="test",
            required_subgoals=("a", "b", "c"),
        )
        self.assertTrue(goal.is_achieved_by({"a", "b", "c"}))

    def test_is_achieved_by_superset(self):
        from host.cve.exploit_chain import ExploitGoal
        goal = ExploitGoal(
            name="test-goal",
            description="test",
            required_subgoals=("a", "b"),
        )
        self.assertTrue(goal.is_achieved_by({"a", "b", "c", "d"}))

    def test_is_achieved_by_not_met(self):
        from host.cve.exploit_chain import ExploitGoal
        goal = ExploitGoal(
            name="test-goal",
            description="test",
            required_subgoals=("a", "b", "c"),
        )
        self.assertFalse(goal.is_achieved_by({"a", "b"}))
        self.assertFalse(goal.is_achieved_by(set()))
        self.assertFalse(goal.is_achieved_by({"d", "e"}))

    def test_is_achieved_by_empty_requirements(self):
        from host.cve.exploit_chain import ExploitGoal
        goal = ExploitGoal(
            name="empty-goal",
            description="empty requirements",
            required_subgoals=(),
        )
        self.assertTrue(goal.is_achieved_by(set()))
        self.assertTrue(goal.is_achieved_by({"anything"}))


# =============================================================================
# ExploitChain tests
# =============================================================================

class TestExploitChain(unittest.TestCase):
    def setUp(self):
        from host.cve.cve_db import CVE, VersionRange
        from host.cve.exploit_chain import ExploitGoal, ChainLink
        self.goal = ExploitGoal(
            name="test-jailbreak",
            description="Test jailbreak",
            required_subgoals=("kernel-rw", "root-privesc", "codesign-bypass"),
            difficulty="hard",
        )
        self.cve1 = CVE(
            id="CVE-2024-KERNEL",
            description="Kernel rw",
            affected_versions=(VersionRange(start="16.0", end="16.5"),),
            affected_components=("kernel",),
            exploit_type=("local", "lpe"),
            exploit_available=True,
            goals=("kernel-rw", "root-privesc"),
            severity="critical",
        )
        self.cve2 = CVE(
            id="CVE-2024-CODESIGN",
            description="Codesign bypass",
            affected_versions=(VersionRange(start="16.0", end="16.5"),),
            affected_components=("kernel",),
            exploit_type=("local",),
            exploit_available=False,
            goals=("codesign-bypass",),
            severity="high",
        )

    def _make_chain(self, links=None):
        from host.cve.exploit_chain import ExploitChain, ChainLink
        if links is None:
            links = [
                ChainLink(cve=self.cve1, step=1, provides={"kernel-rw", "root-privesc"}),
                ChainLink(cve=self.cve2, step=2, provides={"codesign-bypass"}),
            ]
        return ExploitChain(
            goal=self.goal,
            target_version="16.5",
            links=links,
        )

    def test_coverage_complete(self):
        chain = self._make_chain()
        self.assertEqual(chain.coverage, 1.0)

    def test_coverage_partial(self):
        from host.cve.exploit_chain import ChainLink
        links = [
            ChainLink(cve=self.cve1, step=1, provides={"kernel-rw", "root-privesc"}),
        ]
        chain = self._make_chain(links=links)
        self.assertAlmostEqual(chain.coverage, 2 / 3)

    def test_coverage_empty_requirements(self):
        from host.cve.exploit_chain import ExploitGoal, ExploitChain
        goal = ExploitGoal(name="easy", description="easy", required_subgoals=())
        chain = ExploitChain(goal=goal, target_version="16.0", links=[])
        self.assertEqual(chain.coverage, 1.0)

    def test_coverage_zero(self):
        from host.cve.exploit_chain import ExploitChain, ChainLink
        cve = self.cve1
        goal_no_match = self.goal
        links = [ChainLink(cve=cve, step=1, provides={"unrelated"})]
        chain = ExploitChain(goal=goal_no_match, target_version="16.5", links=links)
        self.assertEqual(chain.coverage, 0.0)

    def test_complete_true(self):
        chain = self._make_chain()
        self.assertTrue(chain.complete)

    def test_complete_false(self):
        from host.cve.exploit_chain import ChainLink
        links = [ChainLink(cve=self.cve1, step=1, provides={"kernel-rw"})]
        chain = self._make_chain(links=links)
        self.assertFalse(chain.complete)

    def test_complete_empty_requirements(self):
        from host.cve.exploit_chain import ExploitGoal, ExploitChain
        goal = ExploitGoal(name="easy", description="easy", required_subgoals=())
        chain = ExploitChain(goal=goal, target_version="16.0", links=[])
        self.assertTrue(chain.complete)

    def test_estimate_difficulty_no_links(self):
        from host.cve.exploit_chain import ExploitChain
        chain = ExploitChain(goal=self.goal, target_version="16.5", links=[])
        self.assertEqual(chain.estimate_difficulty, "unknown")

    def test_estimate_difficulty_from_severity(self):
        chain = self._make_chain()
        self.assertEqual(chain.estimate_difficulty, "medium")

    def test_estimated_success_rate_no_links(self):
        from host.cve.exploit_chain import ExploitChain
        chain = ExploitChain(goal=self.goal, target_version="16.5", links=[])
        self.assertEqual(chain.estimated_success_rate, "0%")

    def test_estimated_success_rate_with_exploit_available(self):
        from host.cve.exploit_chain import ExploitChain, ChainLink
        from host.cve.cve_db import CVE, VersionRange
        cve = CVE(
            id="CVE-2024-TEST",
            description="test",
            affected_versions=(VersionRange(start="16.0"),),
            affected_components=("kernel",),
            exploit_type=("local",),
            exploit_available=True,
            goals=("kernel-rw",),
            severity="critical",
        )
        links = [ChainLink(cve=cve, step=1, provides={"kernel-rw"})]
        chain = ExploitChain(goal=self.goal, target_version="16.5", links=links)
        rate = chain.estimated_success_rate
        self.assertTrue(rate.endswith("%"))

    def test_to_dict_structure(self):
        chain = self._make_chain()
        d = chain.to_dict()
        self.assertEqual(d["goal"], "test-jailbreak")
        self.assertEqual(d["target_version"], "16.5")
        self.assertTrue(d["complete"])
        self.assertEqual(d["coverage"], 1.0)
        self.assertEqual(d["estimated_difficulty"], "medium")
        self.assertEqual(d["steps"], 2)
        self.assertIn("chain", d)
        self.assertEqual(len(d["chain"]), 2)
        self.assertEqual(d["chain"][0]["cve_id"], "CVE-2024-KERNEL")
        self.assertEqual(d["chain"][1]["cve_id"], "CVE-2024-CODESIGN")
        self.assertIn("created", d)

    def test_to_dict_partial_chain(self):
        from host.cve.exploit_chain import ExploitChain, ChainLink
        links = [ChainLink(cve=self.cve1, step=1, provides={"kernel-rw"})]
        chain = ExploitChain(goal=self.goal, target_version="16.5", links=links)
        d = chain.to_dict()
        self.assertFalse(d["complete"])
        self.assertAlmostEqual(d["coverage"], 1 / 3)

    def test_created_timestamp_set(self):
        from host.cve.exploit_chain import ExploitChain
        chain = ExploitChain(goal=self.goal, target_version="16.5", links=[])
        self.assertTrue(chain.created.endswith(":00") or "T" in chain.created)


# =============================================================================
# ChainPlanner tests
# =============================================================================

class TestChainPlanner(unittest.TestCase):
    def setUp(self):
        from host.cve.cve_db import CVEDatabase
        from host.cve.exploit_chain import ChainPlanner
        self.db = CVEDatabase.load_json(CVE_DATA)
        self.planner = ChainPlanner(self.db)

    def test_list_goals(self):
        goals = self.planner.list_goals()
        self.assertIn("jailbreak", goals)
        self.assertIn("jailbreak-from-app", goals)
        self.assertIn("jailbreak-remote", goals)
        self.assertIn("userland-jailbreak", goals)
        self.assertIn("extraction", goals)
        self.assertIn("activation-bypass", goals)
        self.assertIn("passcode-bypass", goals)
        self.assertIn("forensics-ready", goals)
        self.assertIn("tethered-jailbreak", goals)
        self.assertIn("initial-footing", goals)
        self.assertIn("lpe-root", goals)
        self.assertIn("persistent-jailbreak", goals)
        self.assertIn("checkm8-jailbreak", goals)
        self.assertIn("t2-compromise", goals)
        self.assertIn("m1-m2-compromise", goals)

    def test_list_goals_returns_descriptions(self):
        goals = self.planner.list_goals()
        for name, desc in goals.items():
            self.assertIsInstance(name, str)
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)

    def test_register_goal(self):
        from host.cve.exploit_chain import ExploitGoal
        new_goal = ExploitGoal(
            name="custom-goal",
            description="Custom goal",
            required_subgoals=("kernel-rw",),
            difficulty="easy",
        )
        self.planner.register_goal(new_goal)
        self.assertIn("custom-goal", self.planner.list_goals())

    def test_find_chains_jailbreak_16_5(self):
        chains = self.planner.find_chains("jailbreak", "16.5")
        self.assertGreater(len(chains), 0)
        for chain in chains:
            self.assertEqual(chain.goal.name, "jailbreak")
            self.assertEqual(chain.target_version, "16.5")

    def test_find_chains_jailbreak_16_5_complete(self):
        chains = self.planner.find_chains("jailbreak", "16.5")
        self.assertGreater(len(chains), 0)
        has_complete = any(c.complete for c in chains)
        self.assertTrue(has_complete)

    def test_find_chains_no_cves_for_version(self):
        chains = self.planner.find_chains("jailbreak", "99.0")
        self.assertEqual(len(chains), 0)

    def test_find_chains_unknown_goal_raises(self):
        from host.cve.exploit_chain import ChainPlannerError
        with self.assertRaises(ChainPlannerError):
            self.planner.find_chains("nonexistent-goal", "16.5")

    def test_find_chains_userland_jailbreak(self):
        chains = self.planner.find_chains("userland-jailbreak", "16.5")
        self.assertGreater(len(chains), 0)

    def test_find_chains_extraction(self):
        chains = self.planner.find_chains("extraction", "16.5")
        self.assertGreater(len(chains), 0)

    def test_find_chains_require_exploit_available(self):
        chains = self.planner.find_chains("jailbreak", "16.5", require_exploit_available=True)
        self.assertGreater(len(chains), 0)
        for chain in chains:
            for link in chain.links:
                self.assertTrue(link.cve.exploit_available)

    def test_find_chains_with_max_chain_length(self):
        chains = self.planner.find_chains("jailbreak", "16.5", max_chain_length=1)
        for chain in chains:
            self.assertLessEqual(len(chain.links), 1)

    def test_find_all_possible_chains(self):
        results = self.planner.find_all_possible_chains("16.5")
        self.assertIsInstance(results, dict)
        self.assertGreater(len(results), 0)
        for goal_name, chains in results.items():
            self.assertGreater(len(chains), 0)

    def test_find_all_possible_chains_no_matches(self):
        results = self.planner.find_all_possible_chains("99.0")
        self.assertEqual(len(results), 0)

    def test_suggest_goals(self):
        suggestions = self.planner.suggest_goals("16.5")
        self.assertGreater(len(suggestions), 0)
        for s in suggestions:
            self.assertIn("goal", s)
            self.assertIn("description", s)
            self.assertIn("achievable", s)
            self.assertIn("coverage", s)
            self.assertIn("difficulty", s)
            self.assertIn("success_rate", s)
            self.assertIn("steps", s)
            self.assertIn("cves", s)

    def test_suggest_goals_sorted_by_achievable_then_difficulty(self):
        suggestions = self.planner.suggest_goals("16.5")
        for i in range(len(suggestions) - 1):
            s1 = suggestions[i]
            s2 = suggestions[i + 1]
            if s1["achievable"] != s2["achievable"]:
                self.assertTrue(s1["achievable"])
            else:
                diff_order = {"easy": 0, "medium": 1, "hard": 2, "extreme": 3}
                self.assertLessEqual(
                    diff_order.get(s1["difficulty"], 99),
                    diff_order.get(s2["difficulty"], 99),
                )

    def test_suggest_goals_no_version(self):
        suggestions = self.planner.suggest_goals("99.0")
        self.assertEqual(len(suggestions), 0)

    def test_chain_to_dict_serialization(self):
        chains = self.planner.find_chains("jailbreak", "16.5")
        self.assertGreater(len(chains), 0)
        d = chains[0].to_dict()
        json_str = json.dumps(d, indent=2)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["goal"], "jailbreak")
        self.assertEqual(parsed["target_version"], "16.5")

    def test_find_chains_extraction(self):
        chains = self.planner.find_chains("extraction", "16.5")
        self.assertGreater(len(chains), 0)


# =============================================================================
# BUILTIN_GOALS tests
# =============================================================================

class TestBuiltinGoals(unittest.TestCase):
    def test_has_all_expected_entries(self):
        from host.cve.exploit_chain import BUILTIN_GOALS
        expected = {
            "jailbreak",
            "jailbreak-from-app",
            "jailbreak-remote",
            "userland-jailbreak",
            "tethered-jailbreak",
            "extraction",
            "activation-bypass",
            "passcode-bypass",
            "forensics-ready",
            "initial-footing",
            "lpe-root",
            "persistent-jailbreak",
            "checkm8-jailbreak",
            "s5-jailbreak",
            "t2-compromise",
            "m1-m2-compromise",
        }
        self.assertEqual(set(BUILTIN_GOALS.keys()), expected)

    def test_all_goals_are_exploit_goal_instances(self):
        from host.cve.exploit_chain import BUILTIN_GOALS, ExploitGoal
        for goal in BUILTIN_GOALS.values():
            self.assertIsInstance(goal, ExploitGoal)

    def test_jailbreak_requires_correct_subgoals(self):
        from host.cve.exploit_chain import BUILTIN_GOALS
        goal = BUILTIN_GOALS["jailbreak"]
        self.assertEqual(goal.required_subgoals, ("kernel-rw", "root-privesc", "codesign-bypass"))
        self.assertEqual(goal.difficulty, "hard")

    def test_userland_jailbreak_subgoals(self):
        from host.cve.exploit_chain import BUILTIN_GOALS
        goal = BUILTIN_GOALS["userland-jailbreak"]
        self.assertEqual(goal.required_subgoals, ("root-privesc", "codesign-bypass"))
        self.assertEqual(goal.difficulty, "medium")

    def test_jailbreak_remote_is_extreme(self):
        from host.cve.exploit_chain import BUILTIN_GOALS
        goal = BUILTIN_GOALS["jailbreak-remote"]
        self.assertEqual(goal.difficulty, "extreme")


# =============================================================================
# Fuzzer tests
# =============================================================================

class TestFuzzTarget(unittest.TestCase):
    def test_create_minimal(self):
        from host.cve.fuzzer import FuzzTarget
        t = FuzzTarget(
            name="test-target",
            component="kernel",
            description="Test target",
        )
        self.assertEqual(t.name, "test-target")
        self.assertEqual(t.fuzzer, "honggfuzz")
        self.assertEqual(t.args, [])
        self.assertIsNone(t.harness_path)
        self.assertIsNone(t.corpus_path)

    def test_create_full(self):
        from host.cve.fuzzer import FuzzTarget
        t = FuzzTarget(
            name="full-target",
            component="webkit",
            description="Full target",
            harness_path="/tmp/harness",
            corpus_path="/tmp/corpus",
            fuzzer="libfuzzer",
            args=["-max_len=1024"],
        )
        self.assertEqual(t.harness_path, "/tmp/harness")
        self.assertEqual(t.fuzzer, "libfuzzer")
        self.assertEqual(t.args, ["-max_len=1024"])


class TestFuzzResult(unittest.TestCase):
    def test_create_result(self):
        from host.cve.fuzzer import FuzzResult
        r = FuzzResult(
            target="webkit-jscore",
            runs=1000,
            crashes=5,
            unique_crashes=3,
            coverage=0.45,
            time_seconds=120,
        )
        self.assertEqual(r.target, "webkit-jscore")
        self.assertEqual(r.runs, 1000)
        self.assertEqual(r.crashes, 5)
        self.assertIsNone(r.crashes_dir)
        self.assertEqual(r.notes, "")

    def test_create_full_result(self):
        from host.cve.fuzzer import FuzzResult
        import pathlib
        r = FuzzResult(
            target="test",
            runs=500,
            crashes=2,
            unique_crashes=1,
            coverage=0.8,
            time_seconds=60,
            crashes_dir=pathlib.Path("/tmp/crashes"),
            notes="Interesting crash",
        )
        self.assertEqual(r.notes, "Interesting crash")


class TestFUZZ_TARGETS(unittest.TestCase):
    def test_has_expected_targets(self):
        from host.cve.fuzzer import FUZZ_TARGETS
        expected = {
            "webkit-jscore",
            "webkit-html",
            "kernel-mach",
            "imageio-jpeg",
            "imageio-png",
            "coretext-font",
            "coreaudio",
        }
        self.assertEqual(set(FUZZ_TARGETS.keys()), expected)

    def test_all_targets_are_fuzz_target_instances(self):
        from host.cve.fuzzer import FUZZ_TARGETS, FuzzTarget
        for t in FUZZ_TARGETS.values():
            self.assertIsInstance(t, FuzzTarget)

    def test_target_components(self):
        from host.cve.fuzzer import FUZZ_TARGETS
        self.assertEqual(FUZZ_TARGETS["webkit-jscore"].component, "webkit")
        self.assertEqual(FUZZ_TARGETS["webkit-jscore"].fuzzer, "honggfuzz")
        self.assertEqual(FUZZ_TARGETS["kernel-mach"].component, "kernel")
        self.assertEqual(FUZZ_TARGETS["coreaudio"].component, "coreaudio")


class TestFuzzerFramework(unittest.TestCase):
    def setUp(self):
        from host.cve.fuzzer import FuzzerFramework
        self.fw = FuzzerFramework()

    def test_list_targets(self):
        targets = self.fw.list_targets()
        self.assertIn("webkit-jscore", targets)
        self.assertIn("kernel-mach", targets)
        self.assertEqual(len(targets), 7)

    def test_list_targets_descriptions(self):
        targets = self.fw.list_targets()
        for name, desc in targets.items():
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)

    def test_register_target(self):
        from host.cve.fuzzer import FuzzTarget
        t = FuzzTarget(
            name="custom-target",
            component="test",
            description="Custom target",
        )
        self.fw.register_target(t)
        self.assertIn("custom-target", self.fw.list_targets())

    def test_fuzz_unknown_target_raises(self):
        from host.cve.fuzzer import FuzzerError
        with self.assertRaises(FuzzerError):
            self.fw.fuzz("nonexistent-target")

    def test_fuzz_raises_when_fuzzer_not_installed(self):
        from host.cve.fuzzer import FuzzerError
        with tempfile.TemporaryDirectory() as tmp:
            fw = type(self.fw)(output_dir=pathlib.Path(tmp))
            with self.assertRaises(FuzzerError) as ctx:
                fw.fuzz("webkit-jscore", runs=10)
            self.assertIn("not found in PATH", str(ctx.exception))


# =============================================================================
# CLI integration tests via B34STCLI
# =============================================================================

class TestCVECLI(unittest.TestCase):
    def _run_cli(self, *args):
        """Run B34STCLI with given cve subcommand args and return (code, stdout)."""
        from b34st.engine import B34STCLI
        from io import StringIO
        import contextlib
        cli = B34STCLI()
        old_stdout = sys.stdout
        sys.stdout = buf = StringIO()
        try:
            code = cli.run(["cve", *args])
        finally:
            sys.stdout = old_stdout
        return code, buf.getvalue()

    def test_stats(self):
        code, out = self._run_cli("stats")
        self.assertEqual(code, 0)
        stats = json.loads(out)
        self.assertIn("total_cves", stats)
        self.assertGreater(stats["total_cves"], 0)

    def test_search_webkit(self):
        code, out = self._run_cli("search", "webkit")
        self.assertEqual(code, 0)
        self.assertIn("Found", out)
        self.assertIn("CVE-", out)

    def test_search_no_results(self):
        code, out = self._run_cli("search", "XYZZYX_NOMATCH_12345")
        self.assertEqual(code, 0)
        self.assertIn("No CVEs found", out)

    def test_query_16_5(self):
        code, out = self._run_cli("query", "16.5")
        self.assertEqual(code, 0)
        self.assertIn("CVEs affecting iOS", out)
        self.assertIn("CVE-", out)

    def test_query_no_results(self):
        code, out = self._run_cli("query", "0.1")
        self.assertEqual(code, 0)
        self.assertIn("No CVEs found", out)

    def test_goals(self):
        code, out = self._run_cli("goals")
        self.assertEqual(code, 0)
        self.assertIn("jailbreak", out)
        self.assertIn("forensics-ready", out)
        self.assertIn("requires:", out)

    def test_chain_jailbreak_16_5(self):
        code, out = self._run_cli("chain", "jailbreak", "16.5")
        self.assertEqual(code, 0)
        self.assertIn("Exploit chains", out)
        self.assertIn("CVE-", out)
        self.assertIn("COMPLETE", out)

    def test_chain_unknown_goal(self):
        code, out = self._run_cli("chain", "nonexistent-goal", "16.5")
        self.assertEqual(code, 1)

    def test_chain_no_results(self):
        code, out = self._run_cli("chain", "jailbreak", "99.0")
        self.assertEqual(code, 0)
        self.assertIn("No exploit chains found", out)

    def test_suggest_16_5(self):
        code, out = self._run_cli("suggest", "16.5")
        self.assertEqual(code, 0)
        self.assertIn("ACHIEVABLE", out)
        self.assertIn("jailbreak", out)

    def test_suggest_no_results(self):
        code, out = self._run_cli("suggest", "99.0")
        self.assertEqual(code, 0)
        self.assertIn("No achievable goals found", out)

    def test_fuzz_list(self):
        code, out = self._run_cli("fuzz", "list")
        self.assertEqual(code, 0)
        self.assertIn("webkit-jscore", out)
        self.assertIn("kernel-mach", out)


# =============================================================================
# FBR34KER CLI integration tests (subprocess)
# =============================================================================

class TestFBR34KERCVECLI(unittest.TestCase):
    def test_fbr34ker_cve_stats(self):
        result = __import__("subprocess").run(
            [str(ROOT / "fbr34ker"), "b34st", "cve", "stats"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        stats = json.loads(result.stdout)
        self.assertIn("total_cves", stats)

    def test_fbr34ker_cve_search_webkit(self):
        result = __import__("subprocess").run(
            [str(ROOT / "fbr34ker"), "b34st", "cve", "search", "webkit"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Found", result.stdout)

    def test_fbr34ker_cve_query_16_5(self):
        result = __import__("subprocess").run(
            [str(ROOT / "fbr34ker"), "b34st", "cve", "query", "16.5"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CVEs affecting iOS", result.stdout)

    def test_fbr34ker_cve_goals(self):
        result = __import__("subprocess").run(
            [str(ROOT / "fbr34ker"), "b34st", "cve", "goals"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("jailbreak", result.stdout)

    def test_fbr34ker_cve_chain_jailbreak_16_5(self):
        result = __import__("subprocess").run(
            [str(ROOT / "fbr34ker"), "b34st", "cve", "chain", "jailbreak", "16.5"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Exploit chains", result.stdout)

    def test_fbr34ker_cve_suggest_16_5(self):
        result = __import__("subprocess").run(
            [str(ROOT / "fbr34ker"), "b34st", "cve", "suggest", "16.5"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ACHIEVABLE", result.stdout)


# =============================================================================
# Import verification tests
# =============================================================================

class TestCVEImports(unittest.TestCase):
    def test_import_cve_db(self):
        from host.cve import CVE, VersionRange, CVEDatabase, CVELookupError
        self.assertTrue(True)

    def test_import_exploit_chain(self):
        from host.cve import ExploitGoal, ExploitChain, ChainPlanner, ChainPlannerError
        self.assertTrue(True)

    def test_import_fuzzer(self):
        from host.cve import FuzzerFramework, FuzzerError
        self.assertTrue(True)

    def test_module_all(self):
        from host.cve import __all__
        expected = {
            "BUILTIN_CVE_DB",
            "CVE",
            "CVEDatabase",
            "CVELookupError",
            "ChainPlanner",
            "ChainPlannerError",
            "ExploitChain",
            "ExploitGoal",
            "FuzzerError",
            "FuzzerFramework",
            "GoalType",
            "VersionRange",
            "DeviceInfo",
            "SocInfo",
            "SOC_DATABASE",
            "DEVICE_DATABASE",
            "get_device",
            "get_soc",
            "devices_for_version",
        }
        self.assertEqual(set(__all__), expected)


# =============================================================================
# Concurrent database access / edge case tests
# =============================================================================

class TestCVEDatabaseEdgeCases(unittest.TestCase):
    def test_add_from_dict_missing_optional_fields(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase()
        data = {
            "id": "CVE-2024-EDGE",
            "affected_versions": [{"start": "14.0"}],
            "affected_components": ["kernel"],
            "exploit_type": ["local"],
            "goals": ["kernel-rw"],
        }
        db.add_from_dict(data)
        cve = db.all_cves[0]
        self.assertEqual(cve.mitigations, ())
        self.assertEqual(cve.references, ())
        self.assertEqual(cve.credits, ())
        self.assertIsNone(cve.exploit_path)
        self.assertIsNone(cve.patch_version)

    def test_filter_with_falsy_version_not_applied(self):
        from host.cve.cve_db import CVEDatabase, CVE, VersionRange
        db = CVEDatabase()
        cve = CVE(
            id="CVE-2024-FILTER",
            description="filter edge case",
            affected_versions=(VersionRange(start="14.0"),),
            affected_components=("kernel",),
            exploit_type=("local",),
            exploit_available=False,
            goals=("kernel-rw",),
        )
        db.add(cve)
        results = db.filter()
        self.assertEqual(len(results), 1)
        results = db.filter(version="")
        self.assertEqual(len(results), 1)

    def test_compute_stats_empty(self):
        from host.cve.cve_db import CVEDatabase
        db = CVEDatabase()
        stats = db.compute_stats()
        self.assertEqual(stats["total_cves"], 0)
        self.assertEqual(stats["exploit_available"], 0)
        self.assertEqual(stats["by_severity"], {})
        self.assertEqual(stats["by_component"], {})
        self.assertEqual(stats["by_goal"], {})
        self.assertEqual(stats["by_exploit_type"], {})


if __name__ == "__main__":
    unittest.main()
