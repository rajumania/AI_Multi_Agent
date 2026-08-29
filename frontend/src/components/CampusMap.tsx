import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { Navigation, RefreshCw } from 'lucide-react';
import { CampusLocation, CampusResource, Incident, LiveEvent, TransportTracking } from '../types';
import { OperatorLocation } from './RealOperationsControls';
import { api } from '../services/api';

// Geocoding helper for the existing response-area location catalog
export const getIncidentCoords = (_location: string): [number, number] => {
  // Exact reporter coordinates and the backend's verified location catalog
  // take precedence. This fallback is intentionally only the AITAM anchor.
  return [18.56517, 84.19587];
};

function resolveIncidentPosition(incident: Incident, locations: CampusLocation[]): { coords: [number, number]; source: 'EXACT' | 'CAMPUS_CATALOG' | 'APPROXIMATE' } {
  if (incident.latitude != null && incident.longitude != null) {
    return { coords: [incident.latitude, incident.longitude], source: 'EXACT' };
  }
  const text = (incident.location || '').toLowerCase();
  const match = locations.find((item) => item.aliases.some((alias) => text.includes(alias.toLowerCase())));
  if (match) return { coords: [match.latitude, match.longitude], source: 'CAMPUS_CATALOG' };
  return { coords: getIncidentCoords(incident.location), source: 'APPROXIMATE' };
}

interface CampusMapProps {
  incidents: Incident[];
  onSelectIncident?: (incident: Incident) => void;
  activeIncidentId?: string;
  selectedResourceId?: string;
  operatorLocation?: OperatorLocation | null;
  /** Events from the command shell's single authenticated WebSocket. */
  liveEvents?: LiveEvent[];
}

export const CampusMap: React.FC<CampusMapProps> = ({
  incidents,
  onSelectIncident,
  activeIncidentId,
  selectedResourceId,
  operatorLocation,
  liveEvents = [],
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  
  // Separate layer groups for map objects
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const routesLayerRef = useRef<L.LayerGroup | null>(null);

  const [resources, setResources] = useState<CampusResource[]>([]);
  const [campusLocations, setCampusLocations] = useState<CampusLocation[]>([]);
  const [filterType, setFilterType] = useState<string>('all');
  const [mapLayer, setMapLayer] = useState<'satellite' | 'standard' | 'navigation' | 'terrain'>('satellite');
  const [loadingResources, setLoadingResources] = useState<boolean>(true);
  const [mouseCoords, setMouseCoords] = useState<{ lat: number; lng: number }>({ lat: 18.56517, lng: 84.19587 });

  const tileLayerRef = useRef<L.LayerGroup | null>(null);

  // Real-time active states
  const [movingVehicles, setMovingVehicles] = useState<{ [rid: string]: any }>({});
  const [activeRoutes, setActiveRoutes] = useState<{ [rid: string]: { coordinates: [number, number][], status: 'active' | 'blocked' } }>({});
  const lastHandledEventRef = useRef<string | null>(null);
  
  // Static preview route before dispatch
  const [staticRoute, setStaticRoute] = useState<{ coordinates: [number, number][], distance: number, eta: number } | null>(null);

  const fetchResources = async () => {
    setLoadingResources(true);
    try {
      const [data, locations] = await Promise.all([api.getResources(), api.getCampusLocations()]);
      setResources(data);
      setCampusLocations(locations);
    } catch (e) {
      console.error('Failed to load map resources', e);
    } finally {
      setLoadingResources(false);
    }
  };

  useEffect(() => {
    fetchResources();
  }, []);

  // Rehydrate persisted transport state so an operator opening or refreshing
  // the command center still sees active assignment-bound GPS and route data.
  // WebSocket events remain the live update path after this initial snapshot.
  useEffect(() => {
    let cancelled = false;
    const activeIncidents = incidents.filter((incident) => !['resolved', 'closed'].includes(String(incident.status).toLowerCase()));
    if (activeIncidents.length === 0) return () => { cancelled = true; };

    const loadActiveTransport = async () => {
      const snapshots: TransportTracking[] = [];
      await Promise.all(activeIncidents.map(async (incident) => {
        try {
          const assignments = await api.getIncidentAssignments(incident.incident_id);
          await Promise.all(assignments
            .filter((assignment) => String(assignment.department).toUpperCase() === 'TRANSPORT' && ['EN_ROUTE', 'ON_SCENE'].includes(String(assignment.status).toUpperCase()))
            .map(async (assignment) => {
              try {
                snapshots.push(await api.getTransportTracking(assignment.id));
              } catch {
                // A newly-created assignment may not have a tracking snapshot yet.
              }
            }));
        } catch {
          // The socket and normal resource feed remain available if a snapshot fails.
        }
      }));
      if (cancelled) return;

      setMovingVehicles((previous) => {
        const next = { ...previous };
        snapshots.forEach((snapshot) => {
          if (!snapshot.resource_id || snapshot.current_latitude == null || snapshot.current_longitude == null) return;
          next[snapshot.resource_id] = {
            ...next[snapshot.resource_id],
            resourceId: snapshot.resource_id,
            latitude: snapshot.current_latitude,
            longitude: snapshot.current_longitude,
            status: snapshot.status,
            etaSeconds: snapshot.eta_seconds,
            distanceRemaining: snapshot.route?.distance_meters != null ? snapshot.route.distance_meters / 1000 : undefined,
            source: snapshot.gps_source,
            routeVersion: snapshot.route?.route_version,
            timestamp: snapshot.last_gps_update,
          };
        });
        return next;
      });
      setActiveRoutes((previous) => {
        const next = { ...previous };
        snapshots.forEach((snapshot) => {
          const coordinates = snapshot.route?.coordinates;
          if (!snapshot.resource_id || !coordinates || coordinates.length < 2) return;
          next[snapshot.resource_id] = {
            coordinates,
            status: snapshot.route?.status === 'blocked' ? 'blocked' : 'active',
          };
        });
        return next;
      });
    };

    void loadActiveTransport();
    return () => { cancelled = true; };
  }, [incidents]);

  // 1. Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [18.56517, 84.19587],
      zoom: 16,
      zoomControl: true,
    });

    const tilesGroup = L.layerGroup().addTo(map);
    const markersGroup = L.layerGroup().addTo(map);
    const routesGroup = L.layerGroup().addTo(map);

    tileLayerRef.current = tilesGroup;
    markersLayerRef.current = markersGroup;
    routesLayerRef.current = routesGroup;
    mapInstanceRef.current = map;

    map.on('mousemove', (e) => {
      setMouseCoords({ lat: Number(e.latlng.lat.toFixed(4)), lng: Number(e.latlng.lng.toFixed(4)) });
    });

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Tile Layer Switcher effect
  useEffect(() => {
    if (!tileLayerRef.current) return;
    const tilesGroup = tileLayerRef.current;
    tilesGroup.clearLayers();

    if (mapLayer === 'satellite') {
      // High resolution Satellite imagery base
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
        maxZoom: 19,
      }).addTo(tilesGroup);

      // Transparent Road vector + Building names overlay
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; CARTO',
        maxZoom: 19,
        pane: 'shadowPane'
      }).addTo(tilesGroup);
    } else if (mapLayer === 'standard') {
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(tilesGroup);
    } else if (mapLayer === 'navigation') {
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; CARTO &copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(tilesGroup);
    } else if (mapLayer === 'terrain') {
      L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
        attribution: 'Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)',
        maxZoom: 17,
      }).addTo(tilesGroup);
    }
  }, [mapLayer]);


  // 2. Consume the command shell's existing real-time event stream. The App
  // owns the single authenticated /api/v1/events/ws connection; this map must
  // not create a second socket for the same browser view.
  useEffect(() => {
    const data = liveEvents[0];
    if (!data) return;
    const eventKey = `${data.event_name}:${data.timestamp || ''}:${data.resource_id || ''}:${data.route_version || ''}`;
    if (lastHandledEventRef.current === eventKey) return;
    lastHandledEventRef.current = eventKey;

    try {

        if (['route_selected', 'transport_route_created', 'transport_route_updated'].includes(data.event_name)) {
          setActiveRoutes(prev => ({
            ...prev,
            [data.resource_id as string]: {
              coordinates: data.coordinates as [number, number][],
              status: 'active'
            }
          }));
          setMovingVehicles(prev => {
            const current = prev[data.resource_id as string];
            if (!current) return prev;
            return {
              ...prev,
              [data.resource_id as string]: {
                ...current,
                etaSeconds: data.eta_seconds,
                distanceRemaining: data.distance_meters != null ? data.distance_meters / 1000 : current.distanceRemaining,
                routeVersion: data.route_version,
                timestamp: data.timestamp,
              },
            };
          });
        } else if (data.event_name === 'route_blocked') {
          setActiveRoutes(prev => {
            const current = prev[data.resource_id as string];
            if (!current) return prev;
            return {
              ...prev,
              [data.resource_id as string]: {
                ...current,
                status: 'blocked'
              }
            };
          });
        } else if (data.event_name === 'route_recalculated') {
          // Clear older routes and set new recalculated active route
          setActiveRoutes(prev => {
            const next = { ...prev };
            // Mark previous as blocked
            if (next[data.resource_id as string]) {
              next[data.resource_id as string].status = 'blocked';
            }
            next[`${data.resource_id}_new`] = {
              coordinates: data.coordinates as [number, number][],
              status: 'active'
            };
            return next;
          });
        } else if (data.event_name === 'transport_eta_updated') {
          setMovingVehicles(prev => {
            const current = prev[data.resource_id as string];
            if (!current) return prev;
            return {
              ...prev,
              [data.resource_id as string]: {
                ...current,
                etaSeconds: data.eta_seconds,
                distanceRemaining: data.distance_meters != null ? data.distance_meters / 1000 : current.distanceRemaining,
                routeVersion: data.route_version,
                timestamp: data.timestamp,
              },
            };
          });
        } else if (['vehicle_location_updated', 'transport_location_updated'].includes(data.event_name)) {
          // Update local resources state coords to move marker in real-time
          setResources(prev => prev.map(r => r.resource_id === data.resource_id ? {
            ...r,
            latitude: data.latitude,
            longitude: data.longitude,
            availability_status: 'busy'
          } : r));

          setMovingVehicles(prev => ({
            ...prev,
            [data.resource_id as string]: {
              resourceId: data.resource_id,
              latitude: data.latitude,
              longitude: data.longitude,
              status: data.status,
              distanceRemaining: data.distance_remaining,
              etaSeconds: data.eta_seconds,
              routeCoordinates: data.route_coordinates,
              source: data.source || 'UNAVAILABLE',
              routeVersion: data.route_version,
              timestamp: data.timestamp,
            }
          }));
        } else if (['vehicle_arrived', 'transport_arrived'].includes(data.event_name)) {
          // Clear active routing lines and overlays
          setMovingVehicles(prev => {
            const next = { ...prev };
            delete next[data.resource_id as string];
            return next;
          });
          setActiveRoutes(prev => {
            const next = { ...prev };
            delete next[data.resource_id as string];
            delete next[`${data.resource_id}_new`];
            return next;
          });
          void fetchResources();
        }
      } catch (e) {
        console.error('Error handling real-time map event:', e);
      }
  }, [liveEvents, fetchResources]);

  // 3. Static preview route calculation
  useEffect(() => {
    if (!selectedResourceId || !activeIncidentId) {
      setStaticRoute(null);
      return;
    }

    const res = resources.find(r => r.resource_id === selectedResourceId);
    const inc = incidents.find(i => i.incident_id === activeIncidentId);

    if (!res || !inc) return;

    const routeRequest = res.latitude != null && res.longitude != null && inc.latitude != null && inc.longitude != null
      ? api.calculateCoordinateRoute({ origin: res.location, destination: inc.location, origin_lat: res.latitude, origin_lng: res.longitude, destination_lat: inc.latitude, destination_lng: inc.longitude })
      : api.calculateRoute(res.location, inc.location);
    routeRequest
      .then(data => {
        setStaticRoute({
          coordinates: data.coordinates,
          distance: data.distance_meters,
          eta: data.eta_minutes
        });
      })
      .catch(err => console.error('Failed to calculate preview route', err));
  }, [selectedResourceId, activeIncidentId, resources, incidents]);

  // 4. Center and Fit Bounds
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    const map = mapInstanceRef.current;

    // A. Focus on moving vehicle
    const activeMvs = Object.keys(movingVehicles);
    if (activeMvs.length > 0 && activeIncidentId) {
      const mv = movingVehicles[activeMvs[0]];
      const inc = incidents.find(i => i.incident_id === activeIncidentId);
      if (mv && inc) {
        const [incLat, incLng] = resolveIncidentPosition(inc, campusLocations).coords;
        const bounds = L.latLngBounds([[mv.latitude, mv.longitude], [incLat, incLng]]);
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
        return;
      }
    }

    // B. Fit bounds for selected static resource & incident
    if (activeIncidentId) {
      const inc = incidents.find(i => i.incident_id === activeIncidentId);
      if (inc) {
          const [incLat, incLng] = resolveIncidentPosition(inc, campusLocations).coords;
        if (selectedResourceId) {
          const res = resources.find(r => r.resource_id === selectedResourceId);
          if (res && res.latitude && res.longitude) {
            const bounds = L.latLngBounds([[incLat, incLng], [res.latitude, res.longitude]]);
            map.fitBounds(bounds, { padding: [50, 50] });
            return;
          }
        }
        // Fallback: center on incident
        map.setView([incLat, incLng], 17);
      }
    }
  }, [activeIncidentId, selectedResourceId, movingVehicles, incidents, resources, campusLocations]);

  // 5. Draw Markers & Routing Layers
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current || !routesLayerRef.current) return;

    const markersLayer = markersLayerRef.current;
    const routesLayer = routesLayerRef.current;

    markersLayer.clearLayers();
    routesLayer.clearLayers();

    // A. Plot Incidents
    if (filterType === 'all' || filterType === 'incidents') {
      incidents.forEach((inc) => {
        const position = resolveIncidentPosition(inc, campusLocations);
        const [lat, lng] = position.coords;
        const isCritical = inc.severity === 'critical' || inc.severity === 'high';
        
        // Highlight active incident in view
        const isActive = inc.incident_id === activeIncidentId;

        const markerHtml = `
          <div style="
            background: ${isCritical ? '#dc2626' : '#f59e0b'};
            color: #ffffff;
            border: ${isActive ? '3px solid #ffffff' : '2px solid #ffffff'};
            box-shadow: 0 0 ${isActive ? '15px' : '8px'} ${isCritical ? 'rgba(220, 38, 38, 0.8)' : 'rgba(245, 158, 11, 0.8)'};
            border-radius: 50%;
            width: ${isActive ? '36px' : '30px'};
            height: ${isActive ? '36px' : '30px'};
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: ${isActive ? '16px' : '13px'};
            font-weight: bold;
            cursor: pointer;
            animation: pulse 1.5s infinite;
          ">
            🚨
          </div>
        `;

        const icon = L.divIcon({
          html: markerHtml,
          className: 'custom-incident-pin',
          iconSize: isActive ? [36, 36] : [30, 30],
          iconAnchor: isActive ? [18, 18] : [15, 15],
        });

        const marker = L.marker([lat, lng], { icon }).addTo(markersLayer);

        // Safety perimeter circle
        if (isCritical) {
          L.circle([lat, lng], {
            radius: 70,
            color: '#dc2626',
            fillColor: '#fee2e2',
            fillOpacity: 0.15,
            weight: 1.2,
            dashArray: '3, 5',
          }).addTo(markersLayer);
        }

        marker.bindPopup(`
          <div style="font-family: Inter, sans-serif; min-width: 190px; padding: 2px;">
            <div style="font-weight: 700; font-size: 0.85rem; color: #0f172a; margin-bottom: 2px;">${inc.incident_id}</div>
            <div style="color: #dc2626; font-size: 0.7rem; font-weight: 600; text-transform: uppercase;">${inc.incident_type} • ${inc.severity}</div>
            <div style="font-size: 0.75rem; color: #475569; margin: 4px 0;">📍 ${inc.location}</div>
            <div style="font-size: 0.65rem; color: #64748b;">Source: ${position.source} · ${lat.toFixed(6)}, ${lng.toFixed(6)}</div>
            <div style="font-size: 0.65rem; color: #64748b;">Reported: ${inc.created_at ? new Date(inc.created_at).toLocaleString() : 'Unavailable'}</div>
            <div style="font-size: 0.7rem; color: #0284c7; font-weight: 600;">Status: ${inc.status.toUpperCase()}</div>
          </div>
        `);

        if (onSelectIncident) {
          marker.on('click', () => onSelectIncident(inc));
        }
      });
    }

    // B. Plot the centralized campus catalog. These are existing project
    // coordinates and remain visibly distinguishable from exact incident GPS.
    campusLocations.forEach((location) => {
      L.circleMarker([location.latitude, location.longitude], {
        radius: 5,
        color: '#0f766e',
        fillColor: '#99f6e4',
        fillOpacity: 0.75,
        weight: 1,
      }).addTo(markersLayer)
        .bindTooltip(`${location.name} · ${location.verification_status.split('_').join(' ')}`, { direction: 'top' });
    });

    // C. Plot Resources (with overlap/offset logic)
    const seenLocations: { [key: string]: number } = {};

    resources.forEach((res) => {
      if (!res.latitude || !res.longitude) return;

      // Category filter check
      if (filterType === 'ambulances' && res.resource_type !== 'ambulance') return;
      if (filterType === 'security' && res.resource_type !== 'security') return;
      if (filterType === 'shelters' && res.resource_type !== 'shelter') return;
      if (filterType === 'vehicles' && res.resource_type !== 'vehicle') return;

      // Check overlap
      const locKey = `${res.latitude.toFixed(5)}_${res.longitude.toFixed(5)}`;
      const overlapCount = seenLocations[locKey] || 0;
      seenLocations[locKey] = overlapCount + 1;

      let lat = res.latitude;
      let lng = res.longitude;
      if (overlapCount > 0) {
        const angle = (overlapCount * 2 * Math.PI) / 8;
        const radius = 0.00015; // Shift overlapping markers by ~15m
        lat += Math.sin(angle) * radius;
        lng += Math.cos(angle) * radius;
      }

      const isSelected = res.resource_id === selectedResourceId;
      const isAvailable = res.availability_status === 'available';

      let iconEmoji = '📍';
      if (res.resource_type === 'ambulance') iconEmoji = '🚑';
      else if (res.resource_type === 'security') iconEmoji = '🛡️';
      else if (res.resource_type === 'first_aid') iconEmoji = '🏥';
      else if (res.resource_type === 'shelter') iconEmoji = '🏠';
      else if (res.resource_type === 'vehicle') iconEmoji = '🚐';
      else if (res.resource_type === 'fire_response') iconEmoji = '🚒';

      const resMarkerHtml = `
        <div style="
          background: #ffffff;
          border: ${isSelected ? '3px solid #3b82f6' : `2px solid ${isAvailable ? '#10b981' : '#ef4444'}`};
          box-shadow: 0 2px 6px ${isSelected ? 'rgba(59, 130, 246, 0.6)' : 'rgba(0,0,0,0.15)'};
          border-radius: 50%;
          width: ${isSelected ? '32px' : '28px'};
          height: ${isSelected ? '32px' : '28px'};
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: ${isSelected ? '15px' : '13px'};
          cursor: pointer;
          transition: transform 0.2s;
        " class="${isSelected ? 'selected-marker' : ''}">
          ${iconEmoji}
        </div>
      `;

      const resIcon = L.divIcon({
        html: resMarkerHtml,
        className: 'custom-resource-pin',
        iconSize: isSelected ? [32, 32] : [28, 28],
        iconAnchor: isSelected ? [16, 16] : [14, 14],
      });

      const resMarker = L.marker([lat, lng], { icon: resIcon }).addTo(markersLayer);

      resMarker.bindPopup(`
        <div style="font-family: Inter, sans-serif; min-width: 175px; padding: 2px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
            <span style="font-weight: 700; font-size: 0.8rem; color: #0f172a;">${res.resource_id}</span>
            <span style="font-size: 0.65rem; background: ${isAvailable ? '#dcfce7' : '#fee2e2'}; color: ${isAvailable ? '#065f46' : '#991b1b'}; padding: 1px 5px; border-radius: 4px; font-weight: 700;">
              ${res.availability_status.toUpperCase()}
            </span>
          </div>
          <div style="font-size: 0.75rem; font-weight: 600; color: #1e293b;">${res.name}</div>
          <div style="font-size: 0.7rem; color: #64748b; margin-top: 3px;">📍 ${res.location}</div>
          ${res.contact ? `<div style="font-size: 0.7rem; color: #2563eb; margin-top: 2px;">📻 ${res.contact}</div>` : ''}
        </div>
      `);
    });

    // Plot the operator/device position only when supplied by real browser GPS.
    if (operatorLocation) {
      const operatorIcon = L.divIcon({
        html: `<div style="background:#2563eb;color:#fff;border:2px solid #fff;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-weight:800;box-shadow:0 2px 8px rgba(0,0,0,.35)">GPS</div>`,
        className: 'operator-location-pin',
        iconSize: [30, 30],
        iconAnchor: [15, 15],
      });
      L.marker([operatorLocation.latitude, operatorLocation.longitude], { icon: operatorIcon })
        .addTo(markersLayer)
        .bindTooltip(`REAL GPS • ${operatorLocation.latitude.toFixed(6)}, ${operatorLocation.longitude.toFixed(6)}`);
    }

    // D. Draw Static Preview Route (if selected resource route is not yet active)
    if (staticRoute && staticRoute.coordinates.length > 0 && Object.keys(activeRoutes).length === 0) {
      const routePoly = L.polyline(staticRoute.coordinates, {
        color: '#3b82f6',
        weight: 5,
        opacity: 0.75,
        dashArray: '2, 6'
      }).addTo(routesLayer);

      routePoly.bindTooltip(`⏱ Route Preview: ${staticRoute.eta} min (${(staticRoute.distance / 1000).toFixed(2)} km)`, { permanent: false, sticky: true });

      // Draw direction arrows along static route
      drawDirectionalArrows(staticRoute.coordinates, '#3b82f6', routesLayer);
    }

    // E. Draw WebSocket Active and Blocked Routes
    Object.keys(activeRoutes).forEach(rid => {
      const route = activeRoutes[rid];
      if (!route || route.coordinates.length === 0) return;

      const isBlocked = route.status === 'blocked';
      
      const routePoly = L.polyline(route.coordinates, {
        color: isBlocked ? '#ef4444' : '#10b981',
        weight: 5,
        opacity: 0.85,
        dashArray: isBlocked ? '5, 8' : 'none'
      }).addTo(routesLayer);

      if (isBlocked) {
        routePoly.bindTooltip('❌ ROAD BLOCKED - DETOUR COMPUTED', { sticky: true });
        
        // Add a block icon at the midpoint of the route
        const midIdx = Math.floor(route.coordinates.length / 2);
        const midPoint = route.coordinates[midIdx];
        
        const blockIcon = L.divIcon({
          html: `<div style="font-size: 16px; background: white; border-radius: 50%; box-shadow: 0 0 5px rgba(0,0,0,0.3); width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; border: 1.5px solid red;">❌</div>`,
          className: 'block-mid-icon',
          iconSize: [22, 22],
          iconAnchor: [11, 11]
        });
        L.marker(midPoint, { icon: blockIcon }).addTo(routesLayer)
          .bindTooltip('Road Blockage', { permanent: true, direction: 'top' });
      } else {
        routePoly.bindTooltip(`✅ Active Response Route (${rid})`, { sticky: true });
        drawDirectionalArrows(route.coordinates, '#10b981', routesLayer);
      }
    });

  }, [incidents, resources, campusLocations, filterType, activeIncidentId, selectedResourceId, staticRoute, activeRoutes, operatorLocation]);

  // Helper to draw CSS rotated arrow markers along a polyline
  const drawDirectionalArrows = (coordinates: [number, number][], color: string, layer: L.LayerGroup) => {
    const totalPoints = coordinates.length;
    if (totalPoints < 2) return;

    // Draw arrows at intervals along the route
    const step = Math.max(3, Math.floor(totalPoints / 4));
    
    for (let i = 0; i < totalPoints - 1; i += step) {
      const p1 = coordinates[i];
      const p2 = coordinates[i + 1];
      
      // Calculate angle between coordinates (heading direction)
      const lat1 = p1[0], lng1 = p1[1];
      const lat2 = p2[0], lng2 = p2[1];
      const angle = Math.atan2(lng2 - lng1, lat2 - lat1) * 180 / Math.PI;
      const midLat = (lat1 + lat2) / 2;
      const midLng = (lng1 + lng2) / 2;

      const arrowIcon = L.divIcon({
        html: `<div style="transform: rotate(${angle - 90}deg); font-size: 12px; color: ${color}; text-shadow: 0 0 3px #ffffff; font-weight: bold;">▲</div>`,
        className: 'route-arrow-icon',
        iconSize: [14, 14],
        iconAnchor: [7, 7]
      });

      L.marker([midLat, midLng], { icon: arrowIcon }).addTo(layer);
    }
  };

  return (
    <div className="panel-card" style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div className="panel-header" style={{ padding: '0.65rem 1rem', background: '#0f172a', color: 'white' }}>
        <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Navigation size={18} color="#38bdf8" />
          <span style={{ fontWeight: 700 }}>Interactive Command & Response Map</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            className="btn"
            style={{ fontSize: '0.68rem', padding: '0.2rem 0.5rem', background: '#1e293b', border: '1px solid #475569', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '0.2rem' }}
            onClick={fetchResources}
            disabled={loadingResources}
            title="Sync Physical GPS Assets"
          >
            <RefreshCw size={11} className={loadingResources ? 'spin' : ''} />
            <span>Sync</span>
          </button>
          <span className="panel-tag" style={{ fontSize: '0.65rem', background: '#0284c7', color: 'white', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
            AITAM RESPONSE AREA
          </span>
        </div>
      </div>

      {/* Filter & Map Layer Toolbar */}
      <div style={{ display: 'flex', gap: '0.35rem', padding: '0.45rem 0.85rem', background: '#0f172a', borderBottom: '1px solid #334155', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', marginRight: '0.2rem', textTransform: 'uppercase' }}>Layer:</span>
          {[
            { id: 'satellite', label: '🛰️ SATELLITE + ROADS' },
            { id: 'standard', label: '🗺️ STANDARD OSM' },
            { id: 'navigation', label: '🚗 NAVIGATION' },
            { id: 'terrain', label: '⛰️ TERRAIN' },
          ].map(layer => (
            <button
              key={layer.id}
              style={{
                fontSize: '0.63rem',
                padding: '0.15rem 0.5rem',
                borderRadius: '4px',
                border: `1px solid ${mapLayer === layer.id ? '#3b82f6' : '#334155'}`,
                background: mapLayer === layer.id ? '#1d4ed8' : '#1e293b',
                color: mapLayer === layer.id ? '#ffffff' : '#cbd5e1',
                cursor: 'pointer',
                fontWeight: 700
              }}
              onClick={() => setMapLayer(layer.id as any)}
            >
              {layer.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', marginRight: '0.2rem', textTransform: 'uppercase' }}>Filter:</span>
          {['all', 'incidents', 'ambulances', 'security', 'shelters', 'vehicles'].map(type => (
            <button
              key={type}
              className={`filter-chip ${filterType === type ? 'active' : ''}`}
              style={{
                fontSize: '0.63rem',
                padding: '0.15rem 0.45rem',
                borderRadius: '4px',
                border: `1px solid ${filterType === type ? '#0284c7' : '#334155'}`,
                background: filterType === type ? '#0284c7' : '#1e293b',
                color: filterType === type ? '#ffffff' : '#94a3b8',
                cursor: 'pointer',
                fontWeight: 600
              }}
              onClick={() => setFilterType(type)}
            >
              {type === 'all' && 'All'}
              {type === 'incidents' && `🚨 Incidents (${incidents.length})`}
              {type === 'ambulances' && '🚑 Ambulances'}
              {type === 'security' && '🛡️ Security'}
              {type === 'shelters' && '🏛️ Shelters'}
              {type === 'vehicles' && '🚐 Shuttles'}
            </button>
          ))}
        </div>
      </div>


      <div className="panel-body" style={{ padding: 0, flex: 1, position: 'relative', minHeight: '350px' }}>
        {/* Leaflet Container */}
        <div className="campus-map-canvas" ref={mapContainerRef} style={{ width: '100%', height: '100%', minHeight: '350px', zIndex: 1 }} />

        {/* Legend Panel overlay */}
        <div style={{
          position: 'absolute',
          top: '10px',
          right: '10px',
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(4px)',
          border: '1px solid #cbd5e1',
          borderRadius: '6px',
          padding: '8px 10px',
          fontSize: '0.7rem',
          color: '#334155',
          zIndex: 1000,
          boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
          pointerEvents: 'auto',
          minWidth: '130px'
        }}>
          <strong style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '3px', marginBottom: '3px', fontSize: '0.72rem' }}>Map Legend</strong>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>BUILD <span style={{ color: '#64748b' }}>Vulnerable Zone</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>🔴 <span style={{ color: '#64748b' }}>Incident</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>🚑 <span style={{ color: '#64748b' }}>Ambulance</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>🛡️ <span style={{ color: '#64748b' }}>Security Squad</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>🏥 <span style={{ color: '#64748b' }}>Medical Unit</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>🚐 <span style={{ color: '#64748b' }}>Emergency Vehicle</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>🏠 <span style={{ color: '#64748b' }}>Muster Shelter</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', height: '14px' }}>
            <div style={{ width: '16px', height: '3px', background: '#3b82f6', borderStyle: 'dashed', borderWidth: '1px' }}></div>
            <span style={{ color: '#64748b' }}>Route Preview</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', height: '14px' }}>
            <div style={{ width: '16px', height: '3px', background: '#10b981' }}></div>
            <span style={{ color: '#64748b' }}>Active Route</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', height: '14px' }}>
            <div style={{ width: '16px', height: '3px', background: '#ef4444', borderStyle: 'dashed', borderWidth: '1px' }}></div>
            <span style={{ color: '#ef4444', fontWeight: 600 }}>❌ Blocked Route</span>
          </div>
        </div>

        {/* Active Moving Vehicle HUD Overlay */}
        {Object.keys(movingVehicles).length > 0 && (() => {
          const mvKey = Object.keys(movingVehicles)[0];
          const mv = movingVehicles[mvKey];
          const inc = activeIncidentId ? incidents.find(i => i.incident_id === activeIncidentId) : null;
          const res = resources.find(r => r.resource_id === mvKey);
          
          return (
            <div style={{
              position: 'absolute',
              top: '10px',
              left: '10px',
              background: 'rgba(15, 23, 42, 0.92)',
              backdropFilter: 'blur(8px)',
              border: '1px solid #0284c7',
              borderRadius: '8px',
              padding: '10px 14px',
              fontSize: '0.75rem',
              color: '#ffffff',
              zIndex: 1000,
              boxShadow: '0 6px 16px rgba(0,0,0,0.3)',
              minWidth: '220px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', borderBottom: '1px solid #334155', paddingBottom: '4px' }}>
                <span style={{ fontWeight: 800, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  🚑 ACTIVE VEHICLE DISPATCH
                </span>
                <span style={{ fontSize: '0.65rem', background: '#0284c7', color: '#ffffff', padding: '1px 6px', borderRadius: '4px', fontWeight: 700 }}>
                  {(mv.status || 'EN_ROUTE').toUpperCase()}
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                <div><strong>Asset:</strong> <span style={{ color: '#38bdf8', fontWeight: 700 }}>{mv.resourceId}</span> {res ? `(${res.name})` : ''}</div>
                <div><strong>Source:</strong> {res?.location || 'Response Base'}</div>
                <div><strong>Destination:</strong> <span style={{ color: '#fca5a5' }}>{inc?.location || 'Emergency Site'}</span></div>
                <div><strong>ETA:</strong> <span style={{ color: '#4ade80', fontWeight: 700 }}>{typeof mv.etaSeconds === 'number' ? `${Math.floor(mv.etaSeconds / 60)}m ${Math.round(mv.etaSeconds % 60)}s` : 'ETA unavailable'}</span></div>
                <div><strong>Distance:</strong> <span style={{ color: '#fde047', fontWeight: 700 }}>{typeof mv.distanceRemaining === 'number' ? `${mv.distanceRemaining.toFixed(2)} km` : 'Unavailable'}</span></div>
                <div style={{ marginTop: '4px', paddingTop: '4px', borderTop: '1px dashed #334155', fontSize: '0.65rem', color: '#94a3b8', fontFamily: 'monospace' }}>
                  🛰️ LOCATION SOURCE: <strong style={{ color: mv.source === 'REAL' ? '#4ade80' : mv.source === 'SIMULATED' ? '#fbbf24' : '#f87171' }}>{mv.source === 'REAL' ? 'REAL GPS' : mv.source === 'SIMULATED' ? 'SIMULATED' : 'UNAVAILABLE'}</strong>
                  {mv.timestamp && <span> · LAST UPDATE {new Date(mv.timestamp).toLocaleTimeString()}</span>}
                </div>
              </div>
            </div>
          );
        })()}

        {/* Live Coordinate display widget */}
        <div style={{
          position: 'absolute',
          bottom: '8px',
          left: '8px',
          background: 'rgba(15, 23, 42, 0.9)',
          border: '1px solid #334155',
          borderRadius: '4px',
          padding: '3px 8px',
          fontSize: '0.65rem',
          color: '#cbd5e1',
          zIndex: 1000,
          fontFamily: 'monospace',
          boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
        }}>
          🛰️ GPS MODE: DEMO / SIMULATED • {mouseCoords.lat.toFixed(4)}N, {mouseCoords.lng.toFixed(4)}E (WGS-84) • LIVE TELEMETRY STREAM
        </div>
      </div>
    </div>
  );
};
