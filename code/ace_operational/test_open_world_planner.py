"""Engineering checks for domain-neutral typed capability composition.

These are PUBLIC development fixtures, not scientific holdouts. A passing
planner test does not establish intelligence, remote worker interoperability,
general semantic understanding, or safe candidate-code execution.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ace_operational.open_world_planner import (
    Capability, CapabilityRegistry, plan_capabilities,
)


def cap(name, inputs, outputs, *, status="VERIFIED", evidence="fixture:pass",
        effect="none", cost=1, provider="example"):
    return Capability(
        name, frozenset(inputs), frozenset(outputs), provider,
        evidence_ref=evidence, status=status, effect=effect, cost_units=cost,
    )


class OpenWorldPlannerTests(unittest.TestCase):
    def test_heterogeneous_multistage_chain_without_domain_allowlist(self):
        registry = CapabilityRegistry()
        registry.register(cap("astro", {"raw:star_catalog"}, {"table:orbit_fit"}))
        registry.register(cap("physics", {"table:orbit_fit"}, {"proof:stability"}))
        registry.register(cap("music", {"score:midi"}, {"render:audio"}))
        result = plan_capabilities(
            registry, available_types={"raw:star_catalog"},
            goal_types={"proof:stability"},
        )
        self.assertEqual(result.status, "READY")
        self.assertEqual(result.capability_ids, ("astro", "physics"))
        self.assertEqual(result.expanded_states, 2)

    def test_new_domain_can_be_registered_without_code_change(self):
        registry = CapabilityRegistry()
        registry.register(cap("next", {"genome:sequences"}, {"hypothesis:protein"}))
        r = plan_capabilities(registry, available_types={"genome:sequences"},
                              goal_types={"hypothesis:protein"})
        self.assertEqual(r.capability_ids, ("next",))

    def test_minimum_cost_not_fewest_steps(self):
        registry = CapabilityRegistry()
        registry.register(cap("expensive", {"raw"}, {"done"}, cost=9))
        registry.register(cap("a", {"raw"}, {"mid"}, cost=1))
        registry.register(cap("b", {"mid"}, {"done"}, cost=1))
        r = plan_capabilities(registry, available_types={"raw"}, goal_types={"done"})
        self.assertEqual(r.capability_ids, ("a", "b"))
        self.assertEqual(r.total_cost_units, 2)

    def test_unverified_and_unreferenced_are_not_eligible(self):
        registry = CapabilityRegistry()
        registry.register(cap("unverified", {"raw"}, {"done"}, status="UNVERIFIED"))
        registry.register(cap("fake", {"raw"}, {"done"}, evidence=""))
        r = plan_capabilities(registry, available_types={"raw"}, goal_types={"done"})
        self.assertEqual(r.status, "NO_PLAN")
        self.assertEqual(r.missing_types, frozenset({"done"}))

    def test_external_effect_requires_explicit_scope(self):
        registry = CapabilityRegistry()
        registry.register(cap("publish", {"draft"}, {"published"}, effect="external"))
        blocked = plan_capabilities(registry, available_types={"draft"}, goal_types={"published"})
        allowed = plan_capabilities(registry, available_types={"draft"}, goal_types={"published"},
                                    allowed_effects={"none", "read", "external"})
        self.assertEqual(blocked.status, "NO_PLAN")
        self.assertEqual(allowed.capability_ids, ("publish",))
        # A plan only authorizes *selection* of a candidate; it never performs a publication.

    def test_cyclic_registry_terminates_without_success(self):
        registry = CapabilityRegistry()
        registry.register(cap("a", {"raw"}, {"mid"}))
        registry.register(cap("b", {"mid"}, {"raw"}))
        r = plan_capabilities(registry, available_types={"raw"}, goal_types={"unknown"})
        self.assertEqual(r.status, "NO_PLAN")
        self.assertLessEqual(r.expanded_states, 2)

    def test_step_budget_halts_and_reports_limit(self):
        registry = CapabilityRegistry()
        registry.register(cap("a", {"raw"}, {"mid"}))
        registry.register(cap("b", {"mid"}, {"done"}))
        r = plan_capabilities(registry, available_types={"raw"},
                              goal_types={"done"}, max_steps=1)
        self.assertEqual(r.status, "SEARCH_LIMIT")

    def test_expansion_budget_halts(self):
        registry = CapabilityRegistry()
        registry.register(cap("a", {"raw"}, {"mid"}))
        registry.register(cap("b", {"mid"}, {"done"}))
        r = plan_capabilities(registry, available_types={"raw"},
                              goal_types={"done"}, max_expansions=1)
        self.assertEqual(r.status, "SEARCH_LIMIT")

    def test_no_work_when_goal_already_available(self):
        r = plan_capabilities(CapabilityRegistry(), available_types={"done"},
                              goal_types={"done"})
        self.assertEqual(r.status, "READY")
        self.assertEqual(r.capability_ids, ())
        self.assertEqual(r.total_cost_units, 0)

    def test_duplicate_capability_id_rejected(self):
        registry = CapabilityRegistry()
        registry.register(cap("same", {"a"}, {"b"}))
        with self.assertRaises(ValueError):
            registry.register(cap("same", {"b"}, {"c"}))

    def test_invalid_contracts_rejected(self):
        with self.assertRaises(ValueError):
            cap("bad", {"a"}, set())
        with self.assertRaises(ValueError):
            cap("bad", {"a"}, {"b"}, cost=0)
        with self.assertRaises(ValueError):
            cap("bad", {"a"}, {"b"}, effect="admin")
        with self.assertRaises(ValueError):
            plan_capabilities(CapabilityRegistry(), available_types={"a"},
                              goal_types=set())

    def test_provider_name_has_no_device_restriction(self):
        registry = CapabilityRegistry()
        registry.register(cap("hpc", {"dataset"}, {"analysis"}, provider="cluster:hpc"))
        registry.register(cap("oracle", {"analysis"}, {"paper"}, provider="a2a:partner"))
        r = plan_capabilities(registry, available_types={"dataset"}, goal_types={"paper"})
        self.assertEqual(r.capability_ids, ("hpc", "oracle"))


if __name__ == "__main__":
    unittest.main()
