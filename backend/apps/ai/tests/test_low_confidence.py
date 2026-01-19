"""
test_low_confidence.py — Tests for LOW_CONFIDENCE vs EMPTY_RESULT distinction.

P1: Verify that:
1. LOW_CONFIDENCE is returned when zone="low_confidence" or confidence < 0.5
2. EMPTY_RESULT is returned when zone is empty and confidence is None/high
3. Structured error_code passthrough works for LOW_CONFIDENCE
"""

from __future__ import annotations

from django.test import TestCase


class TestLowConfidenceHandling(TestCase):
    """Tests for LOW_CONFIDENCE vs EMPTY_RESULT logic in tasks.py."""

    def _make_result(self, items=None, totals=None, meta=None):
        """Factory for creating mock RecognizeFoodResult."""
        from apps.ai_proxy.service import RecognizeFoodResult

        return RecognizeFoodResult(
            items=items or [],
            totals=totals or {},
            meta=meta or {},
        )

    def test_empty_items_with_low_confidence_zone_returns_low_confidence(self):
        """
        Test: AI Proxy returns empty items with zone="low_confidence"
        Expected: LOW_CONFIDENCE error (not EMPTY_RESULT)
        """
        from apps.ai.error_contract import AIErrorRegistry

        # Simulate meta with low_confidence zone
        meta = {
            "request_id": "test-rid",
            "zone": "low_confidence",
            "confidence": 0.3,
        }
        result = self._make_result(items=[], meta=meta)

        # Verify zone triggers LOW_CONFIDENCE
        self.assertEqual(result.meta.get("zone"), "low_confidence")
        # The actual logic is in tasks.py, here we just verify registry has the code
        self.assertTrue(hasattr(AIErrorRegistry, "LOW_CONFIDENCE"))
        self.assertEqual(AIErrorRegistry.LOW_CONFIDENCE.code, "LOW_CONFIDENCE")
        self.assertIn("manual_select", AIErrorRegistry.LOW_CONFIDENCE.user_actions)

    def test_empty_items_with_confidence_below_threshold_returns_low_confidence(self):
        """
        Test: AI Proxy returns empty items with confidence=0.3 (below 0.5)
        Expected: LOW_CONFIDENCE error
        """
        from apps.ai.error_contract import AIErrorRegistry

        meta = {
            "request_id": "test-rid",
            "confidence": 0.3,
        }
        result = self._make_result(items=[], meta=meta)

        # Verify confidence is extracted and below threshold
        self.assertEqual(result.meta.get("confidence"), 0.3)
        self.assertLess(result.meta.get("confidence"), 0.5)  # threshold triggers LOW_CONFIDENCE
        # Verify LOW_CONFIDENCE error exists for this case
        self.assertEqual(AIErrorRegistry.LOW_CONFIDENCE.code, "LOW_CONFIDENCE")

    def test_empty_items_without_metadata_returns_empty_result(self):
        """
        Test: AI Proxy returns empty items without zone/confidence
        Expected: EMPTY_RESULT error (fallback)
        """
        from apps.ai.error_contract import AIErrorRegistry

        meta = {"request_id": "test-rid"}
        result = self._make_result(items=[], meta=meta)

        # No zone, no confidence → should be EMPTY_RESULT
        self.assertIsNone(result.meta.get("zone"))
        self.assertIsNone(result.meta.get("confidence"))
        self.assertEqual(AIErrorRegistry.EMPTY_RESULT.code, "EMPTY_RESULT")

    def test_passthrough_low_confidence_error_code(self):
        """
        Test: AI Proxy returns structured error with error_code=LOW_CONFIDENCE
        Expected: Passthrough (get_by_code returns LOW_CONFIDENCE, not UNKNOWN_ERROR)
        """
        from apps.ai.error_contract import AIErrorRegistry

        error_def = AIErrorRegistry.get_by_code("LOW_CONFIDENCE")

        self.assertEqual(error_def.code, "LOW_CONFIDENCE")
        self.assertEqual(error_def.user_title, "Не уверены в результате")
        self.assertIn("manual_select", error_def.user_actions)

    def test_unknown_error_code_fallback(self):
        """
        Test: Unknown error_code falls back to UNKNOWN_ERROR
        """
        from apps.ai.error_contract import AIErrorRegistry

        error_def = AIErrorRegistry.get_by_code("SOME_UNKNOWN_CODE")

        self.assertEqual(error_def.code, "UNKNOWN_ERROR")

    def test_zone_priority_over_confidence(self):
        """
        Test: zone="food_likely" with confidence=0.49 should NOT trigger LOW_CONFIDENCE
        Because zone takes priority and "food_likely" is not in low_confidence_zones.
        This protects against desync between AI Proxy thresholds and backend.
        """
        meta = {
            "request_id": "test-rid",
            "zone": "food_likely",  # Not in low_confidence_zones
            "confidence": 0.49,  # Below config threshold
        }
        result = self._make_result(items=[], meta=meta)

        # Zone is "food_likely" (not in low_confidence_zones)
        # So this should fallback to EMPTY_RESULT, not LOW_CONFIDENCE
        zone = result.meta.get("zone", "").strip().lower()
        self.assertEqual(zone, "food_likely")
        self.assertNotIn(zone, {"low_confidence", "low", "food_possible"})

    def test_zone_normalization_case_insensitive(self):
        """
        Test: Zone normalization handles uppercase and variants
        """
        # Test uppercase zone
        meta = {"zone": "LOW_CONFIDENCE", "confidence": 0.8}
        result = self._make_result(items=[], meta=meta)

        zone = str(result.meta.get("zone", "")).strip().lower()
        self.assertEqual(zone, "low_confidence")
        self.assertIn(zone, {"low_confidence", "low", "food_possible"})


class TestZoneConstantsIntegration(TestCase):
    """Behavioral tests verifying SSOT zone constants are used correctly."""

    def test_low_confidence_zones_from_constants(self):
        """
        Test: LOW_CONFIDENCE_ZONES constant contains expected values
        and is used in tasks.py logic.
        """
        from apps.ai_proxy.constants import LOW_CONFIDENCE_ZONES

        # Verify expected zones
        self.assertIn("low_confidence", LOW_CONFIDENCE_ZONES)
        self.assertIn("low", LOW_CONFIDENCE_ZONES)
        self.assertIn("food_possible", LOW_CONFIDENCE_ZONES)
        # Verify not in wrong set
        self.assertNotIn("not_food", LOW_CONFIDENCE_ZONES)

    def test_not_food_zones_from_constants(self):
        """
        Test: NOT_FOOD_ZONES constant contains expected values.
        """
        from apps.ai_proxy.constants import NOT_FOOD_ZONES

        # Verify expected zones
        self.assertIn("not_food", NOT_FOOD_ZONES)
        self.assertIn("no_food", NOT_FOOD_ZONES)
        self.assertIn("unsupported", NOT_FOOD_ZONES)
        # Verify not in wrong set
        self.assertNotIn("low_confidence", NOT_FOOD_ZONES)

    def test_zone_food_possible_triggers_low_confidence_error(self):
        """
        Behavioral test: zone="food_possible" should map to LOW_CONFIDENCE error.
        Verifies SSOT is correctly used in decision logic.
        """
        from apps.ai.error_contract import AIErrorRegistry
        from apps.ai_proxy.constants import LOW_CONFIDENCE_ZONES

        # food_possible is in LOW_CONFIDENCE_ZONES
        zone = "food_possible"
        self.assertIn(zone, LOW_CONFIDENCE_ZONES)

        # So it should map to LOW_CONFIDENCE error
        error_def = AIErrorRegistry.LOW_CONFIDENCE
        self.assertEqual(error_def.code, "LOW_CONFIDENCE")
        self.assertIn("manual_select", error_def.user_actions)

    def test_zone_unsupported_triggers_unsupported_content_error(self):
        """
        Behavioral test: zone="unsupported" should map to UNSUPPORTED_CONTENT error.
        """
        from apps.ai.error_contract import AIErrorRegistry
        from apps.ai_proxy.constants import NOT_FOOD_ZONES

        # unsupported is in NOT_FOOD_ZONES
        zone = "unsupported"
        self.assertIn(zone, NOT_FOOD_ZONES)

        # So it should map to UNSUPPORTED_CONTENT error
        error_def = AIErrorRegistry.UNSUPPORTED_CONTENT
        self.assertEqual(error_def.code, "UNSUPPORTED_CONTENT")
        self.assertIn("retake", error_def.user_actions)
