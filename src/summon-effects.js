import * as THREE from "three";
import { SUMMON_DURATION } from "./run.js";

const BURST_DURATION = 0.62;
const SURFACE_VERTEX = `
  varying vec2 point;

  void main() {
    point = 2.0 * uv - 1.0;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

function effectMaterial(vertexShader, fragmentShader) {
  return new THREE.ShaderMaterial({
    vertexShader, fragmentShader,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    toneMapped: false,
    uniforms: { age: { value: 0 }, strength: { value: 0 } },
  });
}

function disc(size, fragmentShader) {
  const material = effectMaterial(SURFACE_VERTEX, fragmentShader);
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(size, size), material);
  mesh.rotation.x = -Math.PI / 2;
  mesh.visible = false;
  return mesh;
}

function ignitionRing() {
  return disc(8.4, `
    varying vec2 point;
    uniform float age;
    uniform float strength;

    void main() {
      float radius = mix(0.10, 0.94, 1.0 - pow(1.0 - age, 1.35));
      float distanceToEdge = abs(length(point) - radius);
      float rim = 1.0 - smoothstep(0.006, 0.017, distanceToEdge);
      float bloom = (1.0 - smoothstep(0.0, 0.063, distanceToEdge)) * 0.38;
      float echo = (1.0 - smoothstep(0.008, 0.025, abs(length(point) - radius * 0.73))) * 0.36;
      vec3 blue = vec3(0.01, 0.23, 0.83);
      vec3 core = vec3(0.41, 0.93, 1.0);
      gl_FragColor = vec4(mix(blue, core, rim), max(max(rim, bloom), echo) * strength);
      #include <colorspace_fragment>
    }
  `);
}

function flightHalo() {
  return disc(2.3, `
    varying vec2 point;
    uniform float age;
    uniform float strength;

    void main() {
      float radius = length(point);
      float rim = 1.0 - smoothstep(0.014, 0.043, abs(radius - 0.65));
      float angle = atan(point.y, point.x);
      float arcs = smoothstep(0.14, 0.29, abs(sin(3.0 * angle + 1.8 * age)));
      float ticks = (1.0 - smoothstep(0.008, 0.039, abs(radius - 0.75))) * arcs;
      float fill = (1.0 - smoothstep(0.2, 0.67, radius)) * 0.27;
      vec3 color = mix(vec3(0.012, 0.25, 0.83), vec3(0.29, 0.91, 1.0), rim);
      gl_FragColor = vec4(color, max(max(rim * 0.78, ticks * 0.56), fill) * strength);
      #include <colorspace_fragment>
    }
  `);
}

function wakeGeometry() {
  const stripSteps = 16;
  const strands = [
    [0.36, 0.13, 3.45],
    [0.48, 0.057, 3.96],
    [0.60, 0.035, 4.30],
  ];
  const positions = [];
  const tracks = [];
  const indices = [];
  for (const sign of [-1, 1]) {
    for (const [offset, width, length] of strands) {
      const first = positions.length / 3;
      for (let step = 0; step <= stripSteps; step++) {
        const along = step / stripSteps;
        for (const edge of [-1, 1]) {
          positions.push(edge, along, 0);
          tracks.push(sign, offset, width, length);
        }
        if (step > 0) {
          const index = first + 2 * step;
          indices.push(index - 2, index - 1, index, index, index - 1, index + 1);
        }
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("track", new THREE.Float32BufferAttribute(tracks, 4));
  geometry.setIndex(indices);
  return geometry;
}

function flightWake() {
  const material = effectMaterial(`
    attribute vec4 track;
    uniform float age;
    varying float edge;
    varying float along;
    varying float seed;
    varying float ribbon;

    void main() {
      edge = position.x;
      along = position.y;
      seed = track.y + track.x * 0.16;
      ribbon = step(0.10, track.z);
      float flutter = sin(along * 6.4 - age * 6.0 + seed * 8.0) * along;
      float width = track.z * (1.0 - 0.78 * along);
      vec3 point = vec3(
        track.x * (track.y + 0.52 * along + 0.075 * flutter) + edge * width,
        0.08 - 0.38 * along + 0.09 * flutter + 0.035 * edge,
        0.12 + track.w * along
      );
      gl_Position = projectionMatrix * modelViewMatrix * vec4(point, 1.0);
    }
  `, `
    uniform float age;
    uniform float strength;
    varying float edge;
    varying float along;
    varying float seed;
    varying float ribbon;

    void main() {
      float shape = 1.0 - smoothstep(0.18, 1.0, abs(edge));
      float taper = smoothstep(0.0, 0.065, along) * (1.0 - smoothstep(0.50, 1.0, along));
      float flow = fract(along * 3.4 - age * 2.5 + seed * 5.0);
      float sparks = smoothstep(0.07, 0.22, flow) * (1.0 - smoothstep(0.57, 0.86, flow));
      float intensity = mix(sparks, 0.63 + 0.37 * sparks, ribbon);
      vec3 blue = vec3(0.012, 0.25, 0.95);
      vec3 cyan = vec3(0.19, 0.82, 1.0);
      vec3 color = mix(blue, cyan, shape);
      color = mix(color, vec3(0.66, 0.94, 1.0), shape * shape * sparks * 0.74);
      gl_FragColor = vec4(color, shape * taper * intensity * strength);
      #include <colorspace_fragment>
    }
  `);
  const mesh = new THREE.Mesh(wakeGeometry(), material);
  // Positions are expanded by the vertex shader rather than the geometry bounds.
  mesh.frustumCulled = false;
  mesh.visible = false;
  return mesh;
}

export function createSummonEffects(scene) {
  const burst = ignitionRing();
  const halo = flightHalo();
  const wake = flightWake();
  const reducedMotion = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)");
  scene.add(burst, halo, wake);

  return function update(run) {
    const remaining = run.summonRemaining;
    if (remaining <= 0) {
      burst.visible = halo.visible = wake.visible = false;
      return;
    }

    const age = SUMMON_DURATION - remaining;
    const reduced = reducedMotion?.matches;
    const fade = THREE.MathUtils.smoothstep(remaining, 0, 0.48);
    burst.visible = !reduced && age < BURST_DURATION;
    if (burst.visible) {
      const progress = age / BURST_DURATION;
      burst.position.set(run.x, 0.118, 0);
      burst.material.uniforms.age.value = progress;
      burst.material.uniforms.strength.value = (1 - progress) ** 1.35;
    }

    halo.visible = true;
    halo.position.set(run.x, Math.max(0.125, run.y - 0.04), 0);
    halo.material.uniforms.age.value = reduced ? 0 : age;
    halo.material.uniforms.strength.value = fade * (reduced ? 0.44 : 0.86);

    wake.visible = !reduced && age > 0.045;
    if (wake.visible) {
      wake.position.set(run.x, run.y, 0);
      wake.material.uniforms.age.value = age;
      wake.material.uniforms.strength.value = fade * THREE.MathUtils.smoothstep(age, 0.045, 0.23);
    }
  };
}
