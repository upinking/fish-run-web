import { MathUtils, Matrix4, Quaternion, Vector3 } from "three";
import { ROLL_DURATION } from "./run.js";

const PANEL_COUNT = 8;
const HEM_LENGTH = Math.hypot(0.18, 0.19);
const STEP = 1 / 120;
const RECOVERY = 0.18;
const X_AXIS = new Vector3(1, 0, 0);
const BODY_CAPSULES = [
  ["ThighL", "ShinL", 0.096], ["ThighR", "ShinR", 0.096],
  ["Tail", "TailCurl", 0.089], ["TailCurl", "TailCurlTip", 0.105],
];

export function createSkirtMotion(figure) {
  const panels = Array.from({ length: PANEL_COUNT }, (_, index) => {
    const bone = figure.getObjectByName(`SkirtPanel${index}`);
    return bone && {
      bone, rest: bone.quaternion.clone(), angle: 0, velocity: 0,
      frame: new Matrix4(), tangent: new Vector3(),
      limit: index >= 5 && index <= 7 ? 0.15 : 0.20,
      samples: [0.68 * HEM_LENGTH, HEM_LENGTH].map(length => ({
        length, clearance: new Float64Array(BODY_CAPSULES.length),
      })),
    };
  });
  if (panels.some(panel => !panel)) return () => {};

  const waist = panels[0].bone.parent;
  const capsules = BODY_CAPSULES.map(([start, end, radius]) => ({
    start: figure.getObjectByName(start), end: figure.getObjectByName(end),
    radiusSq: radius * radius, point: new Vector3(), axis: new Vector3(), axisSq: 0,
  })).filter(capsule => capsule.start && capsule.end);
  const center = new Vector3();
  const lastCenter = new Vector3();
  const velocity = new Vector3();
  const lastVelocity = new Vector3();
  const impulse = new Vector3();
  const tip = new Vector3();
  const offset = new Vector3();
  const rotation = new Quaternion();
  let lastElapsed = -1;
  let recovery = RECOVERY;

  function distanceSq(point, capsule) {
    offset.subVectors(point, capsule.point);
    const along = MathUtils.clamp(offset.dot(capsule.axis) / capsule.axisSq, 0, 1);
    return offset.addScaledVector(capsule.axis, -along).lengthSq();
  }

  function limitContact(panel, angle) {
    if (Math.abs(angle) < 1e-5) return angle;
    for (const sample of panel.samples) {
      tip.set(0, sample.length, 0).applyMatrix4(panel.frame);
      capsules.forEach((capsule, index) => {
        // A baked fold can already touch the body. Only limit added penetration.
        sample.clearance[index] = Math.min(capsule.radiusSq, distanceSq(tip, capsule));
      });
    }
    const clear = (bend) => panel.samples.every(({ length, clearance }) => {
      tip.set(0, length * Math.cos(bend), length * Math.sin(bend)).applyMatrix4(panel.frame);
      return capsules.every((capsule, index) => distanceSq(tip, capsule) + 0.00005 >= clearance[index]);
    });
    if (clear(angle)) return angle;
    let low = 0;
    let high = 1;
    for (let i = 0; i < 5; i++) {
      const fraction = (low + high) / 2;
      if (clear(angle * fraction)) low = fraction;
      else high = fraction;
    }
    return angle * low;
  }

  return function updateSkirt(run) {
    if (run.phase === "ready" || run.elapsed < lastElapsed) {
      lastElapsed = -1;
      recovery = RECOVERY;
      lastVelocity.set(0, 0, 0);
      for (const panel of panels) {
        panel.angle = panel.velocity = 0;
        panel.bone.quaternion.copy(panel.rest);
      }
      return;
    }
    if (run.phase !== "running") return;

    waist.getWorldPosition(center);
    const elapsed = lastElapsed < 0 ? 0 : run.elapsed - lastElapsed;
    if (elapsed > 0) {
      velocity.subVectors(center, lastCenter).multiplyScalar(1 / elapsed);
      impulse.subVectors(lastVelocity, velocity);
      lastVelocity.copy(velocity);
    }
    if (elapsed > 0 || lastElapsed < 0) lastCenter.copy(center);
    lastElapsed = run.elapsed;

    const rolling = run.rollRemaining > 0;
    recovery = rolling ? 0 : Math.min(RECOVERY, recovery + elapsed);
    const weight = rolling
      ? 1 - MathUtils.smoothstep(ROLL_DURATION - run.rollRemaining, 0, 0.08)
      : MathUtils.smoothstep(recovery, 0, RECOVERY);

    if (weight === 0) {
      for (const panel of panels) {
        panel.angle = panel.velocity = 0;
        panel.bone.quaternion.copy(panel.rest);
      }
      return;
    }

    for (const panel of panels) {
      panel.frame.compose(panel.bone.position, panel.rest, panel.bone.scale).premultiply(waist.matrixWorld);
      panel.tangent.set(0, 0, 1).transformDirection(panel.frame);
      if (!rolling && elapsed > 0) {
        // A sudden change in waist velocity leaves the hem moving in its old direction.
        const kick = MathUtils.clamp(impulse.dot(panel.tangent) * 0.39, -3.2, 3.2);
        panel.velocity += kick * weight;
      }
    }
    const steps = rolling ? 0 : Math.min(6, Math.round(elapsed / STEP));
    for (let step = 0; step < steps; step++) {
      panels.forEach((panel, index) => {
        const neighbour = panels[(index + 7) % PANEL_COUNT].angle + panels[(index + 1) % PANEL_COUNT].angle;
        const air = 0.085 * run.speed ** 2 * Math.max(0, panel.tangent.z);
        panel.velocity += (air - 115 * panel.angle - 13 * panel.velocity + 18 * (neighbour - 2 * panel.angle)) * STEP;
      });
      for (const panel of panels) {
        const angle = panel.angle + panel.velocity * STEP;
        panel.angle = MathUtils.clamp(angle, -0.038, panel.limit);
        if (angle !== panel.angle) panel.velocity = 0;
      }
    }

    for (const capsule of capsules) {
      capsule.start.getWorldPosition(capsule.point);
      capsule.end.getWorldPosition(capsule.axis).sub(capsule.point);
      capsule.axisSq = capsule.axis.lengthSq();
    }
    for (const panel of panels) {
      const angle = panel.angle * weight;
      const bend = limitContact(panel, angle);
      if (!rolling && bend !== angle) {
        panel.angle = bend / weight;
        panel.velocity = 0;
      }
      panel.bone.quaternion.copy(panel.rest).multiply(rotation.setFromAxisAngle(X_AXIS, bend));
    }
  };
}
