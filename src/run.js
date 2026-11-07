// The simulation measures meters traveled. The renderer maps forward to -Z.
export const LANE_WIDTH = 2.35;
export const ROLL_DURATION = 0.82;
export const SUMMON_DURATION = 5;

const STEP = 1 / 120;
const SECTION_LENGTH = 342;
const START_SPEED = 9.6;
const MAX_SPEED = 17;
const LANE_SPEED = 15;
const JUMP_SPEED = 7.2;
const GRAVITY = 17;
const SHIELD_GRACE = 0.45;
const RICE_RADIUS = 0.8;

// Each row gives a distance, rice trail lane, then one or two hazards.
// The first three rows teach a train, a low barrier, and a high gate in turn.
const ROWS = [
  [30, 1, [0, "train"]],
  [62, 1, [1, "jump"]],
  [95, 1, [1, "slide"]],
  [130, 0, [-1, "train"], [1, "train"]],
  [164, 0, [0, "jump"], [-1, "slide"]],
  [199, 1, [0, "train"], [-1, "jump"]],
  [234, -1, [0, "slide"], [1, "train"]],
  [270, -1, [-1, "jump"], [1, "slide"]],
  [304, 0, [-1, "train"], [1, "train"]],
  [339, 1, [0, "slide"], [-1, "train"]],
];

const HIT_DEPTH = { train: 2.85, jump: 0.58, slide: 0.52 };
const RICE_BEFORE = [-13, -10, -7, -4];
const RICE_AFTER = [4, 7, 10];

function appendItem(run, kind, lane, distance) {
  run.items.push({ id: run.nextItemId++, kind, lane, distance, taken: false });
}

function appendSection(run) {
  const offset = run.nextSection;
  for (const [at, trail, ...hazards] of ROWS) {
    const distance = offset + at;
    for (const before of RICE_BEFORE) appendItem(run, "rice", trail, distance + before);
    for (const [lane, kind] of hazards) appendItem(run, kind, lane, distance);
    for (const after of RICE_AFTER) appendItem(run, "rice", trail, distance + after);
  }
  run.nextSection += SECTION_LENGTH;
}

export function createRun() {
  const run = {
    phase: "ready",
    distance: 0,
    elapsed: 0,
    x: 0,
    y: 0,
    lane: 0,
    speed: START_SPEED,
    rice: 0,
    shield: 1,
    energy: 0,
    summonRemaining: 0,
    failure: null,
    lastHit: null,
    hitFlash: 0,
    items: [],
    nextItemId: 1,
    nextSection: 0,
    accumulatedTime: 0,
    verticalSpeed: 0,
    rollRemaining: 0,
    rollQueued: false,
    graceRemaining: 0,
  };
  for (const distance of [7, 10, 13]) appendItem(run, "rice", 0, distance);
  appendSection(run);
  return run;
}

export function restartRun(run) {
  Object.assign(run, createRun());
  run.phase = "running";
  return run;
}

export function command(run, action) {
  if (action === "pause" && run.phase === "running") {
    run.phase = "paused";
    run.accumulatedTime = 0;
    return true;
  }
  if (action === "resume" && run.phase === "paused") {
    run.phase = "running";
    return true;
  }
  if (run.phase !== "running") return false;

  switch (action) {
    case "left":
    case "right": {
      const lane = Math.max(-1, Math.min(1, run.lane + (action === "left" ? -1 : 1)));
      const moved = lane !== run.lane;
      run.lane = lane;
      return moved;
    }
    case "jump":
      if (run.y > 0 || run.verticalSpeed > 0 || run.summonRemaining > 0) return false;
      run.verticalSpeed = JUMP_SPEED;
      run.rollRemaining = 0;
      run.rollQueued = false;
      return true;
    case "roll":
      if (run.summonRemaining > 0 || run.rollRemaining > 0) return false;
      if (run.y > 0) {
        run.rollQueued = true;
        run.verticalSpeed = Math.min(run.verticalSpeed, -8);
      } else {
        run.verticalSpeed = 0;
        run.rollQueued = false;
        run.rollRemaining = ROLL_DURATION;
      }
      return true;
    case "summon":
      if (run.energy < 100 || run.summonRemaining > 0) return false;
      run.energy = 0;
      run.summonRemaining = SUMMON_DURATION;
      run.rollRemaining = 0;
      run.rollQueued = false;
      return true;
    default:
      return false;
  }
}

function updateMovement(run, dt) {
  const remaining = run.lane * LANE_WIDTH - run.x;
  run.x += Math.sign(remaining) * Math.min(Math.abs(remaining), LANE_SPEED * dt);

  run.rollRemaining = Math.max(0, run.rollRemaining - dt);
  if (run.summonRemaining > 0) {
    run.y += Math.min(2.35 - run.y, 6 * dt);
    run.verticalSpeed = 0;
  } else if (run.y > 0 || run.verticalSpeed > 0) {
    run.verticalSpeed -= GRAVITY * dt;
    run.y += run.verticalSpeed * dt;
    if (run.y <= 0) {
      run.y = 0;
      run.verticalSpeed = 0;
      if (run.rollQueued) run.rollRemaining = ROLL_DURATION;
      run.rollQueued = false;
    }
  }
}

function collectRice(run, item) {
  item.taken = true;
  run.rice++;
  if (run.summonRemaining === 0 && run.graceRemaining === 0) {
    run.energy = Math.min(100, run.energy + 10);
  }
  if (run.rice % 12 === 0) run.shield = 1;
}

function checkItems(run, before) {
  for (const item of run.items) {
    if (item.distance > run.distance + HIT_DEPTH.train) break;
    const laneGap = Math.abs(run.x - item.lane * LANE_WIDTH);
    if (item.kind === "rice") {
      const flying = run.summonRemaining > 0;
      if (!item.taken && before <= item.distance + RICE_RADIUS &&
          run.distance >= item.distance - RICE_RADIUS &&
          (flying || (laneGap <= 0.85 && run.y < 0.85))) {
        collectRice(run, item);
      }
      continue;
    }
    const depth = HIT_DEPTH[item.kind];
    if (item.hit || before > item.distance + depth ||
        run.distance < item.distance - depth || laneGap >= 1.22) continue;
    if (run.summonRemaining > 0 || run.graceRemaining > 0) continue;
    if (item.kind === "jump" && run.y >= 0.72) continue;
    if (item.kind === "slide" && run.rollRemaining > 0) continue;

    item.hit = true;
    run.lastHit = item.kind;
    run.hitFlash = 0.32;
    if (run.shield > 0) {
      run.shield = 0;
      run.graceRemaining = SHIELD_GRACE;
      continue;
    }
    run.phase = "over";
    run.failure = item.kind;
    return;
  }
}

function advance(run, dt) {
  run.elapsed += dt;
  run.hitFlash = Math.max(0, run.hitFlash - dt);
  run.graceRemaining = Math.max(0, run.graceRemaining - dt);
  if (run.summonRemaining > 0) {
    run.summonRemaining = Math.max(0, run.summonRemaining - dt);
    if (run.summonRemaining === 0) run.graceRemaining = SHIELD_GRACE;
  }
  updateMovement(run, dt);
  run.speed = Math.min(MAX_SPEED, START_SPEED + 0.01 * run.distance);
  if (run.summonRemaining > 0) run.speed += 3.5;
  const before = run.distance;
  run.distance += run.speed * dt;
  if (run.distance + 120 >= run.nextSection) appendSection(run);
  checkItems(run, before);
  const first = run.items.findIndex((item) => item.distance >= run.distance - 22);
  if (first > 0) run.items.splice(0, first);
}

export function stepRun(run, dt) {
  if (run.phase !== "running" || !Number.isFinite(dt) || dt <= 0) return run;
  run.accumulatedTime += Math.min(dt, 0.125);
  while (run.accumulatedTime + 1e-9 >= STEP && run.phase === "running") {
    run.accumulatedTime = Math.max(0, run.accumulatedTime - STEP);
    advance(run, STEP);
  }
  return run;
}
