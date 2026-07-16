// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

export class CoursePythonRunner extends EventTarget {
  constructor(workerUrl, { timeoutMs = 180_000 } = {}) {
    super();
    this.workerUrl = workerUrl;
    this.timeoutMs = timeoutMs;
    this.nextId = 1;
    this.pending = new Map();
    this.queue = [];
    this.active = null;
    this.worker = null;
    this.configuration = null;
  }

  reset(configuration = this.configuration) {
    this.worker?.terminate();
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error("Python runtime reset."));
    }
    this.pending.clear();
    this.queue = [];
    this.active = null;
    this.configuration = configuration;
    this.worker = new Worker(this.workerUrl, { type: "module" });
    this.worker.addEventListener("message", event => this.handle(event.data));
    this.worker.addEventListener("error", event => this.failAll(event.message || "Python worker failed."));
    this.emitQueue();
  }

  request(type, values = {}) {
    if (!this.worker) this.reset();
    const id = this.nextId++;
    const promise = new Promise((resolve, reject) => {
      const job = { id, type, values, configuration: this.configuration, resolve, reject, timer: null };
      this.pending.set(id, job);
      this.queue.push(job);
      this.emitQueue();
      queueMicrotask(() => this.pump());
    });
    promise.requestId = id;
    return promise;
  }

  configure(configuration) {
    this.configuration = configuration;
  }

  pump() {
    if (this.active || !this.queue.length) return;
    const job = this.queue.shift();
    this.active = job;
    job.timer = setTimeout(() => {
      this.pending.delete(job.id);
      job.reject(new Error(`Python execution exceeded ${Math.round(this.timeoutMs / 1000)} seconds.`));
      this.reset();
    }, this.timeoutMs);
    this.worker.postMessage({ id: job.id, type: job.type, configuration: job.configuration, ...job.values });
    this.dispatchEvent(new CustomEvent("job-start", { detail: { id: job.id, type: job.type } }));
    this.emitQueue();
  }

  emitQueue() {
    this.dispatchEvent(new CustomEvent("queue-change", {
      detail: { active: this.active?.id || null, queued: this.queue.length },
    }));
  }

  preload() {
    return this.request("preload");
  }

  run(source, apiKey) {
    return this.request("run", { source, apiKey });
  }

  chat(chatId, prompt, apiKey) {
    return this.request("chat", { chatId, prompt, apiKey });
  }

  inspect() {
    return this.request("inspect");
  }

  stop() {
    this.worker?.terminate();
    this.failAll("Python execution stopped.");
    this.reset();
  }

  handle(message) {
    if (message.type === "model-stream") {
      this.dispatchEvent(new CustomEvent("model-stream", { detail: message }));
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
    if (pending.timer) clearTimeout(pending.timer);
    this.pending.delete(message.id);
    if (this.active?.id === message.id) this.active = null;
    pending.resolve(message);
    this.emitQueue();
    this.pump();
  }

  failAll(message) {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error(message));
    }
    this.pending.clear();
    this.queue = [];
    this.active = null;
    this.emitQueue();
  }
}
