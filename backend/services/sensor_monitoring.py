"""Normalized sensor ingestion and anomaly detection."""

from __future__ import annotations

import uuid
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from sqlalchemy.orm import Session
import httpx

from backend.database.models import EnvironmentalObservationDB, SensorEventDB, SensorObservationDB, WeatherObservationDB, ZoneDB
from backend.models.phase3 import SensorObservationCreate
from backend.services.event_engine import event_engine
from backend.services.audit_service import audit_service
from backend.config import settings
from backend.services.provider_health import provider_health

logger = logging.getLogger(__name__)


THRESHOLDS = {
    "rainfall": (80.0, 120.0),
    "river_level": (70.0, 85.0),
    "water_level": (70.0, 85.0),
    "soil_moisture": (75.0, 90.0),
    "ground_movement": (40.0, 70.0),
    "tilt": (5.0, 10.0),
    "temperature": (38.0, 42.0),
    "wind": (65.0, 90.0),
}


class SensorProvider(Protocol):
    """Provider contract for normalized sensor readings."""

    def read(self, zone: ZoneDB, scenario: str = "default") -> list[SensorObservationCreate]: ...


class SensorProviderUnavailable(RuntimeError):
    pass


class DemoSensorProvider:
    """Deterministic simulated readings, always labelled DEMO_SIMULATION."""

    SCENARIOS = {
        "nepal_mountain": [("rainfall", 180, "mm/6h"), ("river_level", 88, "normalized"), ("soil_moisture", 92, "%"), ("ground_movement", 80, "normalized")],
        "urban_flood": [("rainfall", 130, "mm"), ("water_level", 82, "normalized"), ("soil_moisture", 80, "%")],
        "cyclone": [("wind", 110, "kph"), ("rainfall", 105, "mm"), ("water_level", 72, "normalized")],
        "heatwave": [("temperature", 44, "celsius"), ("soil_moisture", 25, "%")],
    }

    def read(self, zone: ZoneDB, scenario: str = "default") -> list[SensorObservationCreate]:
        readings = self.SCENARIOS.get(scenario.lower().replace(" ", "_").replace("-", "_"))
        if readings is None:
            raise SensorProviderUnavailable(f"no demo sensor scenario named {scenario}")
        return [SensorObservationCreate(sensor_id=f"{zone.id}-{sensor_type.upper()}-{index + 1}", sensor_type=sensor_type, zone_id=zone.id, value=value, unit=unit, source="DEMO_SIMULATION") for index, (sensor_type, value, unit) in enumerate(readings)]


class ExternalSensorProvider:
    """Reserved adapter boundary for configured IoT gateways.

    Physical hardware is intentionally optional in this phase; an unavailable
    gateway must be represented as a provider failure, never as live data.
    """

    def read(self, zone: ZoneDB, scenario: str = "default") -> list[SensorObservationCreate]:
        raise SensorProviderUnavailable("external sensor gateway is not configured")


class HttpSensorProvider:
    """Normalized HTTP gateway adapter for future IoT/environment devices."""

    name = "IOT_HTTP"

    def __init__(self, client_factory=httpx.Client):
        self.client_factory = client_factory

    def read(self, zone: ZoneDB, scenario: str = "default") -> list[SensorObservationCreate]:
        if not settings.SENSOR_API_URL:
            raise SensorProviderUnavailable("HTTP sensor gateway is not configured")
        started = time.perf_counter()
        try:
            headers = {"User-Agent": "AITAM-Disaster-Response/1.0"}
            if settings.SENSOR_API_KEY:
                headers["Authorization"] = f"Bearer {settings.SENSOR_API_KEY}"
            body = self._request({"zone_id": zone.id, "scenario": scenario}, headers)
            raw_items = body.get("observations") if isinstance(body, dict) else body
            if not isinstance(raw_items, list):
                raise SensorProviderUnavailable("sensor gateway response must be a list")
            readings = []
            for item in raw_items:
                if not isinstance(item, dict):
                    raise SensorProviderUnavailable("sensor gateway returned an invalid observation")
                normalized = SensorObservationCreate.model_validate({**item, "zone_id": item.get("zone_id") or zone.id, "region_id": item.get("region_id") or zone.region_id, "location": item.get("location") or zone.name, "source": item.get("source") or "IOT"})
                readings.append(normalized)
            provider_health.success(self.name, latency_ms=(time.perf_counter() - started) * 1000, source="iot")
            return readings
        except (httpx.HTTPError, ValueError, TypeError, SensorProviderUnavailable) as exc:
            provider_health.failure(self.name, latency_ms=(time.perf_counter() - started) * 1000, error_type=type(exc).__name__, source="iot")
            logger.warning("sensor provider failed provider=%s error_type=%s", self.name, type(exc).__name__)
            raise SensorProviderUnavailable(f"HTTP sensor provider failed: {type(exc).__name__}") from exc

    def _request(self, params: dict[str, str], headers: dict[str, str]) -> Any:
        attempts = max(1, settings.SENSOR_RETRIES + 1)
        for attempt in range(attempts):
            try:
                with self.client_factory(timeout=settings.SENSOR_TIMEOUT_SECONDS) as client:
                    response = client.get(settings.SENSOR_API_URL, params=params, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        time.sleep(settings.SENSOR_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                        continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 < attempts:
                    time.sleep(settings.SENSOR_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                    continue
                raise SensorProviderUnavailable(type(exc).__name__) from exc
            except httpx.HTTPStatusError as exc:
                raise SensorProviderUnavailable(f"HTTP_{exc.response.status_code}") from exc
            except ValueError as exc:
                raise SensorProviderUnavailable("invalid_json") from exc
        raise SensorProviderUnavailable("provider_exhausted_retries")


def get_sensor_provider():
    if settings.SENSOR_PROVIDER.strip().lower() in {"http", "iot", "iot_http"}:
        return HttpSensorProvider()
    return DemoSensorProvider()


class SensorAnomalyDetector:
    def detect(self, sensor_type: str, current: float, previous: Optional[float]) -> Optional[dict[str, Any]]:
        key = sensor_type.lower().replace("-", "_").replace(" ", "_")
        low, critical = THRESHOLDS.get(key, (None, None))
        change = current - previous if previous is not None else None
        rising = change is not None and change >= max(5.0, abs(current) * 0.15)
        if low is None:
            return None
        level = "critical" if current >= critical else "high" if current >= low or rising else None
        if level is None:
            return None
        direction = "rapidly rising" if rising else "elevated"
        return {"anomaly_level": level, "change_value": change, "description": f"{key.replace('_', ' ').title()} is {direction} ({current:g}); environmental review triggered."}


class SensorMonitoringService:
    def __init__(self, detector: Optional[SensorAnomalyDetector] = None):
        self.detector = detector or SensorAnomalyDetector()

    def ingest(self, db: Session, payload: SensorObservationCreate, zone: ZoneDB) -> tuple[SensorObservationDB, Optional[SensorEventDB]]:
        previous_row = db.query(SensorObservationDB).filter(SensorObservationDB.sensor_id == payload.sensor_id).order_by(SensorObservationDB.observed_at.desc()).first()
        now = datetime.now(timezone.utc)
        row = SensorObservationDB(sensor_id=payload.sensor_id, sensor_type=payload.sensor_type.lower().replace(" ", "_"), region_id=zone.region_id, zone_id=zone.id, location=payload.location or zone.name, latitude=payload.latitude if payload.latitude is not None else zone.latitude, longitude=payload.longitude if payload.longitude is not None else zone.longitude, value=payload.value, unit=payload.unit, observed_at=payload.observed_at or now, received_at=now, source=payload.source.upper(), metadata_json=__import__("json").dumps(payload.metadata))
        db.add(row)
        db.flush()
        self._mirror_observation(db, row, zone)
        event_engine.publish_event("sensor_update", f"sensor:{row.id}", {"event_name": "sensor_update", "event": "SENSOR_UPDATE", "observation_id": row.id, "sensor_type": row.sensor_type, "zone_id": zone.id, "value": row.value, "source": row.source})
        anomaly = self.detector.detect(row.sensor_type, row.value, previous_row.value if previous_row else None)
        event = None
        if anomaly:
            event = SensorEventDB(event_id=f"SENSOR-EVT-{uuid.uuid4().hex[:12].upper()}", sensor_id=row.sensor_id, sensor_type=row.sensor_type, region_id=zone.region_id, zone_id=zone.id, previous_value=previous_row.value if previous_row else None, current_value=row.value, change_value=anomaly["change_value"], anomaly_level=anomaly["anomaly_level"], description=anomaly["description"], source=row.source, status="detected", created_at=now)
            db.add(event)
            db.flush()
            event_engine.publish_event("environment_anomaly", event.event_id, {"event_name": "environment_anomaly", "event": "ENVIRONMENT_ANOMALY", "sensor_event_id": event.event_id, "sensor_type": event.sensor_type, "zone_id": zone.id, "anomaly_level": event.anomaly_level, "description": event.description})
        db.commit()
        audit_service.log("sensor_observation_ingested", f"Sensor observation {row.id} ingested from {row.source}.", incident_id=event.event_id if event else None, actor="Sensor Monitoring Service", details={"sensor_id": row.sensor_id, "sensor_type": row.sensor_type, "zone_id": row.zone_id, "value": row.value, "source": row.source, "anomaly": anomaly}, db=db)
        if event:
            event_engine.publish_event("disaster_detected", event.event_id, {"event_name": "disaster_detected", "event": "DISASTER_DETECTED", "zone_id": zone.id, "description": event.description})
        return row, event

    @staticmethod
    def _mirror_observation(db: Session, row: SensorObservationDB, zone: ZoneDB) -> None:
        sensor_type = row.sensor_type
        if sensor_type in {"rainfall", "temperature", "wind"}:
            weather = WeatherObservationDB(region_id=zone.region_id, zone_id=zone.id, location=zone.name, latitude=zone.latitude, longitude=zone.longitude, observed_at=row.observed_at, received_at=row.received_at, condition="sensor observation", rainfall_mm=row.value if sensor_type == "rainfall" else None, rainfall_intensity=row.value if sensor_type == "rainfall" else None, temperature_c=row.value if sensor_type == "temperature" else None, wind_speed_kph=row.value if sensor_type == "wind" else None, source=row.source)
            db.add(weather)
        indicator = {"river_level": "water_level_score", "water_level": "water_level_score", "soil_moisture": "soil_moisture_score", "ground_movement": "ground_movement_score", "tilt": "ground_movement_score"}.get(sensor_type)
        if indicator:
            db.add(EnvironmentalObservationDB(region_id=zone.region_id, zone_id=zone.id, location=zone.name, latitude=zone.latitude, longitude=zone.longitude, observed_at=row.observed_at, received_at=row.received_at, indicator=indicator, value=row.value, unit=row.unit, source=row.source))


sensor_monitoring_service = SensorMonitoringService()
