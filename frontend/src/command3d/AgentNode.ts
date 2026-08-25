// ---------------------------------------------------------------------------
// Command Center 3D — reusable AgentNode (Phase 3).
//
// A single agent rendered as a 3D object: an icosahedron core whose color and
// emissive glow reflect the agent's live status, wrapped by an identity ring in
// the agent's accent color. Pure three.js (no React), so it can be reused by any
// scene. The `update` method is called every frame with the CURRENT status
// visual (derived from real backend events) and the elapsed clock — the only
// animation is a glow/scale pulse for genuinely live states (WORKING /
// WAITING_APPROVAL). Nothing here advances the workflow; it only reflects it.
// ---------------------------------------------------------------------------

import * as THREE from 'three';
import type { StatusVisual } from './agentStatus';

export interface AgentNodeHandle {
  /** The group to add to the scene (already positioned). */
  group: THREE.Group;
  /** The core mesh for raycasting click selection. */
  coreMesh: THREE.Mesh;
  /** Reflect the latest status visual; `elapsed` is seconds from the clock. */
  update: (visual: StatusVisual, elapsed: number, selected: boolean) => void;
  /** Release GPU resources. */
  dispose: () => void;
}

export function createAgentNode(
  accent: string,
  position: readonly [number, number, number],
): AgentNodeHandle {
  const group = new THREE.Group();
  group.position.set(position[0], position[1], position[2]);

  // Core — colored by live status.
  const coreGeometry = new THREE.IcosahedronGeometry(0.62, 1);
  const coreMaterial = new THREE.MeshStandardMaterial({
    color: new THREE.Color('#64748b'),
    emissive: new THREE.Color('#64748b'),
    emissiveIntensity: 0.05,
    metalness: 0.35,
    roughness: 0.4,
    flatShading: true,
  });
  const core = new THREE.Mesh(coreGeometry, coreMaterial);
  group.add(core);

  // Selection outline ring/globe (only visible/pulsing when selected).
  const selectGeometry = new THREE.IcosahedronGeometry(0.78, 1);
  const selectMaterial = new THREE.MeshBasicMaterial({
    color: new THREE.Color(accent),
    wireframe: true,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const selectMesh = new THREE.Mesh(selectGeometry, selectMaterial);
  group.add(selectMesh);

  // Identity ring 1 — constant accent color, opacity breathes with activity.
  const ringGeometry = new THREE.TorusGeometry(0.98, 0.022, 10, 64);
  const ringMaterial = new THREE.MeshBasicMaterial({
    color: new THREE.Color(accent),
    transparent: true,
    opacity: 0.22,
  });
  const ring = new THREE.Mesh(ringGeometry, ringMaterial);
  ring.rotation.x = Math.PI / 2;
  group.add(ring);

  // Identity ring 2 — gyroscope companion rotating on different axis.
  const ring2Geometry = new THREE.TorusGeometry(1.12, 0.016, 8, 64);
  const ring2Material = new THREE.MeshBasicMaterial({
    color: new THREE.Color(accent),
    transparent: true,
    opacity: 0.14,
  });
  const ring2 = new THREE.Mesh(ring2Geometry, ring2Material);
  ring2.rotation.y = Math.PI / 2;
  group.add(ring2);

  // Subtle floating particle cloud around the node.
  const particleCount = 30;
  const pGeometry = new THREE.BufferGeometry();
  const pPositions = new Float32Array(particleCount * 3);
  const pRadius: number[] = [];
  const pAngles: number[] = [];
  const pSpeeds: number[] = [];
  const pYOffsets: number[] = [];
  
  for (let i = 0; i < particleCount; i++) {
    pRadius.push(0.7 + Math.random() * 0.4);
    pAngles.push(Math.random() * Math.PI * 2);
    pSpeeds.push((0.3 + Math.random() * 1.2) * (Math.random() > 0.5 ? 1 : -1));
    pYOffsets.push((Math.random() - 0.5) * 0.5);
    
    pPositions[i * 3] = pRadius[i] * Math.cos(pAngles[i]);
    pPositions[i * 3 + 1] = pYOffsets[i];
    pPositions[i * 3 + 2] = pRadius[i] * Math.sin(pAngles[i]);
  }
  
  pGeometry.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
  const pMaterial = new THREE.PointsMaterial({
    color: new THREE.Color(accent),
    size: 0.055,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const particles = new THREE.Points(pGeometry, pMaterial);
  group.add(particles);

  const statusColor = new THREE.Color();

  return {
    group,
    coreMesh: core,
    update(visual: StatusVisual, elapsed: number, selected: boolean) {
      statusColor.set(visual.color);
      coreMaterial.color.copy(statusColor);
      coreMaterial.emissive.copy(statusColor);

      const wave = visual.pulse ? Math.sin(elapsed * 3.4) * 0.5 + 0.5 : 0;
      coreMaterial.emissiveIntensity = visual.glow + wave * 0.6;
      core.scale.setScalar(1 + wave * 0.14);
      core.rotation.y = elapsed * 0.35;
      core.rotation.x = Math.sin(elapsed * 0.4) * 0.15;

      // Identity rings animation
      ringMaterial.opacity = 0.18 + (visual.pulse ? wave * 0.4 : 0.06);
      ring.rotation.z += 0.004;

      ring2Material.opacity = 0.1 + (visual.pulse ? wave * 0.25 : 0.02);
      ring2.rotation.x += 0.006;
      ring2.rotation.y += 0.003;

      // Particles animation
      const targetPOpacity = visual.pulse ? 0.65 : 0.0;
      pMaterial.opacity += (targetPOpacity - pMaterial.opacity) * 0.05;
      if (pMaterial.opacity > 0.01) {
        const posAttr = pGeometry.getAttribute('position') as THREE.BufferAttribute;
        for (let i = 0; i < particleCount; i++) {
          pAngles[i] += elapsed * 0.0005 * pSpeeds[i];
          const x = pRadius[i] * Math.cos(pAngles[i]);
          const z = pRadius[i] * Math.sin(pAngles[i]);
          posAttr.setX(i, x);
          posAttr.setZ(i, z);
        }
        posAttr.needsUpdate = true;
      }

      // Selection outline animation
      if (selected) {
        selectMaterial.opacity += (0.35 - selectMaterial.opacity) * 0.1;
        selectMesh.rotation.y = -elapsed * 0.5;
        selectMesh.rotation.z = elapsed * 0.3;
        selectMesh.scale.setScalar(1.0 + Math.sin(elapsed * 4.0) * 0.04);
      } else {
        selectMaterial.opacity += (0.0 - selectMaterial.opacity) * 0.2;
      }
    },
    dispose() {
      coreGeometry.dispose();
      coreMaterial.dispose();
      ringGeometry.dispose();
      ringMaterial.dispose();
      ring2Geometry.dispose();
      ring2Material.dispose();
      selectGeometry.dispose();
      selectMaterial.dispose();
      pGeometry.dispose();
      pMaterial.dispose();
    },
  };
}
