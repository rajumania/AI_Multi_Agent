// ---------------------------------------------------------------------------
// Command Center 3D — imperative three.js scene (Phase 3).
//
// Builds the 3D constellation of agent nodes and drives them entirely from the
// REAL Phase 2 realtime state: every frame, each node is asked to reflect the
// status DERIVED from actual backend events (no timers, no scripted sequence).
// The scene owns only presentation — camera, lights, orbit, render loop — and
// exposes `setIncident` so the React layer can push the latest live state in.
//
// Pure three.js (no React here). WebGL creation is guarded; callers should use
// `isWebGLAvailable()` and/or catch a throw from `createCommandCenterScene` to
// fall back to the DOM-only view. `dispose()` releases every GPU resource and
// listener so the lazy tab can mount/unmount cleanly (Phase 15 cleanup rule).
// ---------------------------------------------------------------------------

import * as THREE from 'three';
import { AGENT_CONNECTIONS, VISUAL_AGENTS } from './agentCatalog';
import { STATUS_VISUALS, deriveAgentDisplayStatus, type DisplayStatus } from './agentStatus';
import { createAgentNode, type AgentNodeHandle } from './AgentNode';
import type { IncidentWorkflowState } from '../realtime/workflowReducer';

export interface CommandCenterSceneHandle {
  /** Push the latest real incident workflow state (or undefined when none). */
  setIncident: (incident: IncidentWorkflowState | undefined) => void;
  /** Set the selected agent to update visual outlines in 3D. */
  setSelectedAgent: (key: string | null) => void;
  /** Tear down the renderer, listeners and all GPU resources. */
  dispose: () => void;
}

/** Cheap, side-effect-free probe for WebGL support (no context is retained). */
export function isWebGLAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    );
  } catch {
    return false;
  }
}

// Statuses that indicate the node's outbound links should "carry signal".
const ACTIVE_FOR_LINKS: ReadonlySet<DisplayStatus> = new Set<DisplayStatus>([
  'WORKING',
  'COMPLETED',
  'WAITING_APPROVAL',
]);

export function createCommandCenterScene(
  container: HTMLElement,
  onSelectAgent?: (key: string | null) => void,
): CommandCenterSceneHandle {
  const width = container.clientWidth || 1;
  const height = container.clientHeight || 1;

  // Renderer — alpha so the CSS backdrop shows through. Throws if WebGL is
  // unavailable; the caller catches this and renders the DOM fallback.
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height, false);
  renderer.setClearColor(0x000000, 0);
  renderer.domElement.style.width = '100%';
  renderer.domElement.style.height = '100%';
  renderer.domElement.style.display = 'block';
  renderer.domElement.style.touchAction = 'none';
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(48, width / height, 0.1, 100);

  // Lighting — soft ambient plus two tinted key lights for a command-center feel.
  const ambient = new THREE.AmbientLight(0xb9c7ff, 0.75);
  scene.add(ambient);
  const keyLight = new THREE.DirectionalLight(0x8fd0ff, 1.1);
  keyLight.position.set(4, 6, 5);
  scene.add(keyLight);
  const rimLight = new THREE.DirectionalLight(0x6f5cff, 0.6);
  rimLight.position.set(-5, -2, -4);
  scene.add(rimLight);

  // Faint ground grid for depth reference.
  const grid = new THREE.GridHelper(14, 14, 0x334155, 0x1e293b);
  grid.position.y = -3.2;
  const gridMaterial = grid.material as THREE.Material | THREE.Material[];
  if (Array.isArray(gridMaterial)) {
    gridMaterial.forEach((m) => {
      m.transparent = true;
      m.opacity = 0.18;
    });
  } else {
    gridMaterial.transparent = true;
    gridMaterial.opacity = 0.18;
  }
  scene.add(grid);

  // Nodes — one per visual agent, keyed by its REAL backend node key.
  const positionByKey: Record<string, readonly [number, number, number]> = {};
  const nodes: Array<{ key: string; node: AgentNodeHandle }> = [];
  for (const agent of VISUAL_AGENTS) {
    positionByKey[agent.key] = agent.position;
    const node = createAgentNode(agent.accent, agent.position);
    scene.add(node.group);
    nodes.push({ key: agent.key, node });
  }
  // Connector lines — resolved from catalog key-pairs to node positions. Base
  // color is slate; when the source node is active it brightens toward accent.
  const accentByKey: Record<string, string> = {};
  for (const agent of VISUAL_AGENTS) accentByKey[agent.key] = agent.accent;

  const baseLineColor = new THREE.Color(0x334155);
  const links: Array<{
    material: THREE.LineBasicMaterial;
    geometry: THREE.BufferGeometry;
    fromKey: string;
    activeColor: THREE.Color;
  }> = [];
  for (const [fromKey, toKey] of AGENT_CONNECTIONS) {
    const from = positionByKey[fromKey];
    const to = positionByKey[toKey];
    if (!from || !to) continue;
    const geometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(from[0], from[1], from[2]),
      new THREE.Vector3(to[0], to[1], to[2]),
    ]);
    const material = new THREE.LineBasicMaterial({
      color: baseLineColor.clone(),
      transparent: true,
      opacity: 0.14,
    });
    const line = new THREE.Line(geometry, material);
    scene.add(line);
    links.push({ material, geometry, fromKey, activeColor: new THREE.Color(accentByKey[fromKey] || '#38bdf8') });
  }

  // Data-flow particles along active connections.
  const maxFlowParticles = 100;
  const flowGeometry = new THREE.BufferGeometry();
  const flowPositions = new Float32Array(maxFlowParticles * 3);
  for (let i = 0; i < maxFlowParticles * 3; i++) flowPositions[i] = 9999;
  flowGeometry.setAttribute('position', new THREE.BufferAttribute(flowPositions, 3));

  const flowMaterial = new THREE.PointsMaterial({
    color: new THREE.Color('#93c5fd'),
    size: 0.045,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const flowPoints = new THREE.Points(flowGeometry, flowMaterial);
  scene.add(flowPoints);

  interface FlowParticle {
    fromPos: THREE.Vector3;
    toPos: THREE.Vector3;
    progress: number;
    speed: number;
  }
  let activeParticles: FlowParticle[] = [];
  const connectionSpawnTimers: Record<string, number> = {};

  // ----- Orbit control (manual — no examples/jsm dependency) ----------------
  const spherical = { radius: 7.4, theta: Math.PI * 0.25, phi: Math.PI * 0.42 };
  const AUTO_SPEED = 0.12; // radians / second when idle
  let dragging = false;
  let clickX = 0;
  let clickY = 0;
  let lastX = 0;
  let lastY = 0;
  let selectedAgentKey: string | null = null;
  const target = new THREE.Vector3(0, 0, 0);

  const applyCamera = () => {
    const { radius, theta, phi } = spherical;
    camera.position.set(
      radius * Math.sin(phi) * Math.sin(theta),
      radius * Math.cos(phi),
      radius * Math.sin(phi) * Math.cos(theta),
    );
    camera.lookAt(target);
  };
  applyCamera();

  const onPointerDown = (e: PointerEvent) => {
    dragging = true;
    clickX = e.clientX;
    clickY = e.clientY;
    lastX = e.clientX;
    lastY = e.clientY;
    renderer.domElement.setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: PointerEvent) => {
    if (!dragging) return;
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    lastX = e.clientX;
    lastY = e.clientY;
    spherical.theta -= dx * 0.005;
    spherical.phi = Math.min(Math.PI - 0.25, Math.max(0.25, spherical.phi - dy * 0.005));
  };
  const onPointerUp = (e: PointerEvent) => {
    dragging = false;
    renderer.domElement.releasePointerCapture?.(e.pointerId);
    
    // Detect click vs drag (under 4 pixels is a click)
    const dx = e.clientX - clickX;
    const dy = e.clientY - clickY;
    if (Math.sqrt(dx * dx + dy * dy) < 4) {
      const rect = renderer.domElement.getBoundingClientRect();
      const mouse = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      );
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(mouse, camera);

      const intersects = raycaster.intersectObjects(nodes.map((n) => n.node.coreMesh));
      if (intersects.length > 0) {
        const hitCore = intersects[0].object;
        const matched = nodes.find((n) => n.node.coreMesh === hitCore);
        if (matched) {
          onSelectAgent?.(matched.key);
        }
      } else {
        onSelectAgent?.(null);
      }
    }
  };
  renderer.domElement.addEventListener('pointerdown', onPointerDown);
  renderer.domElement.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);

  // ----- Resize -------------------------------------------------------------
  const resize = () => {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  };
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  window.addEventListener('resize', resize);

  // ----- Live state + render loop ------------------------------------------
  let currentIncident: IncidentWorkflowState | undefined;
  const clock = new THREE.Clock();
  let rafId = 0;
  let disposed = false;

  const renderFrame = () => {
    if (disposed) return;
    // Read delta ONCE; `elapsedTime` is advanced by getDelta(), so read it as a
    // property afterwards (calling getElapsedTime() here too would double-advance
    // the clock and zero the delta).
    const delta = clock.getDelta();
    const elapsed = clock.elapsedTime;

    if (!dragging) spherical.theta += AUTO_SPEED * delta;
    applyCamera();

    // Reflect REAL per-agent status on every node this frame.
    const activeKeys = new Set<string>();
    for (const { key, node } of nodes) {
      const status = STATUS_VISUALS[deriveAgentDisplayStatus(currentIncident, key)];
      node.update(status, elapsed, selectedAgentKey === key);
      if (ACTIVE_FOR_LINKS.has(status.status)) activeKeys.add(key);
    }

    // Spawn data-flow particles along active connections.
    for (const [fromKey, toKey] of AGENT_CONNECTIONS) {
      const status = deriveAgentDisplayStatus(currentIncident, fromKey);
      if (status === 'IDLE' || status === 'QUEUED') continue;

      const connKey = `${fromKey}->${toKey}`;
      let spawnInterval = 0.42;
      if (status === 'COMPLETED' || status === 'WAITING_APPROVAL') {
        spawnInterval = 1.25;
      }

      connectionSpawnTimers[connKey] = (connectionSpawnTimers[connKey] || 0) + delta;
      if (connectionSpawnTimers[connKey] >= spawnInterval) {
        connectionSpawnTimers[connKey] = 0;
        const from = positionByKey[fromKey];
        const to = positionByKey[toKey];
        if (from && to && activeParticles.length < maxFlowParticles) {
          activeParticles.push({
            fromPos: new THREE.Vector3(from[0], from[1], from[2]),
            toPos: new THREE.Vector3(to[0], to[1], to[2]),
            progress: 0,
            speed: 1.0 + Math.random() * 0.4,
          });
        }
      }
    }

    // Update active particles positions
    activeParticles = activeParticles.filter((p) => {
      p.progress += delta * p.speed;
      return p.progress < 1.0;
    });

    const flowPosAttr = flowGeometry.getAttribute('position') as THREE.BufferAttribute;
    for (let i = 0; i < maxFlowParticles; i++) {
      const p = activeParticles[i];
      if (p) {
        const x = THREE.MathUtils.lerp(p.fromPos.x, p.toPos.x, p.progress);
        const y = THREE.MathUtils.lerp(p.fromPos.y, p.toPos.y, p.progress);
        const z = THREE.MathUtils.lerp(p.fromPos.z, p.toPos.z, p.progress);
        flowPosAttr.setXYZ(i, x, y, z);
      } else {
        flowPosAttr.setXYZ(i, 9999, 9999, 9999);
      }
    }
    flowPosAttr.needsUpdate = true;

    // Links brighten when their source node is carrying signal.
    for (const link of links) {
      const active = activeKeys.has(link.fromKey);
      const targetOpacity = active ? 0.5 : 0.12;
      link.material.opacity += (targetOpacity - link.material.opacity) * 0.08;
      link.material.color.lerp(active ? link.activeColor : baseLineColor, 0.08);
    }

    renderer.render(scene, camera);
    rafId = requestAnimationFrame(renderFrame);
  };
  rafId = requestAnimationFrame(renderFrame);

  return {
    setIncident(incident) {
      currentIncident = incident;
    },
    setSelectedAgent(key) {
      selectedAgentKey = key;
    },
    dispose() {
      disposed = true;
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointerup', onPointerUp);
      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);

      for (const { node } of nodes) node.dispose();
      for (const link of links) {
        link.geometry.dispose();
        link.material.dispose();
      }
      grid.geometry.dispose();
      if (Array.isArray(gridMaterial)) gridMaterial.forEach((m) => m.dispose());
      else gridMaterial.dispose();

      flowGeometry.dispose();
      flowMaterial.dispose();

      renderer.dispose();
      renderer.forceContextLoss?.();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    },
  };
}
