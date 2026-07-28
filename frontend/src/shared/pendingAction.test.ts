import { describe, expect, it, vi } from "vitest";

import { runPendingAction } from "./pendingAction";

describe("runPendingAction", () => {
  it("owns pending state for the full action lifecycle", async () => {
    const pending = new Set<string>();
    const states: boolean[] = [];

    await runPendingAction({
      key: "buy",
      pending,
      onPendingChange: () => states.push(pending.has("buy")),
      action: () => Promise.resolve(),
      onError: vi.fn(),
    });

    expect(states).toEqual([true, false]);
  });

  it("reports failures and suppresses duplicate work", async () => {
    const pending = new Set(["busy"]);
    const action = vi.fn(() => Promise.reject(new Error("nope")));
    const onError = vi.fn();

    await runPendingAction({
      key: "busy",
      pending,
      action,
      onError,
      onPendingChange: vi.fn(),
    });
    expect(action).not.toHaveBeenCalled();

    pending.clear();
    await runPendingAction({
      key: "retry",
      pending,
      action,
      onError,
      onPendingChange: vi.fn(),
    });
    expect(onError).toHaveBeenCalledWith(expect.any(Error));
    expect(pending).toEqual(new Set());
  });
});
