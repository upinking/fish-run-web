import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { LANE_WIDTH, ROLL_DURATION, SUMMON_DURATION } from "./run.js";
import { createSkirtMotion } from "./skirt.js";
import { createSummonEffects } from "./summon-effects.js";

const TILE_LENGTH = 40;
const PORTAL_SPACING = 80;
const ZONE_LENGTH = 320;
const RUNNER_ASSET = "runner-hunyuan";
export const ASSET_NAMES = ["track", "portal", "deepsea-track", "deepsea-portal", "train", "jump", "slide", RUNNER_ASSET];

function isUnderwater(distance) {
  return Math.floor(distance / ZONE_LENGTH) % 2 === 1;
}

export function zoneName(distance) {
  return isUnderwater(distance) ? "深海算力舱" : "海滨算力站";
}

function loadAssets() {
  const loader = new GLTFLoader();
  const base = import.meta.env.BASE_URL;
  const embeddedModels = document.getElementById("offline-models");
  const models = embeddedModels && JSON.parse(embeddedModels.textContent);
  return Promise.all(ASSET_NAMES.map(async (name) => {
    if (models) {
      const binary = atob(models[name]);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      return [name, await loader.parseAsync(bytes.buffer, "")];
    }
    const asset = await loader.loadAsync(`${base}models/${name}.glb`);
    return [name, asset];
  })).then(Object.fromEntries);
}

function sky() {
  const material = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    uniforms: {
      horizon: { value: new THREE.Color("#d3f4ff") },
      zenith: { value: new THREE.Color("#429cd9") },
      immersion: { value: 0 },
      time: { value: 0 },
    },
    vertexShader: `
      varying vec3 direction;
      void main() {
        direction = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 horizon;
      uniform vec3 zenith;
      uniform float immersion;
      uniform float time;
      varying vec3 direction;
      void main() {
        vec3 ray = normalize(direction);
        vec3 base = mix(horizon, zenith, smoothstep(-0.04, 0.65, ray.y));
        float glare = pow(max(0.0, dot(ray, normalize(vec3(-0.55, 0.38, -0.7)))), 14.0);
        vec3 color = mix(base, vec3(1.0, 0.98, 0.91), glare * 0.38);
        if (immersion > 0.0) {
          float surface = smoothstep(0.08, 0.74, ray.y);
          vec2 p = ray.xz * (12.0 / max(ray.y, 0.16));
          float wave = sin(p.x + 1.2 * sin(p.y * 0.75 + time * 0.8) - time * 0.6);
          float ripple = smoothstep(0.85, 1.0, wave) * surface;
          vec3 water = mix(vec3(0.016, 0.11, 0.21), vec3(0.025, 0.48, 0.63), surface);
          color = mix(color, water + vec3(0.12, 0.24, 0.26) * ripple, immersion);
        }
        gl_FragColor = vec4(color, 1.0);
        #include <colorspace_fragment>
      }
    `,
  });
  const dome = new THREE.Mesh(new THREE.SphereGeometry(205, 28, 16), material);
  dome.renderOrder = -10;
  return dome;
}

function ocean() {
  const material = new THREE.ShaderMaterial({
    uniforms: {
      time: { value: 0 },
      aqua: { value: new THREE.Color("#22cdd4") },
      deep: { value: new THREE.Color("#158cc0") },
      haze: { value: new THREE.Color("#c6edfb") },
    },
    vertexShader: `
      varying vec3 point;
      void main() {
        point = (modelMatrix * vec4(position, 1.0)).xyz;
        gl_Position = projectionMatrix * viewMatrix * vec4(point, 1.0);
      }
    `,
    fragmentShader: `
      uniform float time;
      uniform vec3 aqua;
      uniform vec3 deep;
      uniform vec3 haze;
      varying vec3 point;
      void main() {
        vec2 p = point.xz;
        float wave = sin(p.y * 2.1 + sin(p.x * 0.53) * 1.4 - time * 1.7);
        float second = sin(p.y * 0.71 - p.x * 0.76 + time * 1.08);
        float glint = smoothstep(0.69, 0.98, 0.67 * wave + 0.33 * second);
        float dist = distance(point, cameraPosition);
        vec3 base = mix(aqua, deep, smoothstep(7.0, 73.0, dist));
        base = mix(base, vec3(0.76, 0.97, 1.0), glint * 0.34);
        gl_FragColor = vec4(mix(base, haze, smoothstep(48.0, 172.0, dist)), 1.0);
        #include <colorspace_fragment>
      }
    `,
  });
  const surface = new THREE.Mesh(new THREE.PlaneGeometry(440, 440), material);
  surface.rotation.x = -Math.PI / 2;
  surface.position.set(0, -0.33, -110);
  return surface;
}

function coast(scene) {
  const hillGeometry = new THREE.IcosahedronGeometry(1, 2);
  const greens = ["#749b76", "#80a883", "#629077"].map((color) =>
    new THREE.MeshStandardMaterial({ color, flatShading: true, roughness: 1 }));
  const islands = [
    [-38, -61, 13, 3.8], [-46, -73, 16, 5.1], [-56, -83, 17, 5.7],
    [42, -98, 14, 3.7], [55, -109, 19, 5.6], [67, -112, 16, 4.3],
  ];
  for (const [index, [x, z, width, height]] of islands.entries()) {
    const hill = new THREE.Mesh(hillGeometry, greens[index % greens.length]);
    hill.position.set(x, -0.65, z);
    hill.scale.set(width, height, width * 0.58);
    scene.add(hill);
  }
  const cloudGeometry = new THREE.SphereGeometry(1, 12, 8);
  const cloudMaterial = new THREE.MeshBasicMaterial({ color: "#f3fbff" });
  for (const [x, y, z, scale] of [[-39, 12, -76, 1.35], [37, 13, -86, 1.5], [-14, 11, -112, 1], [16, 15, -130, 1.3]]) {
    const cloud = new THREE.Group();
    cloud.position.set(x, y, z);
    cloud.scale.setScalar(scale);
    for (const [offset, height, sx, sy] of [[-4.5, -0.2, 3, 1.3], [-1.9, 1.0, 2.8, 2.8], [1.1, 0.6, 3.4, 2.3], [4.2, -0.3, 2.6, 1.3]]) {
      const puff = new THREE.Mesh(cloudGeometry, cloudMaterial);
      puff.position.set(offset, height, 0);
      puff.scale.set(sx, sy, 1.3);
      cloud.add(puff);
    }
    scene.add(cloud);
  }
}

function riceModel() {
  const rice = new THREE.Group();
  const shape = new THREE.Shape();
  shape.moveTo(-0.22, 0.05);
  shape.quadraticCurveTo(-0.26, 0.09, -0.21, 0.18);
  shape.lineTo(-0.07, 0.42);
  shape.quadraticCurveTo(0, 0.51, 0.07, 0.42);
  shape.lineTo(0.21, 0.18);
  shape.quadraticCurveTo(0.26, 0.09, 0.22, 0.05);
  shape.quadraticCurveTo(0, 0.018, -0.22, 0.05);
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: 0.18, bevelEnabled: true, bevelThickness: 0.055,
    bevelSize: 0.045, bevelSegments: 2, curveSegments: 5,
  });
  geometry.translate(0, 0, -0.09);
  rice.add(new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
    color: "#fff5d8", roughness: 0.58,
  })));
  const nori = new THREE.Mesh(
    new THREE.BoxGeometry(0.135, 0.16, 0.012),
    new THREE.MeshStandardMaterial({ color: "#244238", roughness: 0.9 }),
  );
  nori.position.set(0, 0.10, 0.147);
  rice.add(nori);
  return rice;
}

function shadows(group, { cast = false, receive = true } = {}) {
  group.traverse((node) => {
    if (!node.isMesh) return;
    node.castShadow = cast;
    node.receiveShadow = receive;
  });
  return group;
}

export async function createScene(mount) {
  const assets = await loadAssets();
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog("#c6edfb", 37, 155);
  const camera = new THREE.PerspectiveCamera(49, 1, 0.15, 420);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.65));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.16;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  mount.append(renderer.domElement);

  const dome = sky();
  scene.add(dome);
  const water = ocean();
  const shore = new THREE.Group();
  shore.add(water);
  coast(shore);
  scene.add(shore);
  const hemisphere = new THREE.HemisphereLight("#dff7ff", "#8194a7", 1.75);
  scene.add(hemisphere);
  const sun = new THREE.DirectionalLight("#fff2d7", 2.5);
  sun.position.set(-10, 17, 7);
  sun.target.position.set(0, 0, -9);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -14, right: 14, top: 14, bottom: -14, near: 0.5, far: 50 });
  sun.shadow.bias = -0.00032;
  sun.shadow.normalBias = 0.025;
  scene.add(sun, sun.target);
  const coastFog = scene.fog.color.clone();
  const deepFog = new THREE.Color("#367c9f");
  const coastLight = hemisphere.color.clone();
  const deepLight = new THREE.Color("#beeaff");

  const tiles = Array.from({ length: 6 }, () => {
    const tile = new THREE.Group();
    const deck = shadows(assets.track.scene.clone());
    const tunnel = shadows(assets["deepsea-track"].scene.clone());
    tile.add(deck, tunnel);
    scene.add(tile);
    return { tile, deck, tunnel };
  });
  const portals = Array.from({ length: 3 }, () => assets.portal.scene.clone());
  const airlock = assets["deepsea-portal"].scene;
  scene.add(...portals, airlock);
  const model = assets[RUNNER_ASSET];
  const figure = shadows(model.scene, { cast: true });
  const updateSkirt = createSkirtMotion(figure);
  const runner = new THREE.Group();
  runner.add(figure);
  scene.add(runner);
  const updateSummonEffects = createSummonEffects(scene);
  const mixer = new THREE.AnimationMixer(figure);
  const clips = new Map(model.animations.map((clip) => [clip.name.toLowerCase(), mixer.clipAction(clip)]));
  const rollAction = clips.get("roll");
  rollAction?.setEffectiveTimeScale(0);
  const boostAction = clips.get("boost");
  boostAction?.setEffectiveTimeScale(0);
  let pose = null;
  let action = null;
  const rice = riceModel();
  const itemViews = new Map();
  const cameraTarget = new THREE.Vector3();
  let cameraX = 0;
  let sceneTime = 0;

  function resize() {
    const width = mount.clientWidth;
    const height = mount.clientHeight;
    if (width < 1 || height < 1) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
  }
  const observer = new ResizeObserver(resize);
  observer.observe(mount);
  resize();

  function syncItems(run) {
    const active = new Set();
    for (const item of run.items) {
      const depth = run.distance - item.distance;
      if (item.taken || depth < -128 || depth > 8) continue;
      active.add(item.id);
      let view = itemViews.get(item.id);
      if (!view) {
        view = item.kind === "rice" ? rice.clone() : shadows(assets[item.kind].scene.clone(), { cast: true });
        itemViews.set(item.id, view);
        scene.add(view);
      }
      const y = item.kind === "rice" ? 0.095 + Math.sin(sceneTime * 3.8 + item.id) * 0.055 : 0;
      view.position.set(item.lane * LANE_WIDTH, y, depth);
    }
    for (const [id, view] of itemViews) {
      if (!active.has(id)) {
        scene.remove(view);
        itemViews.delete(id);
      }
    }
  }

  function setPose(run, dt) {
    const current = run.summonRemaining > 0 && boostAction ? "boost" :
      run.rollRemaining > 0 ? "roll" : run.y > 0.08 ? "jump" : "run";
    if (pose !== current) {
      const next = clips.get(current) ?? clips.get("run");
      if (next !== action) {
        next?.reset().play();
        if (action && next) next.crossFadeFrom(action, current === "roll" ? 0.08 : 0.11, false);
        else action?.stop();
        action = next;
      }
      pose = current;
    }
    if (current === "roll" && rollAction) {
      const progress = 1 - run.rollRemaining / ROLL_DURATION;
      rollAction.time = progress * rollAction.getClip().duration;
    }
    if (current === "boost") {
      const progress = 1 - run.summonRemaining / SUMMON_DURATION;
      boostAction.time = progress * boostAction.getClip().duration;
    }
    if (run.phase === "running" || run.phase === "ready") {
      mixer.update(dt * (run.phase === "ready" ? 0.48 : 1));
    }
    runner.position.set(run.x, run.y, 0);
    updateSkirt(run);
  }

  function render(run, dt) {
    if (run.phase !== "paused" && run.phase !== "over") sceneTime += dt;
    water.material.uniforms.time.value = sceneTime;
    const cycle = run.distance % (2 * ZONE_LENGTH);
    const immersion = THREE.MathUtils.smoothstep(cycle, ZONE_LENGTH, ZONE_LENGTH + 18) *
      (1 - THREE.MathUtils.smoothstep(cycle, 2 * ZONE_LENGTH - 19, 2 * ZONE_LENGTH));
    dome.material.uniforms.immersion.value = immersion;
    dome.material.uniforms.time.value = sceneTime;
    shore.visible = immersion < 0.99;
    scene.fog.color.lerpColors(coastFog, deepFog, immersion);
    scene.fog.near = THREE.MathUtils.lerp(37, 23, immersion);
    scene.fog.far = THREE.MathUtils.lerp(155, 115, immersion);
    hemisphere.color.lerpColors(coastLight, deepLight, immersion);
    sun.intensity = THREE.MathUtils.lerp(2.5, 1.7, immersion);

    const tileIndex = Math.floor((run.distance + 14) / TILE_LENGTH);
    tiles.forEach(({ tile, deck, tunnel }, index) => {
      const start = (tileIndex + index - 2) * TILE_LENGTH;
      const underwater = isUnderwater(start);
      tile.position.z = run.distance - start;
      deck.visible = !underwater;
      tunnel.visible = underwater;
    });
    const portalIndex = Math.max(0, Math.floor((run.distance - 50) / PORTAL_SPACING));
    portals.forEach((portal, index) => {
      const distance = 41 + (portalIndex + index) * PORTAL_SPACING;
      portal.position.z = run.distance - distance;
      portal.visible = !isUnderwater(distance);
    });
    const boundary = Math.max(1, Math.floor((run.distance - 14) / ZONE_LENGTH) + 1);
    airlock.position.z = run.distance - boundary * ZONE_LENGTH;
    airlock.visible = airlock.position.z > -155;
    airlock.rotation.y = boundary % 2 === 0 ? Math.PI : 0;
    syncItems(run);
    setPose(run, dt);
    updateSummonEffects(run);

    // Track motion is forward on one axis. Lateral follow keeps the camera behind the runner.
    const narrow = camera.aspect < 1.2;
    const follow = narrow ? 0.72 : 0.29;
    cameraX = THREE.MathUtils.damp(cameraX, run.x * follow, 8, dt);
    camera.position.set(cameraX, 3.17 + run.y * 0.16, narrow ? 7.5 : 6.02);
    cameraTarget.set(cameraX * 0.55, 0.72 + run.y * 0.10, -8.5);
    camera.lookAt(cameraTarget);
    renderer.render(scene, camera);
  }

  return { render };
}
