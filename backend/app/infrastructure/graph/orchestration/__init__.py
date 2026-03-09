"""Orchestration Module - Separated Voice and Spotlight Orchestrations

Voice orchestration: voice/
Spotlight orchestration: spotlight/
Shared utilities: shared/

Import the specific orchestration you need:
    from app.infrastructure.graph.orchestration.voice import get_voice_orchestration_app
    from app.infrastructure.graph.orchestration.spotlight import get_spotlight_orchestration_app
"""

from app.infrastructure.graph.orchestration.spotlight import get_spotlight_orchestration_app
from app.infrastructure.graph.orchestration.voice import get_voice_orchestration_app

__all__ = ["get_voice_orchestration_app", "get_spotlight_orchestration_app"]
