import { afterEach, describe, expect, it, vi } from "vitest";

import { createClientRequestId } from "./requestId";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("createClientRequestId", () => {
  it("uses the browser UUID implementation when it is available", () => {
    const expected = "12345678-1234-4123-8123-123456789abc";
    const randomUUID = vi.fn(() => expected);
    vi.stubGlobal("crypto", {
      randomUUID,
      getRandomValues: vi.fn(),
    });

    expect(createClientRequestId()).toBe(expected);
    expect(randomUUID).toHaveBeenCalledOnce();
  });

  it("builds a valid UUID when LAN HTTP disables randomUUID", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: (target: Uint8Array) => {
        target.set(Array.from({ length: 16 }, (_value, index) => index));
        return target;
      },
    });

    expect(createClientRequestId()).toBe(
      "00010203-0405-4607-8809-0a0b0c0d0e0f",
    );
  });

  it("falls back even when an exposed randomUUID method rejects the origin", () => {
    vi.stubGlobal("crypto", {
      randomUUID: () => {
        throw new DOMException("The operation is insecure.", "SecurityError");
      },
      getRandomValues: (target: Uint8Array) => target.fill(255),
    });

    expect(createClientRequestId()).toBe(
      "ffffffff-ffff-4fff-bfff-ffffffffffff",
    );
  });
});
