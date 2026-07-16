// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

export class CoursePythonRunner extends EventTarget {
  constructor(workerUrl, { runTimeoutMs = 180_000, queueTimeoutMs = 30_000 } = {}) {
    super();
    this.workerUrl = workerUrl;
    this.runTimeoutMs = runTimeoutMs;
    this.queueTimeoutMs = queueTimeoutMs;
    this.nextId = 1;
    this.pending = new Map();
    this.queue = [];
    this.active = null;
    this.worker = null;
    this.configuration = null;
  }

  createWorker() {
    this.worker = new Worker(this.workerUrl, { type: "module" });
    this.worker.addEventListener("message", event => this.handle(event.data));
    this.worker.addEventListener("error", event => {
      const message = event.message || "Python worker failed.";
      this.failAll(message, "failed");
      this.worker?.terminate();
      this.worker = null;
    });
  }

  reset(configuration = this.configuration, reason = "Python runtime reset.") {
    this.worker?.terminate();
    this.worker = null;
    this.failAll(reason, "cancelled");
    this.configuration = configuration;
    this.createWorker();
    this.emitQueue();
  }

  request(type, values = {}, { label = `Python ${type}` } = {}) {
    if (!this.worker) this.reset();
    const id = this.nextId++;
    const promise = new Promise((resolve, reject) => {
      const job = {
        id, type, label, values, configuration: this.configuration, resolve, reject,
        timer: null, queuedAt: Date.now(), startedAt: null,
      };
      this.pending.set(id, job);
      this.queue.push(job);
      this.armTimeout(job, this.queueTimeoutMs, "queue");
      this.emitJob(job, "queued");
      this.emitQueue();
      queueMicrotask(() => this.pump());
    });
    promise.requestId = id;
    return promise;
  }

  configure(configuration) {
    this.configuration = configuration;
  }

  armTimeout(job, timeoutMs, phase) {
    clearTimeout(job.timer);
    job.timer = setTimeout(() => this.expire(job, phase, timeoutMs), timeoutMs);
  }

  expire(job, phase, timeoutMs) {
    if (!this.pending.has(job.id)) return;
    const message = phase === "queue"
      ? `Python job waited more than ${Math.round(timeoutMs / 1000)} seconds in the queue.`
      : `Python execution exceeded ${Math.round(timeoutMs / 1000)} seconds.`;
    clearTimeout(job.timer);
    this.pending.delete(job.id);
    this.queue = this.queue.filter(candidate => candidate.id !== job.id);
    if (this.active?.id === job.id) {
      this.active = null;
      this.worker?.terminate();
      this.worker = null;
    }
    job.reject(new Error(message));
    this.emitJob(job, "timed-out", message);
    if (!this.worker) {
      this.failAll("Python restarted after a timed-out execution.", "cancelled");
      this.createWorker();
    }
    this.emitQueue();
    this.pump();
  }

  pump() {
    if (this.active || !this.queue.length) return;
    const job = this.queue.shift();
    if (!this.pending.has(job.id)) return this.pump();
    this.active = job;
    job.startedAt = Date.now();
    this.armTimeout(job, this.runTimeoutMs, "run");
    this.worker.postMessage({ id: job.id, type: job.type, configuration: job.configuration, ...job.values });
    this.emitJob(job, "running");
    this.dispatchEvent(new CustomEvent("job-start", { detail: { id: job.id, type: job.type } }));
    this.emitQueue();
  }

  emitJob(job, state, message = "") {
    const finishedAt = ["succeeded", "failed", "timed-out", "cancelled"].includes(state) ? Date.now() : null;
    this.dispatchEvent(new CustomEvent("job-state", {
      detail: {
        id: job.id,
        type: job.type,
        label: job.label,
        state,
        message,
        queuedAt: job.queuedAt,
        startedAt: job.startedAt,
        finishedAt,
        queueWaitMs: job.startedAt ? job.startedAt - job.queuedAt : null,
        runMs: finishedAt && job.startedAt ? finishedAt - job.startedAt : null,
      },
    }));
  }

  emitQueue() {
    this.dispatchEvent(new CustomEvent("queue-change", {
      detail: {
        active: this.active?.id || null,
        activeLabel: this.active?.label || "",
        queued: this.queue.length,
      },
    }));
  }

  preload(options) {
    return this.request("preload", {}, options);
  }

  run(source, apiKey, options) {
    return this.request("run", { source, apiKey }, options);
  }

  chat(chatId, prompt, apiKey, options) {
    return this.request("chat", { chatId, prompt, apiKey }, options);
  }

  assistant(prompt, context, apiKey, options) {
    return this.request("assistant", { prompt, context, apiKey }, options);
  }

  inspect(options) {
    return this.request("inspect", {}, options);
  }

  stop() {
    this.reset(this.configuration, "Python execution stopped.");
  }

  handle(message) {
    if (message.type === "model-stream") {
      this.dispatchEvent(new CustomEvent("model-stream", { detail: message }));
      return;
    }
    if (message.type === "operation-note") {
      this.dispatchEvent(new CustomEvent("operation-note", { detail: message }));
      return;
    }
    if (message.type === "input-request") {
      let answered = false;
      const respond = value => {
        if (answered || !this.worker) return;
        answered = true;
        this.worker.postMessage({ type: "input-response", promptId: message.promptId, value: String(value ?? "") });
      };
      this.dispatchEvent(new CustomEvent("input-request", {
        detail: { prompt: String(message.prompt || ""), requestId: message.requestId, respond },
      }));
      return;
    }
    if (message.type !== "result") return;
    const pending = this.pending.get(message.id);
    if (!pending) return;
    clearTimeout(pending.timer);
    this.pending.delete(message.id);
    if (this.active?.id === message.id) this.active = null;
    this.emitJob(pending, message.ok ? "succeeded" : "failed", message.ok ? "" : message.stderr || "Python job failed.");
    pending.resolve(message);
    this.emitQueue();
    this.pump();
  }

  failAll(message, state = "failed") {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error(message));
      this.emitJob(pending, state, message);
    }
    this.pending.clear();
    this.queue = [];
    this.active = null;
    this.emitQueue();
  }
}
