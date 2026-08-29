"""Explainable, deterministic disaster-risk feature extraction and scoring.

This module deliberately does not call an LLM.  It turns normalized evidence
into bounded features, applies configurable disaster-specific weights, and
returns a result that can be audited and reproduced.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.config import settings
from backend.models.incident import DisasterType, SeverityLevel


FEATURE_LABELS = {
    "rainfall_score": "Rainfall",
    "rainfall_intensity_score": "Rainfall intensity",
    "water_level_score": "Water level",
    "elevation_vulnerability": "Low-elevation vulnerability",
    "slope_vulnerability": "Slope vulnerability",
    "soil_moisture_score": "Soil moisture",
    "drainage_vulnerability": "Drainage vulnerability",
    "terrain_vulnerability": "Terrain vulnerability",
    "historical_risk": "Historical disaster risk",
    "community_signal": "Community reports",
    "population_exposure": "Population exposure",
    "wind_severity": "Wind severity",
    "pressure_severity": "Atmospheric pressure concern",
    "temperature_severity": "Temperature severity",
    "humidity_severity": "Humidity",
    "weather_severity": "Weather severity",
    "coastal_vulnerability": "Coastal vulnerability",
    "heat_duration": "Heat duration",
    "ground_movement_score": "Ground movement",
    "weather_warning_score": "Authoritative weather warning",
    "earthquake_magnitude_score": "Nearby earthquake magnitude",
    "image_evidence_score": "Image evidence (supporting signal)",
}


DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "flood": {"rainfall_score": .25, "water_level_score": .20, "elevation_vulnerability": .15, "historical_risk": .15, "community_signal": .08, "image_evidence_score": .04, "drainage_vulnerability": .10, "population_exposure": .05},
    "urban_flood": {"rainfall_score": .25, "drainage_vulnerability": .25, "community_signal": .15, "elevation_vulnerability": .15, "historical_risk": .10, "population_exposure": .10},
    "landslide": {"rainfall_score": .20, "rainfall_intensity_score": .16, "slope_vulnerability": .18, "soil_moisture_score": .14, "terrain_vulnerability": .12, "ground_movement_score": .10, "image_evidence_score": .05, "historical_risk": .05},
    "cyclone": {"wind_severity": .20, "pressure_severity": .12, "weather_severity": .18, "weather_warning_score": .20, "rainfall_score": .12, "image_evidence_score": .03, "coastal_vulnerability": .08, "population_exposure": .07},
    "heatwave": {"temperature_severity": .30, "humidity_severity": .15, "heat_duration": .20, "historical_risk": .15, "population_exposure": .20},
    "severe_weather": {"wind_severity": .20, "rainfall_score": .16, "rainfall_intensity_score": .12, "weather_severity": .20, "weather_warning_score": .20, "historical_risk": .07, "population_exposure": .05},
    "earthquake": {"earthquake_magnitude_score": .55, "ground_movement_score": .15, "image_evidence_score": .05, "historical_risk": .10, "population_exposure": .15},
    "fire": {"weather_severity": .25, "community_signal": .20, "image_evidence_score": .10, "population_exposure": .20, "historical_risk": .15, "wind_severity": .10},
    "other": {"weather_severity": .35, "historical_risk": .20, "community_signal": .15, "image_evidence_score": .10, "population_exposure": .15, "terrain_vulnerability": .05},
}


def _clamp(value: Any, low: float = 0.0, high: float = 100.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return round(max(low, min(high, number)), 2)


def _value(source: Any, name: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _first_indicator(observations: list[Any], *names: str) -> Optional[float]:
    wanted = {name.lower() for name in names}
    for row in reversed(observations):
        indicator = str(_value(row, "indicator", "")).lower().replace("-", "_").replace(" ", "_")
        if indicator in wanted:
            raw = _value(row, "value")
            try:
                if raw is not None and math.isfinite(float(raw)):
                    return float(raw)
            except (TypeError, ValueError):
                pass
    return None


def _score(value: Optional[float], maximum: float) -> Optional[float]:
    return None if value is None else _clamp((value / maximum) * 100.0)


@dataclass
class RiskFeatures:
    values: dict[str, float]
    available: set[str] = field(default_factory=set)
    source_count: int = 0
    freshness_seconds: Optional[float] = None
    data_status: str = "DEMO"
    stale: bool = False

    def as_dict(self) -> dict[str, float]:
        return {key: _clamp(value) for key, value in self.values.items()}


@dataclass
class RiskResult:
    score: float
    level: SeverityLevel
    confidence: float
    features: dict[str, float]
    contributing_factors: list[str]
    recommendations: list[str]
    explanation: str
    data_status: str
    freshness_seconds: Optional[float]
    stale: bool


class RiskFeatureEngine:
    """Extract bounded features from weather, environment and zone evidence."""

    def build(
        self,
        zone: Any,
        weather: Any = None,
        environmental: Optional[list[Any]] = None,
        community_reports: Optional[list[Any]] = None,
        now: Optional[datetime] = None,
    ) -> RiskFeatures:
        environmental = environmental or []
        community_reports = community_reports or []
        now = now or datetime.now(timezone.utc)
        values: dict[str, float] = {}
        available: set[str] = set()
        sources: set[str] = set()
        freshness: list[float] = []
        statuses: set[str] = set()

        def add(name: str, value: Optional[float], source: Any = None):
            if value is None:
                return
            values[name] = _clamp(value)
            available.add(name)
            if source:
                sources.add(str(source).upper())

        # Weather is normalized by the provider, but DB rows and dictionaries
        # are both accepted so the feature engine remains easy to test/reuse.
        if weather is not None:
            source = _value(weather, "source", "")
            weather_status = str(_value(weather, "status", "")).upper()
            if weather_status:
                statuses.add(weather_status)
            observed = _value(weather, "timestamp") or _value(weather, "observed_at") or _value(weather, "received_at")
            if observed:
                if isinstance(observed, str):
                    try:
                        observed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
                    except ValueError:
                        observed = None
                if observed:
                    if observed.tzinfo is None:
                        observed = observed.replace(tzinfo=timezone.utc)
                    freshness.append(max(0.0, (now - observed).total_seconds()))
            if str(_value(weather, "status", "")).upper() in {"FALLBACK", "OFFLINE"}:
                # A fallback response is useful for development but must not
                # be treated as a fresh live observation by risk scoring.
                freshness.append(float(settings.WEATHER_STALE_AFTER_MINUTES * 60 + 1))
            rainfall = _value(weather, "rainfall_mm")
            intensity = _value(weather, "rainfall_intensity")
            wind = _value(weather, "wind_speed_kph")
            pressure = _value(weather, "pressure")
            temperature = _value(weather, "temperature_c")
            humidity = _value(weather, "humidity")
            condition = str(_value(weather, "condition", "")).lower()
            add("rainfall_score", _score(rainfall, 150), source)
            add("rainfall_intensity_score", _score(intensity, 50), source)
            add("wind_severity", _score(wind, 120), source)
            add("pressure_severity", _score(max(0.0, 1013.0 - float(pressure)) if pressure is not None else None, 60), source)
            add("temperature_severity", _score(max(0.0, float(temperature) - 30.0) if temperature is not None else None, 18), source)
            add("humidity_severity", _score(max(0.0, float(humidity) - 60.0) if humidity is not None else None, 40), source)
            condition_score = 85 if any(word in condition for word in ("storm", "thunder", "cyclone", "extreme")) else 55 if any(word in condition for word in ("rain", "shower", "squall")) else 20 if condition and condition != "unknown" else None
            add("weather_severity", condition_score, source)

        # Environmental indicators may be live sensor values or explicitly
        # labelled DEMO/SIMULATION records.
        for row in environmental:
            sources.add(str(_value(row, "source", "")).upper())
            row_status = str(_value(row, "status", "")).upper()
            if row_status:
                statuses.add(row_status)
            observed = _value(row, "received_at") or _value(row, "observed_at")
            if observed:
                if isinstance(observed, str):
                    try:
                        observed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
                    except ValueError:
                        observed = None
                if observed:
                    if observed.tzinfo is None:
                        observed = observed.replace(tzinfo=timezone.utc)
                    freshness.append(max(0.0, (now - observed).total_seconds()))
        add("water_level_score", _first_indicator(environmental, "water_level_score", "water_level", "river_level"), "environment")
        add("soil_moisture_score", _first_indicator(environmental, "soil_moisture_score", "soil_moisture"), "environment")
        add("drainage_vulnerability", _first_indicator(environmental, "drainage_vulnerability", "waterlogging", "drainage"), "environment")
        add("heat_duration", _score(_first_indicator(environmental, "heat_duration_hours", "heat_duration"), 72), "environment")
        add("ground_movement_score", _first_indicator(environmental, "ground_movement_score", "ground_movement", "tilt"), "environment")
        terrain = _first_indicator(environmental, "terrain_vulnerability", "land_vulnerability")
        add("terrain_vulnerability", terrain, "environment")
        community_count = _first_indicator(environmental, "community_flood_reports", "community_reports")
        if community_count is None:
            community_count = len(community_reports)
        add("community_signal", _score(community_count, 17), "community" if community_count else None)
        image_score = _first_indicator(environmental, "image_evidence_score")
        add("image_evidence_score", image_score, "VISION" if image_score is not None else None)

        # Zone metadata is the geographic and historical baseline. Missing
        # values intentionally remain absent and are handled by weight
        # renormalization in the scorer.
        elevation = _value(zone, "elevation_m")
        add("elevation_vulnerability", _score(max(0.0, 30.0 - float(elevation)) if elevation is not None else None, 30), "geographic")
        add("slope_vulnerability", _score(_value(zone, "slope_deg"), 45), "geographic")
        add("historical_risk", _score(_value(zone, "historical_disaster_frequency"), 5), "historical")
        if "drainage_vulnerability" not in values:
            add("drainage_vulnerability", _value(zone, "drainage_vulnerability"), "geographic")
        if "terrain_vulnerability" not in values:
            add("terrain_vulnerability", _value(zone, "vulnerability_score"), "geographic")
        add("coastal_vulnerability", _value(zone, "coastal_vulnerability"), "geographic")
        population = _value(zone, "population")
        add("population_exposure", _score(population, 50000), "geographic")

        age = max(freshness) if freshness else None
        stale_after = max(1, int(settings.WEATHER_STALE_AFTER_MINUTES)) * 60
        stale = age is not None and age > stale_after
        upper_sources = {source for source in sources if source}
        has_demo = any("DEMO" in source or "SIMULATION" in source for source in upper_sources)
        has_fallback = any("FALLBACK" in source for source in upper_sources)
        has_live = any(source in {"EXTERNAL", "LIVE", "SENSOR", "OPEN_METEO", "OPENWEATHER", "IOT", "USGS", "IMD_CAP", "VISION"} for source in upper_sources)
        if has_fallback:
            freshness.append(float(settings.WEATHER_STALE_AFTER_MINUTES * 60 + 1))
        has_offline = "OFFLINE" in statuses
        has_stale = "STALE" in statuses or stale
        if has_live and (has_demo or has_fallback or has_stale or has_offline):
            data_status = "MIXED"
        elif has_fallback:
            data_status = "FALLBACK"
        elif has_stale:
            data_status = "STALE"
        elif has_live:
            data_status = "LIVE"
        else:
            data_status = "DEMO" if has_demo or not upper_sources else "MANUAL"
        return RiskFeatures(values, available, len(upper_sources), max(freshness) if freshness else None, data_status, stale)


class DeterministicRiskEngine:
    def __init__(self):
        self.weights = self._load_weights()
        self.thresholds = self._load_thresholds()

    @staticmethod
    def _load_thresholds() -> dict[str, float]:
        defaults = {"low": 0.0, "medium": 25.0, "high": 50.0, "critical": 75.0}
        try:
            configured = json.loads(settings.RISK_THRESHOLDS_JSON or "{}")
            for name in ("low", "medium", "high", "critical"):
                if name in configured and math.isfinite(float(configured[name])):
                    defaults[name] = _clamp(configured[name])
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
        if not (defaults["low"] <= defaults["medium"] <= defaults["high"] <= defaults["critical"]):
            return {"low": 0.0, "medium": 25.0, "high": 50.0, "critical": 75.0}
        return defaults

    @staticmethod
    def _load_weights() -> dict[str, dict[str, float]]:
        weights = json.loads(json.dumps(DEFAULT_WEIGHTS))
        try:
            override = json.loads(settings.RISK_WEIGHTS_JSON or "{}")
            for disaster, values in override.items():
                if isinstance(values, dict):
                    weights.setdefault(str(disaster).lower(), {}).update({str(k): float(v) for k, v in values.items() if math.isfinite(float(v)) and float(v) >= 0})
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
        return weights

    def _level(self, score: float) -> SeverityLevel:
        if score >= self.thresholds["critical"]:
            return SeverityLevel.CRITICAL
        if score >= self.thresholds["high"]:
            return SeverityLevel.HIGH
        if score >= self.thresholds["medium"]:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    def score(self, disaster_type: DisasterType | str, features: RiskFeatures) -> RiskResult:
        key = disaster_type.value if isinstance(disaster_type, DisasterType) else str(disaster_type).lower()
        weights = self.weights.get(key, self.weights["other"])
        usable = {name: weight for name, weight in weights.items() if name in features.available and weight > 0}
        total_weight = sum(usable.values())
        score = sum(features.values[name] * weight for name, weight in usable.items()) / total_weight if total_weight else 0.0
        score = round(_clamp(score), 2)
        level = self._level(score)
        # High-value weighted evidence is shown in the UI and persisted for
        # auditability. It is never invented by a language model.
        ranked = sorted(usable, key=lambda name: features.values[name] * usable[name], reverse=True)
        factors = [f"{FEATURE_LABELS.get(name, name.replace('_', ' ').title())}: {features.values[name]:g}/100" for name in ranked[:5] if features.values[name] > 0]
        recommendations = self.recommendations(key, level)
        explanation = f"{key.replace('_', ' ').title()} risk is {score:g}/100 ({level.value.upper()}) based on {', '.join(factors[:3]) or 'limited available evidence'}."
        coverage = len(usable) / max(1, len(weights))
        source_confidence = min(1.0, max(features.source_count, 1) / 3)
        freshness_confidence = 0.25 if features.stale else 1.0 if features.freshness_seconds is not None else .65
        confidence = round(_clamp((coverage * 55 + source_confidence * 30 + freshness_confidence * 15)), 2)
        return RiskResult(score, level, confidence, features.as_dict(), factors, recommendations, explanation, features.data_status, features.freshness_seconds, features.stale)

    @staticmethod
    def recommendations(disaster_type: str, level: SeverityLevel) -> list[str]:
        if level in {SeverityLevel.LOW, SeverityLevel.MEDIUM}:
            return ["Continue monitoring updated observations", "Review local response readiness"]
        common = ["Prepare rescue resources", "Check shelter and hospital capacity", "Monitor the affected zone"]
        if disaster_type in {"flood", "urban_flood"}:
            return common + ["Inspect drainage and water-level reports"]
        if disaster_type == "landslide":
            return common + ["Restrict access to unstable slopes"]
        if disaster_type == "heatwave":
            return common + ["Coordinate welfare checks for vulnerable residents"]
        return common + ["Notify the appropriate response teams"]
