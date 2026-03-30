"""Worker 설정값 검증 유틸."""

import logging
import math

logger = logging.getLogger(__name__)


def validate_tts_volume_scale(value: object) -> float:
    """TTS 볼륨 스케일 값을 안전한 범위로 보정한다."""
    default_scale = 0.70

    if value is None or value == "":
        return default_scale

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        logger.warning(
            "잘못된 TTS_VOLUME_SCALE 값(%r), 기본값 %.2f 사용",
            value,
            default_scale,
        )
        return default_scale

    if not math.isfinite(numeric_value):
        logger.warning(
            "유한하지 않은 TTS_VOLUME_SCALE 값(%r), 기본값 %.2f 사용",
            value,
            default_scale,
        )
        return default_scale

    clamped_value = min(1.0, max(0.0, numeric_value))
    if clamped_value != numeric_value:
        logger.warning(
            "TTS_VOLUME_SCALE %.3f 범위 이탈, %.3f로 보정",
            numeric_value,
            clamped_value,
        )

    return clamped_value
