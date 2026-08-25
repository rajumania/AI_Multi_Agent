"""Backward-compatible telemetry schema exports."""

from backend.models.transport import TelemetryIngestRequest, TelemetryIngestResponse

__all__ = ["TelemetryIngestRequest", "TelemetryIngestResponse"]
