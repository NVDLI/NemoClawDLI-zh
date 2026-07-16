// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

const TERMINAL_STATES = new Set(["succeeded", "failed", "timed-out", "cancelled"]);

function safeDetail(value) {
  return String(value ?? "").trim()
    .replace(/nvapi-[A-Za-z0-9_-]{6,}/g, "nvapi-[hidden]")
    .replace(/(bearer\s+)[A-Za-z0-9._-]{8,}/gi, "$1[hidden]")
    .slice(0, 800);
}

export class ObservableOperations extends EventTarget {
  constructor({ limit = 60 } = {}) {
    super();
    this.limit = limit;
    this.records = new Map();
    this.nextId = 1;
  }

  begin(label, { id, kind = "workflow", detail = "", startedAt = Date.now() } = {}) {
    const operationId = String(id ?? `workflow-${this.nextId++}`);
    this.records.set(operationId, {
      id: operationId,
      label: safeDetail(label) || "Background work",
      kind: safeDetail(kind) || "workflow",
      state: "running",
      detail: safeDetail(detail),
      queuedAt: startedAt,
      startedAt,
      finishedAt: null,
    });
    this.trim();
    this.emit();
    return operationId;
  }

  update(id, detail) {
    const record = this.records.get(String(id));
    if (!record || TERMINAL_STATES.has(record.state)) return;
    record.detail = safeDetail(detail);
    this.emit();
  }

  settle(id, state, detail = "", timing = {}) {
    const operationId = String(id);
    const record = this.records.get(operationId) || {
      id: operationId,
      label: safeDetail(timing.label) || "Background work",
      kind: safeDetail(timing.kind) || "workflow",
      queuedAt: timing.queuedAt || Date.now(),
      startedAt: timing.startedAt || timing.queuedAt || Date.now(),
    };
    record.state = TERMINAL_STATES.has(state) ? state : "failed";
    record.detail = safeDetail(detail || record.detail);
    record.finishedAt = timing.finishedAt || Date.now();
    record.startedAt = timing.startedAt || record.startedAt;
    record.queuedAt = timing.queuedAt || record.queuedAt;
    this.records.set(operationId, record);
    this.trim();
    this.emit();
  }

  ingest(detail) {
    const id = `python-${detail.id}`;
    if (detail.state === "queued") {
      const operationId = this.begin(detail.label || `Python ${detail.type}`, {
        id,
        kind: "python",
        detail: "Waiting for the current Python job",
        startedAt: detail.queuedAt,
      });
      const record = this.records.get(operationId);
      record.state = "queued";
      this.emit();
      return;
    }
    const record = this.records.get(id);
    if (detail.state === "running") {
      if (!record) this.begin(detail.label || `Python ${detail.type}`, { id, kind: "python", startedAt: detail.startedAt });
      const active = this.records.get(id);
      active.state = "running";
      active.startedAt = detail.startedAt || Date.now();
      active.detail = detail.queueWaitMs ? `Started after ${formatDuration(detail.queueWaitMs)} in the queue` : "Running now";
      this.emit();
      return;
    }
    this.settle(id, detail.state, detail.message || "", detail);
  }

  async run(label, task, { timeoutMs = 20_000, kind = "network" } = {}) {
    const controller = new AbortController();
    const id = this.begin(label, { kind, detail: "Starting" });
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => {
        controller.abort();
        const error = new Error(`${label} exceeded ${Math.round(timeoutMs / 1000)} seconds.`);
        error.name = "WorkflowTimeoutError";
        reject(error);
      }, timeoutMs);
    });
    try {
      const result = await Promise.race([
        Promise.resolve().then(() => task({ signal: controller.signal, update: detail => this.update(id, detail) })),
        timeout,
      ]);
      this.settle(id, "succeeded", "Completed");
      return result;
    } catch (error) {
      const state = error?.name === "WorkflowTimeoutError" || error?.name === "AbortError" ? "timed-out" : "failed";
      this.settle(id, state, error?.message || String(error));
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  clearSettled() {
    for (const [id, record] of this.records) if (TERMINAL_STATES.has(record.state)) this.records.delete(id);
    this.emit();
  }

  snapshot() {
    return [...this.records.values()].sort((left, right) => (right.queuedAt || 0) - (left.queuedAt || 0));
  }

  trim() {
    const records = this.snapshot();
    for (const record of records.slice(this.limit)) {
      if (TERMINAL_STATES.has(record.state)) this.records.delete(record.id);
    }
  }

  emit() {
    this.dispatchEvent(new CustomEvent("change", { detail: this.snapshot() }));
  }
}

export function formatDuration(milliseconds) {
  const seconds = Math.max(0, Number(milliseconds || 0)) / 1000;
  return seconds < 10 ? `${seconds.toFixed(1)}s` : `${Math.round(seconds)}s`;
}
