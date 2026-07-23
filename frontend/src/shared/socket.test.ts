import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveSocket } from "./socket";

class FakeWindow extends EventTarget {
  readonly location = {
    protocol: "http:",
    host: "localhost:1515",
  };

  setTimeout(
    callback: () => void,
    delay?: number,
  ): ReturnType<typeof globalThis.setTimeout> {
    return globalThis.setTimeout(callback, delay);
  }

  clearTimeout(timer: ReturnType<typeof globalThis.setTimeout>): void {
    globalThis.clearTimeout(timer);
  }

  setInterval(
    callback: () => void,
    delay?: number,
  ): ReturnType<typeof globalThis.setInterval> {
    return globalThis.setInterval(callback, delay);
  }

  clearInterval(timer: ReturnType<typeof globalThis.setInterval>): void {
    globalThis.clearInterval(timer);
  }
}

class FakeWebSocket extends EventTarget {
  static readonly OPEN = 1;
  static instances: FakeWebSocket[] = [];

  readonly url: string;
  readyState = 0;
  sent: string[] = [];

  constructor(url: string) {
    super();
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(payload: string): void {
    this.sent.push(payload);
  }

  close(): void {
    if (this.readyState === 3) {
      return;
    }
    this.readyState = 3;
    this.dispatchEvent(new Event("close"));
  }
}

describe("LiveSocket lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal("window", new FakeWindow());
    vi.stubGlobal("navigator", { onLine: true });
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("starts idempotently and closes its active socket", () => {
    const socket = new LiveSocket({
      role: "bet",
      onMessage: vi.fn(),
      onStatus: vi.fn(),
    });

    socket.start();
    socket.start();

    expect(FakeWebSocket.instances).toHaveLength(1);
    socket.stop();
    expect(FakeWebSocket.instances[0]?.readyState).toBe(3);
  });

  it("cancels a scheduled retry when reconnecting immediately", () => {
    const socket = new LiveSocket({
      role: "display",
      onMessage: vi.fn(),
      onStatus: vi.fn(),
    });
    socket.start();
    FakeWebSocket.instances[0]?.close();

    socket.reconnect();
    vi.advanceTimersByTime(1_000);

    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[1]?.url).toContain("role=display");
    socket.stop();
  });

  it("does not leave a backoff retry behind after the browser comes online", () => {
    const socket = new LiveSocket({
      role: "bet",
      onMessage: vi.fn(),
      onStatus: vi.fn(),
    });
    socket.start();
    FakeWebSocket.instances[0]?.close();

    window.dispatchEvent(new Event("online"));
    vi.advanceTimersByTime(1_000);

    expect(FakeWebSocket.instances).toHaveLength(2);
    socket.stop();
  });
});
