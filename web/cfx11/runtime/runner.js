// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

export class CoursePythonRunner extends EventTarget {
  constructor(workerUrl, { timeoutMs = 180_000 } = {}) {
    super();
    this.workerUrl = workerUrl;
    this.timeoutMs = timeoutMs;
    this.nextId = 1;
    this.pending = new Map();
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
    this.configuration = configuration;
    this.worker = new Worker(this.workerUrl, { type: "module" });
    this.worker.addEventListener("message", event => this.handle(event.data));
    this.worker.addEventListener("error", event => this.failAll(event.message || "Python worker failed."));
  }

  request(type, values = {}) {
    if (!this.worker) this.reset();
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        this.reset();
        reject(new Error(`Python execution exceeded ${Math.round(this.timeoutMs / 1000)} seconds.`));
      }, this.timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.worker.postMessage({ id, type, configuration: this.configuration, ...values });
    });
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
    if (message.type !== "result") return;
    const pending = this.pending.get(message.id);
    if (!pending) return;
    clearTimeout(pending.timer);
    this.pending.delete(message.id);
    pending.resolve(message);
  }

  failAll(message) {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error(message));
    }
    this.pending.clear();
  }
}
