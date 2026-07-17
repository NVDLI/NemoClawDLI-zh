// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import test from "node:test";
import { CoursePythonRunner } from "../../web/cfx11/runtime/runner.js";
import { ObservableOperations } from "../../web/cfx11/runtime/operations.js";

class FakeWorker extends EventTarget {
  static instances = [];

  constructor() {
    super();
    this.messages = [];
    this.terminated = false;
    FakeWorker.instances.push(this);
  }

  postMessage(message) {
    this.messages.push(message);
  }

  terminate() {
    this.terminated = true;
  }

  reply(message) {
    this.dispatchEvent(new MessageEvent("message", { data: message }));
  }
}

globalThis.Worker = FakeWorker;

test("runner reports every queue and execution transition", async () => {
  const runner = new CoursePythonRunner(new URL("file:///worker.js"), { queueTimeoutMs: 100, runTimeoutMs: 100 });
  const states = [];
  runner.addEventListener("job-state", event => states.push(event.detail));
  runner.reset({});
  const request = runner.inspect({ label: "Refresh runtime variables" });
  await new Promise(resolve => setTimeout(resolve, 0));
  const worker = FakeWorker.instances.at(-1);
  worker.reply({ type: "result", id: request.requestId, ok: true, kernel: {} });
  await request;
  assert.deepEqual(states.map(event => event.state), ["queued", "running", "succeeded"]);
  assert.equal(states.at(-1).label, "Refresh runtime variables");
  runner.stop();
});

test("a queued job fails visibly instead of waiting forever", async () => {
  const runner = new CoursePythonRunner(new URL("file:///worker.js"), { queueTimeoutMs: 12, runTimeoutMs: 200 });
  const ledger = new ObservableOperations();
  runner.addEventListener("job-state", event => ledger.ingest(event.detail));
  runner.reset({});
  const active = runner.run("input()", "", { label: "Waiting cell" });
  active.catch(() => {});
  await new Promise(resolve => setTimeout(resolve, 0));
  const queued = runner.inspect({ label: "Refresh runtime variables" });
  await assert.rejects(queued, /waited more than/);
  const refresh = ledger.snapshot().find(record => record.label === "Refresh runtime variables");
  assert.equal(refresh.state, "timed-out");
  runner.stop();
});

test("an execution timeout cancels dependent queued work and replaces the worker", async () => {
  const runner = new CoursePythonRunner(new URL("file:///worker.js"), { queueTimeoutMs: 100, runTimeoutMs: 12 });
  const states = [];
  runner.addEventListener("job-state", event => states.push(event.detail));
  runner.reset({});
  const firstWorker = FakeWorker.instances.at(-1);
  const active = runner.run("while True: pass", "", { label: "Stalled cell" });
  await new Promise(resolve => setTimeout(resolve, 0));
  const dependent = runner.inspect({ label: "Dependent refresh" });
  await assert.rejects(active, /execution exceeded/);
  await assert.rejects(dependent, /restarted after/);
  assert.equal(states.find(event => event.label === "Stalled cell" && event.state === "timed-out")?.state, "timed-out");
  assert.equal(states.find(event => event.label === "Dependent refresh" && event.state === "cancelled")?.state, "cancelled");
  assert.equal(firstWorker.terminated, true);
  assert.notEqual(FakeWorker.instances.at(-1), firstWorker);
  runner.stop();
});

test("lesson context changes stay lazy until a worker exists, then replace it", async () => {
  const runner = new CoursePythonRunner(new URL("file:///worker.js"), { queueTimeoutMs: 100, runTimeoutMs: 100 });
  assert.equal(runner.switchContext({ lessonDirectory: "lesson-one" }), false);
  assert.equal(runner.worker, null);
  assert.equal(runner.configuration.lessonDirectory, "lesson-one");

  const pending = runner.preload({ label: "Start first lesson" });
  pending.catch(() => {});
  await new Promise(resolve => setTimeout(resolve, 0));
  const firstWorker = FakeWorker.instances.at(-1);
  assert.equal(runner.switchContext({ lessonDirectory: "lesson-two" }, "Lesson changed."), true);
  await assert.rejects(pending, /Lesson changed/);
  assert.equal(firstWorker.terminated, true);
  assert.notEqual(FakeWorker.instances.at(-1), firstWorker);
  assert.equal(runner.configuration.lessonDirectory, "lesson-two");
  runner.stop();
});

test("observed network work times out and records the failure", async () => {
  const ledger = new ObservableOperations();
  await assert.rejects(
    ledger.run("Connection check", () => new Promise(() => {}), { timeoutMs: 8 }),
    /exceeded/,
  );
  const record = ledger.snapshot().find(candidate => candidate.label === "Connection check");
  assert.equal(record.state, "timed-out");
  assert.ok(record.finishedAt >= record.startedAt);
});
