"use client";

import React from "react";
import { useApi } from "@/lib/api/client";
import type { ArbitrageOpp } from "@/lib/types/api";

export default function ArbitrageScanner() {
  const { data, error, isLoading } = useApi<ArbitrageOpp[]>("/api/arbitrage");
  const opps = data ?? [];

  return (
    <div className="flex-1 overflow-auto p-8 h-full">
      <div className="mb-8 flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-black uppercase italic text-[#e5e1e4]">
            CROSS-PLATFORM DISCREPANCIES
          </h2>
          <p className="text-[10px] font-mono text-[#e5e1e4]/40 uppercase tracking-widest mt-1">
            Stat-arb scanner: Kalshi ↔ Polymarket
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <span
            title="Per REVIEW-DECISIONS.md 1C, Polymarket is read-only. The engine never auto-executes the Polymarket leg."
            className="bg-yellow-500/10 border border-yellow-500/30 text-yellow-500 text-[10px] font-mono font-bold px-3 py-2 uppercase tracking-widest"
          >
            DISPLAY ONLY
          </span>
        </div>
      </div>

      <div className="bg-[#201f21] border border-[#1b1b1d]">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-[#1b1b1d] text-[10px] font-mono text-[#e5e1e4]/40 uppercase border-b border-[#201f21]">
              <th className="px-6 py-4 font-medium">Event / Match</th>
              <th className="px-4 py-4 font-medium">Type</th>
              <th className="px-4 py-4 font-medium">Kalshi</th>
              <th className="px-4 py-4 font-medium">Polymarket</th>
              <th className="px-4 py-4 font-medium text-right">Implied Sum</th>
              <th className="px-4 py-4 font-medium text-right text-emerald-500">
                Net Edge
              </th>
              <th className="px-4 py-4 font-medium text-right">Kelly</th>
            </tr>
          </thead>
          <tbody className="text-[11px] font-mono divide-y divide-[#1b1b1d]">
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-6 py-5 text-center text-[#958da1]">
                  Initializing live feeds…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={7} className="px-6 py-5 text-center text-rose-500">
                  API error: {error.message}
                </td>
              </tr>
            ) : opps.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-5 text-center text-[#958da1]">
                  No arbitrage opportunities detected.
                </td>
              </tr>
            ) : (
              opps.map((arb, idx) => (
                <tr key={idx} className="hover:bg-[#39393b] transition-colors">
                  <td className="px-6 py-5">
                    <div className="font-bold text-[#e5e1e4] mb-1">{arb.event}</div>
                    <div className="flex gap-2 opacity-40 text-[9px]">
                      {arb.kalshi_ticker} :: {arb.poly_ticker}
                    </div>
                    <div className="text-[8px] text-[#958da1]/50 mt-1">
                      match {arb.match_score.toFixed(1)}/100
                    </div>
                  </td>
                  <td className="px-4 py-5">
                    <span
                      className={`text-[9px] font-bold px-1.5 py-0.5 ${
                        arb.opportunity_type === "PURE_ARB"
                          ? "bg-emerald-900/30 text-emerald-400"
                          : "bg-[#7C3AED]/20 text-[#d2bbff]"
                      }`}
                    >
                      {arb.opportunity_type}
                    </span>
                  </td>
                  <td className="px-4 py-5">
                    <div className="flex flex-col gap-0.5 text-[10px]">
                      <span className="text-[#958da1]">
                        Bid:{" "}
                        <span className="text-[#e5e1e4] font-bold">
                          {arb.kalshi_bid.toFixed(1)}¢
                        </span>
                      </span>
                      <span className="text-[#958da1]">
                        Ask:{" "}
                        <span className="text-[#e5e1e4] font-bold">
                          {arb.kalshi_ask.toFixed(1)}¢
                        </span>
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-5">
                    <div className="flex flex-col gap-0.5 text-[10px]">
                      <span className="text-[#958da1]">
                        Bid:{" "}
                        <span className="text-[#e5e1e4] font-bold">
                          {arb.poly_bid.toFixed(1)}¢
                        </span>
                      </span>
                      <span className="text-[#958da1]">
                        Ask:{" "}
                        <span className="text-[#e5e1e4] font-bold">
                          {arb.poly_ask.toFixed(1)}¢
                        </span>
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-5 text-right font-bold text-[#e5e1e4]/60">
                    {arb.implied_sum.toFixed(1)}¢
                  </td>
                  <td className="px-4 py-5 text-right">
                    <div
                      className={`font-bold ${
                        arb.net_arb >= 0 ? "text-emerald-500" : "text-rose-500"
                      }`}
                    >
                      {arb.net_arb >= 0 ? "+" : ""}
                      {arb.net_arb.toFixed(2)}%
                    </div>
                  </td>
                  <td className="px-4 py-5 text-right text-[#d2bbff] font-bold">
                    {(arb.kelly_size * 100).toFixed(2)}%
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
