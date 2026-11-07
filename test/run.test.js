import assert from "node:assert/strict";
import { test } from "node:test";
import { command, createRun, LANE_WIDTH, restartRun, stepRun } from "../src/run.js";

const DT = 1 / 60;

function reach(run, distance) {
  while (run.distance < distance && run.phase === "running") {
    const before = run.distance;
    stepRun(run, DT);
    assert.ok(run.distance > before, "running always moves the player forward");
  }
}

test("opening train, low barrier, and gate can be cleared in order", () => {
  const run = restartRun(createRun());
  reach(run, 20);
  command(run, "right");
  reach(run, 58.5);
  assert.equal(run.x, LANE_WIDTH);
  command(run, "jump");
  reach(run, 64);
  assert.equal(run.y > 0, true);
  reach(run, 92.2);
  assert.equal(command(run, "roll"), true);
  reach(run, 97);
  const remaining = run.rollRemaining;
  assert.ok(remaining > 0);
  assert.equal(command(run, "roll"), false);
  assert.equal(run.rollRemaining, remaining);
  reach(run, 108);
  assert.equal(run.rollRemaining, 0);
  assert.equal(run.phase, "running");
  assert.equal(run.shield, 1);
  assert.equal(run.lastHit, null);
  assert.ok(run.rice >= 10);
  assert.equal(command(run, "summon"), true);
  assert.equal(run.energy, 0);
  reach(run, 134);
  assert.equal(run.phase, "running");
  assert.ok(run.y > 1.5);
});

test("contact consumes the initial shield, then the next unavoided hazard ends the run", () => {
  const run = restartRun(createRun());
  reach(run, 40);
  assert.equal(run.shield, 0);
  assert.equal(run.lastHit, "train");
  command(run, "right");
  reach(run, 70);
  assert.equal(run.phase, "over");
  assert.equal(run.failure, "jump");
  assert.ok(run.distance >= 61 && run.distance < 63);
  assert.equal(restartRun(run).phase, "running");
  assert.equal(run.distance, 0);
  assert.equal(run.shield, 1);
  assert.equal(run.failure, null);
});

test("track replenishes after the first section and fixed steps are independent of frame rate", () => {
  const fast = restartRun(createRun());
  const slow = restartRun(createRun());
  command(fast, "left");
  command(slow, "left");
  for (let tick = 0; tick < 96; tick++) stepRun(fast, 1 / 120);
  for (let frame = 0; frame < 24; frame++) stepRun(slow, 1 / 30);
  assert.equal(fast.distance, slow.distance);
  assert.equal(fast.x, slow.x);
  assert.equal(command(fast, "pause"), true);
  assert.equal(stepRun(fast, 0.125).distance, slow.distance);
  assert.equal(command(fast, "resume"), true);

  while (fast.distance < 380 && fast.phase === "running") {
    const nextHazard = fast.items.find((item) => item.kind !== "rice" &&
      item.distance > fast.distance - 3);
    if (nextHazard && nextHazard.distance < fast.distance + 8) {
      const blocked = fast.items.filter((item) => item.kind !== "rice" &&
        item.distance === nextHazard.distance).map((item) => item.lane);
      if (blocked.includes(fast.lane)) {
        const clear = [-1, 0, 1].find((lane) => !blocked.includes(lane));
        command(fast, clear < fast.lane ? "left" : "right");
      }
    }
    stepRun(fast, DT);
  }
  assert.equal(fast.phase, "running");
  assert.equal(fast.shield, 1);
  assert.ok(fast.items.some((item) => item.distance > 600));
  assert.ok(fast.items.every((item) => item.distance >= fast.distance - 22));
});
