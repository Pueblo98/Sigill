"use client";

// Thin SWR wrapper for the Sigil API.
// Per REVIEW-DECISIONS.md 4D, dashboard polls every 5s; no WebSocket channel.

import useSWR, { type SWRConfiguration, type SWRResponse } from "swr";

export const DEFAULT_REFRESH_INTERVAL_MS = 5000;

export function getApiBase(): string {
  if (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  return "http://localhost:8000";
}

export function buildUrl(endpoint: string): string {
  const base = getApiBase().replace(/\/+$/, "");
  if (!endpoint.startsWith("/")) endpoint = "/" + endpoint;
  return base + endpoint;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url, { credentials: "omit" });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      // ignore
    }
    throw new ApiError(res.status, body);
  }
  return (await res.json()) as T;
}

export interface UseApiResult<T> {
  data: T | undefined;
  error: Error | undefined;
  isLoading: boolean;
  mutate: SWRResponse<T>["mutate"];
}

export function useApi<T>(
  endpoint: string | null,
  config?: SWRConfiguration
): UseApiResult<T> {
  const key = endpoint ? buildUrl(endpoint) : null;
  const { data, error, isLoading, mutate } = useSWR<T>(key, fetcher, {
    refreshInterval: DEFAULT_REFRESH_INTERVAL_MS,
    revalidateOnFocus: false,
    ...config,
  });
  return { data, error, isLoading, mutate };
}
