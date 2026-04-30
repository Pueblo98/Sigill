import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock SWR-backed hook so tests don't need real network.
const useApiMock = vi.fn();
vi.mock("@/lib/api/client", () => ({
  useApi: (...args: unknown[]) => useApiMock(...args),
  DEFAULT_REFRESH_INTERVAL_MS: 5000,
}));

import Dashboard from "./page";

describe("Dashboard page", () => {
  beforeEach(() => {
    useApiMock.mockReset();
  });

  it("renders empty state when portfolio has no data", () => {
    useApiMock.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/portfolio") {
        return {
          data: {
            state: "no_data",
            mode: "paper",
            balance: 0,
            roi: 0,
            unrealized_pnl: 0,
            realized_pnl: 0,
            settled_trades_total: 0,
            settled_trades_30d: 0,
            as_of: null,
          },
          error: undefined,
          isLoading: false,
          mutate: vi.fn(),
        };
      }
      return {
        data: [],
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      };
    });

    render(<Dashboard />);
    expect(screen.getByText(/No bankroll snapshot yet/i)).toBeInTheDocument();
  });

  it("renders portfolio numbers when state is ok", () => {
    useApiMock.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/portfolio") {
        return {
          data: {
            state: "ok",
            mode: "paper",
            balance: 5500,
            roi: 10.0,
            unrealized_pnl: 100,
            realized_pnl: 400,
            settled_trades_total: 12,
            settled_trades_30d: 6,
            as_of: new Date().toISOString(),
          },
          error: undefined,
          isLoading: false,
          mutate: vi.fn(),
        };
      }
      if (endpoint === "/api/health") {
        return {
          data: { state: "no_data", sources: [], as_of: null },
          error: undefined,
          isLoading: false,
          mutate: vi.fn(),
        };
      }
      return {
        data: [],
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      };
    });

    render(<Dashboard />);
    expect(screen.getByText(/\$5,500/)).toBeInTheDocument();
    expect(screen.getByText(/\+10\.00% ROI/)).toBeInTheDocument();
  });

  it("renders empty positions and signals cleanly", () => {
    useApiMock.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/portfolio") {
        return {
          data: {
            state: "no_data",
            mode: "paper",
            balance: 0,
            roi: 0,
            unrealized_pnl: 0,
            realized_pnl: 0,
            settled_trades_total: 0,
            settled_trades_30d: 0,
            as_of: null,
          },
          error: undefined,
          isLoading: false,
          mutate: vi.fn(),
        };
      }
      if (endpoint === "/api/health") {
        return {
          data: { state: "no_data", sources: [], as_of: null },
          error: undefined,
          isLoading: false,
          mutate: vi.fn(),
        };
      }
      return {
        data: [],
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      };
    });

    render(<Dashboard />);
    expect(screen.getByText(/No open positions/i)).toBeInTheDocument();
    expect(screen.getByText(/No active signals/i)).toBeInTheDocument();
  });
});
