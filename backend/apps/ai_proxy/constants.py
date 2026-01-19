"""
Zone constants for AI Proxy response handling.

SSOT for zone classification used in tasks.py empty-items decision logic.
If you update these sets, also update docs/AI_PROXY.md Zone Mapping table.
"""

# Zones indicating AI detected possible food but confidence is too low
# → triggers LOW_CONFIDENCE error (user can manually select or retake)
LOW_CONFIDENCE_ZONES = frozenset({"low_confidence", "low", "food_possible"})

# Zones indicating AI determined content is not food
# → triggers UNSUPPORTED_CONTENT error (user should take photo of actual food)
# Note: "unsupported" here means "unsupported content type (not food)",
#       NOT "unsupported image format" which comes as HTTP 400/error_code
NOT_FOOD_ZONES = frozenset({"not_food", "no_food", "unsupported"})
