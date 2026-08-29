import { describe, expect, it } from 'vitest';
import { isValidGeoJSONGeometry } from './geojson';

describe('DisasterRiskMap geometry validation', () => {
  it('accepts valid point, line and polygon geometry', () => {
    expect(isValidGeoJSONGeometry({ type: 'Point', coordinates: [84.02, 28.21] })).toBe(true);
    expect(isValidGeoJSONGeometry({ type: 'LineString', coordinates: [[84.01, 28.20], [84.02, 28.21]] })).toBe(true);
    expect(isValidGeoJSONGeometry({ type: 'Polygon', coordinates: [[[84.01, 28.20], [84.02, 28.20], [84.02, 28.21], [84.01, 28.20]]] })).toBe(true);
  });

  it('rejects malformed or non-finite geometry without throwing', () => {
    expect(isValidGeoJSONGeometry(null)).toBe(false);
    expect(isValidGeoJSONGeometry({ type: 'Polygon', coordinates: 'invalid' })).toBe(false);
    expect(isValidGeoJSONGeometry({ type: 'Point', coordinates: [84.02, Number.NaN] })).toBe(false);
  });
});
