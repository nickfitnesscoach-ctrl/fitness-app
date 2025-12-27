# Image Normalization (AI Proxy)

## HARD SLA

All images sent to Vision models MUST be:
- **Format**: JPEG
- **Quality**: 85
- **Dimension**: Max 1024px on longest side
- **Color Mode**: RGB (No Alpha)

## Action-Based Logic

`normalize_image()` returns `metrics["action"]`:
- `"ok"` → Image can be sent to Vision
- `"reject"` → FORBIDDEN, service returns controlled error

**On reject**: Returns `b""` (empty bytes) — impossible to accidentally send originals.

## Fallback Policy

Pass-through allowed ONLY if:
- `content_type == image/jpeg`
- `longest side <= 1024px`
- `size <= 512KB`

All other cases: MUST normalize or reject.

## content_type Normalization

Input `content_type` is normalized:
- Lowercase
- Stripped after `;` (e.g., `image/jpeg; charset=binary` → `image/jpeg`)

## Error Codes

| Code | Reason |
|------|--------|
| `UNSUPPORTED_IMAGE_FORMAT` | HEIC without decoder |
| `IMAGE_DECODE_FAILED` | Corrupted, too slow, save failed |
| `IMAGE_VALIDATION_FAILED` | Final assert failed (regression) |

## Metrics Logged

- `request_id`, `action`, `reason`
- `content_type_in`, `content_type_out`
- `original_size_bytes`, `normalized_size_bytes`
- `original_px`, `normalized_px`
- `original_longest_side`, `normalized_longest_side`
- `processing_ms`

**Note**: `normalized_longest_side = 0` on reject.

## Execution Rule

Normalization executed **exactly once** per request, before base64 and retries.

## Non-Goals

- No background/async normalization
- No disk persistence
- No metadata exposure to users

## Android Note

High-resolution JPEG from Android (8–12MB, >6000px) normalized using same rules. JPEG format ≠ safe size.
