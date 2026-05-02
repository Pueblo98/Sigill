import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import {
  buildUrl,
  DEFAULT_REFRESH_INTERVAL_MS,
  fetcher,
  getApiBase,
  useApi,
  ApiError,
} from "./client";

describe("getApiBase / buildUrl", () => {
  const original = process.env.NEXT_PUBLIC_API_URL;
  afterEach(() => {
    if (original === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = original;
  });

  it("defaults to localhost:8003 dev port", () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    expect(getApiBase()).toBe("http://localhost:8003");
  });

  it("respects NEXT_PUBLIC_API_URL", () => {
    process.env.NEXT_PUBLIC_API_URL = "http://api.sigil.local:8080";
    expect(getApiBase()).toBe("http://api.sigil.local:8080");
  });

  it("composes URLs correctly", () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    expect(buildUrl("/api/portfolio")).toBe("http://localhost:8003/api/portfolio");
    expect(buildUrl("api/markets")).toBe("http://localhost:8003/api/markets");
  });

  it("strips trailing slashes from base", () => {
    process.env.NEXT_PUBLIC_API_URL = "http://example.com/";
    expect(buildUrl("/api/x")).toBe("http://example.com/api/x");
  });
});

describe("DEFAULT_REFRESH_INTERVAL_MS", () => {
  it("is 5000 (REVIEW-DECISIONS.md 4D)", () => {
    expect(DEFAULT_REFRESH_INTERVAL_MS).toBe(5000);
  });
});

describe("fetcher", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed JSON on success", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    );
    const data = await fetcher<{ ok: boolean }>("http://localhost:8000/api/x");
    expect(data).toEqual({ ok: true });
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("throws ApiError on non-2xx", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "nope" }), { status: 500 })
    );
    await expect(fetcher("http://localhost:8000/api/x")).rejects.toBeInstanceOf(
      ApiError
    );
  });
});

describe("useApi", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("composes the URL from endpoint and calls fetch with the correct URL", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ hello: "world" }), { status: 200 })
    );

    const { result } = renderHook(() =>
      useApi<{ hello: string }>("/api/portfolio", { refreshInterval: 0 })
    );

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data).toEqual({ hello: "world" });

    const calledWith = String(fetchSpy.mock.calls[0]?.[0] ?? "");
    expect(calledWith).toContain("/api/portfolio");
  });

  it("returns no data and no error when endpoint is null", () => {
    const { result } = renderHook(() => useApi<unknown>(null));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeUndefined();
  });
});
