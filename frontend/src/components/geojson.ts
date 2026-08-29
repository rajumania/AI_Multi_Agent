export const isValidGeoJSONGeometry = (geometry: any): boolean => {
  if (!geometry || !['Point', 'LineString', 'Polygon'].includes(geometry.type) || !Array.isArray(geometry.coordinates)) return false;
  const walk = (value: any): boolean => Array.isArray(value) ? (value.length === 0 || (typeof value[0] === 'number' ? value.length >= 2 && Number.isFinite(value[0]) && Number.isFinite(value[1]) : value.every(walk))) : false;
  return walk(geometry.coordinates);
};
