"use client";

import React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { useApi } from "@/lib/api/client";
import type { ApiModelDetail } from "@/lib/types/api";

function formatPnL(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}$${v.toFixed(2)}`;
}

function formatPercent(v: number | null): string {
  if (v === null || Number.isNaN(v)) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function Stat({
  label,
  value,
  accent,
  color,
}: {
  label: string;
  value: string;
  accent?: boolean;
  color?: "green" | "red" | "neutral";
}) {
  const colorCls =
    color === "green"
      ? "text-emerald-400"
      : color === "red"
      ? "text-rose-400"
      : accent
      ? "text-[#7C3AED]"
      : "text-[#e5e1e4]";
  return (
    <div className="bg-[#1b1b1d] border border-[#201f21] p-4 flex flex-col items-center justify-center gap-1">
      <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-[#958da1]">
        {label}
      </span>
      <span className={`text-2xl font-mono ${colorCls}`}>{value}</span>
    </div>
  );
}

function EquityCurve({
  points,
}: {
  points: { t: string; cum_pnl: number }[];
}) {
  if (points.length === 0) {
    return (
      <div className="bg-[#1b1b1d] border border-[#201f21] p-12 flex items-center justify-center">
        <p className="text-[10px] font-mono uppercase tracking-widest text-[#958da1]">
          No closed trades yet — equity curve unlocks once a position settles.
        </p>
      </div>
    );
  }
  const data = points.map((p) => ({
    ...p,
    ts: new Date(p.t).getTime(),
  }));
  return (
    <div className="bg-[#1b1b1d] border border-[#201f21] p-4 h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 16, right: 24, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#39393b" strokeDasharray="2 4" />
          <XAxis
            dataKey="ts"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(v: number) =>
              new Date(v).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })
            }
            tick={{ fill: "#958da1", fontSize: 10, fontFamily: "monospace" }}
            stroke="#39393b"
          />
          <YAxis
            tick={{ fill: "#958da1", fontSize: 10, fontFamily: "monospace" }}
            stroke="#39393b"
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#201f21",
              border: "1px solid #39393b",
              fontFamily: "monospace",
              fontSize: 11,
              color: "#e5e1e4",
            }}
            labelFormatter={(v) => new Date(v as number).toLocaleString()}
            formatter={(v) => [formatPnL(Number(v)), "Cum P&L"]}
          />
          <Line
            type="monotone"
            dataKey="cum_pnl"
            stroke="#7C3AED"
            strokeWidth={2}
            dot={{ r: 2, fill: "#7C3AED" }}
            activeDot={{ r: 4, fill: "#d2bbff" }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function ModelDetail() {
  const params = useParams<{ modelId: string }>();
  const modelId = params?.modelId;
  const endpoint = modelId
    ? `/api/models/${encodeURIComponent(modelId)}`
    : null;
  const { data, error, isLoading } = useApi<ApiModelDetail>(endpoint);

  if (isLoading) {
    return (
      <div className="p-12 font-mono text-xs uppercase text-[#958da1] tracking-widest">
        Loading model…
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="p-12">
        <h1 className="text-3xl font-black text-rose-500 mb-4">404: NOT FOUND</h1>
        <p className="font-mono text-[#958da1] text-xs">
          Model id <code>{modelId}</code> is not registered.
        </p>
        <Link
          href="/models"
          className="mt-8 font-mono text-[10px] uppercase text-[#7C3AED] hover:text-[#d2bbff] underline inline-block"
        >
          ← back to models
        </Link>
      </div>
    );
  }

  const s = data.summary;
  const noData = s.state === "no_data";

  return (
    <div className="flex flex-col h-full bg-[#0e0e10] p-8 text-[#e5e1e4] overflow-y-auto w-full">
      {/* Header */}
      <div className="mb-8 max-w-6xl">
        <div className="flex items-center gap-4 mb-4">
          <Link
            href="/models"
            className="text-[#958da1] hover:text-[#e5e1e4] transition-colors text-xs"
          >
            ← back to models
          </Link>
          <span className="bg-[#39393b] text-[#958da1] text-[9px] font-bold px-2 py-0.5 font-mono tracking-widest uppercase">
            {data.version}
          </span>
          {data.tags.map((t) => (
            <span
              key={t}
              className="text-[9px] font-bold px-1.5 py-0.5 bg-[#7C3AED]/20 text-[#d2bbff] font-mono uppercase tracking-widest"
            >
              {t}
            </span>
          ))}
        </div>
        <h1 className="text-4xl md:text-5xl font-black leading-none tracking-tight mb-3">
          {data.display_name}
        </h1>
        <p className="text-sm text-[#958da1] max-w-3xl">{data.description}</p>
      </div>

      {/* Stat strip */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8 max-w-6xl">
        <Stat
          label="Trades"
          value={noData ? "--" : String(s.trades_total)}
        />
        <Stat label="Win Rate" value={formatPercent(s.win_rate)} />
        <Stat
          label="Realized P&L"
          value={noData ? "--" : formatPnL(s.realized_pnl)}
          color={
            noData
              ? "neutral"
              : s.realized_pnl > 0
              ? "green"
              : s.realized_pnl < 0
              ? "red"
              : "neutral"
          }
        />
        <Stat
          label="Unrealized"
          value={noData ? "--" : formatPnL(s.unrealized_pnl)}
          color={
            noData
              ? "neutral"
              : s.unrealized_pnl > 0
              ? "green"
              : s.unrealized_pnl < 0
              ? "red"
              : "neutral"
          }
        />
        <Stat
          label="Max Drawdown"
          value={
            s.max_drawdown !== null && !noData
              ? `-$${s.max_drawdown.toFixed(2)}`
              : "--"
          }
        />
        <Stat
          label="Predictions / 24h"
          value={String(s.predictions_24h)}
          accent
        />
      </div>

      {/* Equity curve */}
      <div className="mb-8 max-w-6xl">
        <h3 className="text-[10px] font-mono font-bold text-[#7C3AED] uppercase tracking-[0.2em] mb-3">
          P&amp;L Equity Curve
        </h3>
        <EquityCurve points={data.equity_curve} />
      </div>

      {/* Recent trades */}
      <div className="mb-8 max-w-6xl">
        <h3 className="text-[10px] font-mono font-bold text-[#7C3AED] uppercase tracking-[0.2em] mb-3">
          Recent Trades ({data.recent_trades.length})
        </h3>
        <div className="bg-[#201f21] overflow-hidden">
          {data.recent_trades.length === 0 ? (
            <div className="p-8 text-[10px] font-mono uppercase tracking-widest text-[#958da1]">
              No trades yet — decision loop hasn't acted on this model's predictions.
            </div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-[#2a2a2c]/90 backdrop-blur z-10">
                  <tr>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1]">
                      Time
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1]">
                      Market
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1]">
                      Side
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1]">
                      Outcome
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                      Qty
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                      Fill
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                      Edge@Entry
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1]">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#4a4455]/5">
                  {data.recent_trades.map((t) => (
                    <tr key={t.id} className="hover:bg-[#39393b]">
                      <td className="px-4 py-3 text-[10px] font-mono text-[#958da1]">
                        {t.created_at
                          ? new Date(t.created_at).toLocaleString()
                          : "--"}
                      </td>
                      <td className="px-4 py-3 text-[10px] font-mono text-[#e5e1e4] max-w-xs truncate">
                        <Link
                          href={`/trade-detail/${encodeURIComponent(t.external_id)}`}
                          className="hover:text-[#d2bbff]"
                        >
                          {t.market_title}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-[10px] font-mono uppercase">
                        <span
                          className={
                            t.side === "buy"
                              ? "text-emerald-400"
                              : "text-rose-400"
                          }
                        >
                          {t.side}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[10px] font-mono uppercase text-[#e5e1e4]">
                        {t.outcome}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">
                        {t.filled_quantity} / {t.quantity}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">
                        {t.avg_fill_price !== null
                          ? `${(t.avg_fill_price * 100).toFixed(1)}¢`
                          : "--"}
                      </td>
                      <td
                        className={`px-4 py-3 text-right font-mono text-[10px] ${
                          t.edge_at_entry !== null && t.edge_at_entry >= 0
                            ? "text-emerald-400"
                            : t.edge_at_entry !== null
                            ? "text-rose-400"
                            : "text-[#e5e1e4]/40"
                        }`}
                      >
                        {t.edge_at_entry !== null
                          ? `${t.edge_at_entry >= 0 ? "+" : ""}${(t.edge_at_entry * 100).toFixed(2)}¢`
                          : "--"}
                      </td>
                      <td className="px-4 py-3 text-[9px] font-mono uppercase">
                        <span
                          className={`px-2 py-0.5 ${
                            t.status === "filled"
                              ? "bg-emerald-900/30 text-emerald-400"
                              : t.status === "rejected" ||
                                t.status === "failed"
                              ? "bg-rose-900/30 text-rose-400"
                              : "bg-[#39393b] text-[#958da1]"
                          }`}
                        >
                          {t.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Recent predictions */}
      <div className="mb-8 max-w-6xl">
        <h3 className="text-[10px] font-mono font-bold text-[#7C3AED] uppercase tracking-[0.2em] mb-3">
          Recent Predictions ({data.recent_predictions.length})
        </h3>
        <div className="bg-[#201f21] overflow-hidden">
          {data.recent_predictions.length === 0 ? (
            <div className="p-8 text-[10px] font-mono uppercase tracking-widest text-[#958da1]">
              No predictions yet.
            </div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-[#2a2a2c]/90 backdrop-blur z-10">
                  <tr>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1]">
                      Time
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1]">
                      Market
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                      Pred P
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                      Market P
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                      Edge
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                      Conf
                    </th>
                    <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1]">
                      Order
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#4a4455]/5">
                  {data.recent_predictions.map((p) => (
                    <tr key={p.id} className="hover:bg-[#39393b]">
                      <td className="px-4 py-3 text-[10px] font-mono text-[#958da1]">
                        {p.created_at
                          ? new Date(p.created_at).toLocaleString()
                          : "--"}
                      </td>
                      <td className="px-4 py-3 text-[10px] font-mono text-[#e5e1e4] max-w-xs truncate">
                        <Link
                          href={`/trade-detail/${encodeURIComponent(p.external_id)}`}
                          className="hover:text-[#d2bbff]"
                        >
                          {p.market_title}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">
                        {(p.predicted_prob * 100).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">
                        {p.market_price_at_prediction !== null
                          ? `${(p.market_price_at_prediction * 100).toFixed(1)}¢`
                          : "--"}
                      </td>
                      <td
                        className={`px-4 py-3 text-right font-mono text-[10px] ${
                          p.edge !== null && p.edge >= 0
                            ? "text-emerald-400"
                            : p.edge !== null
                            ? "text-rose-400"
                            : "text-[#e5e1e4]/40"
                        }`}
                      >
                        {p.edge !== null
                          ? `${p.edge >= 0 ? "+" : ""}${(p.edge * 100).toFixed(2)}¢`
                          : "--"}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">
                        {p.confidence !== null
                          ? `${(p.confidence * 100).toFixed(0)}%`
                          : "--"}
                      </td>
                      <td className="px-4 py-3 text-[9px] font-mono uppercase">
                        {p.order_id ? (
                          <span className="bg-emerald-900/30 text-emerald-400 px-2 py-0.5">
                            {p.order_status || "linked"}
                          </span>
                        ) : (
                          <span className="text-[#958da1]/60">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
