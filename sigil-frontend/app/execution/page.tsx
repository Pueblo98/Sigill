"use client";

import React from "react";
import { useApi } from "@/lib/api/client";
import type { ApiOrder } from "@/lib/types/api";

function formatTime(iso: string | null): string {
  if (!iso) return "--";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function ExecutionLog() {
  const { data, error, isLoading } = useApi<ApiOrder[]>("/api/orders");
  const orders = data ?? [];

  return (
    <div className="flex-1 overflow-auto p-8">
      <div className="mb-8">
        <h2 className="text-3xl font-black uppercase italic text-[#e5e1e4]">
          EXECUTION LOG
        </h2>
        <p className="text-[10px] font-mono text-[#e5e1e4]/40 uppercase tracking-widest mt-1">
          Audit trail of automated orders ({orders.length} latest)
        </p>
      </div>

      <div className="bg-[#201f21] border border-[#1b1b1d]">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-[#1b1b1d] text-[10px] font-mono text-[#e5e1e4]/40 uppercase border-b border-[#201f21]">
              <th className="px-6 py-4 font-medium">Timestamp</th>
              <th className="px-4 py-4 font-medium">Platform</th>
              <th className="px-4 py-4 font-medium">Mode</th>
              <th className="px-4 py-4 font-medium">Side / Outcome</th>
              <th className="px-4 py-4 font-medium">Type</th>
              <th className="px-4 py-4 font-medium text-right">Qty</th>
              <th className="px-4 py-4 font-medium text-right">Price</th>
              <th className="px-4 py-4 font-medium text-right">Filled</th>
              <th className="px-4 py-4 font-medium text-right">Status</th>
            </tr>
          </thead>
          <tbody className="text-[11px] font-mono divide-y divide-[#1b1b1d]">
            {isLoading ? (
              <tr>
                <td colSpan={9} className="px-6 py-5 text-center text-[#958da1]">
                  Loading orders...
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={9} className="px-6 py-5 text-center text-rose-500">
                  API error: {error.message}
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-6 py-5 text-center text-[#958da1]">
                  No orders recorded.
                </td>
              </tr>
            ) : (
              orders.map((o) => (
                <tr key={o.id} className="hover:bg-[#39393b] transition-colors">
                  <td className="px-6 py-4 text-[#e5e1e4]/60">
                    {formatTime(o.created_at)}
                  </td>
                  <td className="px-4 py-4 uppercase">{o.platform}</td>
                  <td className="px-4 py-4">
                    <span
                      className={`text-[9px] font-bold px-1.5 py-0.5 ${
                        o.mode === "live"
                          ? "bg-rose-500/10 text-rose-500"
                          : "bg-[#39393b] text-[#958da1]"
                      }`}
                    >
                      {o.mode.toUpperCase()}
                    </span>
                  </td>
                  <td
                    className={`px-4 py-4 font-bold ${
                      o.side === "buy" ? "text-emerald-500" : "text-rose-500"
                    }`}
                  >
                    {o.side.toUpperCase()}_{o.outcome.toUpperCase()}
                  </td>
                  <td className="px-4 py-4 uppercase">{o.order_type}</td>
                  <td className="px-4 py-4 text-right">
                    {o.quantity.toLocaleString()}
                  </td>
                  <td className="px-4 py-4 text-right">
                    {(o.price * 100).toFixed(1)}¢
                  </td>
                  <td className="px-4 py-4 text-right">
                    {o.filled_quantity}/{o.quantity}
                  </td>
                  <td className="px-4 py-4 text-right uppercase">{o.status}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
