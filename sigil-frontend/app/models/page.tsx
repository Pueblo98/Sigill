"use client";

import React, { useMemo, useState } from "react";
import { useApi } from "@/lib/api/client";
import type { ApiPrediction } from "@/lib/types/api";

export default function Models() {
  const [modelFilter, setModelFilter] = useState<string>("");
  const endpoint = modelFilter
    ? `/api/predictions?model_id=${encodeURIComponent(modelFilter)}`
    : "/api/predictions";
  const { data, error, isLoading } = useApi<ApiPrediction[]>(endpoint);
  const predictions = data ?? [];

  const stats = useMemo(() => {
    if (predictions.length === 0) {
      return { count: 0, avgEdge: null, avgConf: null };
    }
    const edges = predictions
      .map((p) => p.edge)
      .filter((v): v is number => v !== null);
    const confs = predictions
      .map((p) => p.confidence)
      .filter((v): v is number => v !== null);
    const avg = (arr: number[]) =>
      arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
    return {
      count: predictions.length,
      avgEdge: avg(edges),
      avgConf: avg(confs),
    };
  }, [predictions]);

  const byModel = useMemo(() => {
    const m = new Map<string, ApiPrediction[]>();
    for (const p of predictions) {
      const key = `${p.model_id}@${p.model_version}`;
      const arr = m.get(key) ?? [];
      arr.push(p);
      m.set(key, arr);
    }
    return Array.from(m.entries());
  }, [predictions]);

  return (
    <div className="p-6">
      <header className="flex justify-between items-center mb-8 pb-4 border-b border-[#4a4455]/10">
        <div>
          <h2 className="text-xs font-medium uppercase tracking-[0.2em] text-[#958da1] mb-1">
            Model Performance
          </h2>
          <h1 className="text-2xl font-black tracking-tight text-[#e5e1e4]">
            PREDICTIONS LOG
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <input
            type="text"
            placeholder="Filter by model_id..."
            value={modelFilter}
            onChange={(e) => setModelFilter(e.target.value)}
            className="bg-[#1b1b1d] border border-[#201f21] px-3 py-2 text-[10px] font-mono text-[#e5e1e4] focus:outline-none focus:border-[#7C3AED]/50"
          />
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-[#201f21] p-6 border-l-2 border-[#7C3AED]">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#958da1]">
            Predictions
          </h3>
          <p className="font-mono text-3xl font-bold text-[#e5e1e4] mt-2">
            {stats.count}
          </p>
        </div>
        <div className="bg-[#201f21] p-6 border-l-2 border-[#4a4455]/40">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#958da1]">
            Avg Edge
          </h3>
          <p className="font-mono text-3xl font-bold text-[#e5e1e4] mt-2">
            {stats.avgEdge !== null
              ? `${(stats.avgEdge * 100).toFixed(2)}¢`
              : "--"}
          </p>
        </div>
        <div className="bg-[#201f21] p-6 border-l-2 border-[#7C3AED]">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#958da1]">
            Avg Confidence
          </h3>
          <p className="font-mono text-3xl font-bold text-[#e5e1e4] mt-2">
            {stats.avgConf !== null
              ? `${(stats.avgConf * 100).toFixed(1)}%`
              : "--"}
          </p>
        </div>
      </div>

      <div className="bg-[#201f21] overflow-hidden flex flex-col">
        <div className="p-4 border-b border-[#4a4455]/10 bg-[#2a2a2c]/30">
          <h3 className="text-xs font-bold uppercase tracking-widest text-[#e5e1e4]">
            Recent Predictions
          </h3>
        </div>
        {isLoading ? (
          <div className="p-8 text-[10px] font-mono uppercase tracking-widest text-[#958da1]">
            Loading predictions...
          </div>
        ) : error ? (
          <div className="p-8 text-[10px] font-mono uppercase tracking-widest text-rose-500">
            API error: {error.message}
          </div>
        ) : predictions.length === 0 ? (
          <div className="p-8 text-[10px] font-mono uppercase tracking-widest text-[#958da1]">
            No predictions yet. Models have not produced output.
          </div>
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-[#2a2a2c]/90 backdrop-blur z-10">
                <tr>
                  <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1]">
                    Model
                  </th>
                  <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                    Predicted P
                  </th>
                  <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                    Market P
                  </th>
                  <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                    Edge
                  </th>
                  <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                    Confidence
                  </th>
                  <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] text-right">
                    When
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#4a4455]/5">
                {predictions.map((p) => (
                  <tr key={p.id} className="hover:bg-[#39393b]">
                    <td className="px-4 py-3 text-[10px] font-mono text-[#e5e1e4]">
                      {p.model_id}@{p.model_version}
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
                          ? "text-emerald-500"
                          : p.edge !== null
                          ? "text-rose-500"
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
                    <td className="px-4 py-3 text-right font-mono text-[10px] text-[#958da1]">
                      {p.created_at
                        ? new Date(p.created_at).toLocaleString()
                        : "--"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {byModel.length > 0 && (
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {byModel.map(([key, preds]) => (
            <div key={key} className="bg-[#201f21] p-4 border border-[#1b1b1d]">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#d2bbff]">
                {key}
              </h4>
              <p className="font-mono text-2xl font-bold text-[#e5e1e4] mt-2">
                {preds.length}
              </p>
              <p className="text-[9px] font-mono text-[#958da1]">predictions</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
