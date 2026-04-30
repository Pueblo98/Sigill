"use client";

import React from "react";
import { useApi } from "@/lib/api/client";
import type { Health, HealthSource } from "@/lib/types/api";

function statusStyle(status: string): {
  badge: string;
  dot: string;
  label: string;
} {
  const s = status.toLowerCase();
  if (s === "ok" || s === "healthy") {
    return {
      badge: "bg-emerald-500/10 text-emerald-500",
      dot: "bg-emerald-500",
      label: "Healthy",
    };
  }
  if (s === "degraded" || s === "warning") {
    return {
      badge: "bg-yellow-500/10 text-yellow-500",
      dot: "bg-yellow-500",
      label: "Degraded",
    };
  }
  return {
    badge: "bg-rose-500/10 text-rose-500",
    dot: "bg-rose-500",
    label: "Failing",
  };
}

function SourceCard({ s }: { s: HealthSource }) {
  const style = statusStyle(s.status);
  return (
    <div className="bg-[#201f21] p-4 flex flex-col gap-4 border border-transparent hover:border-[#d2bbff]/20 transition-all">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#d2bbff]/80 font-mono">
            INGESTION
          </p>
          <h3 className="text-lg font-black tracking-tight">{s.source_name}</h3>
        </div>
        <div className={`flex items-center gap-1.5 px-2 py-0.5 ${style.badge}`}>
          <span className={`w-1.5 h-1.5 ${style.dot}`}></span>
          <span className="text-[9px] font-bold uppercase">{style.label}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mt-auto">
        <div>
          <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">
            P50 Latency
          </p>
          <p className="text-sm font-mono font-bold">
            {s.latency_p50_ms !== null ? `${s.latency_p50_ms}ms` : "--"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">
            P95 Latency
          </p>
          <p className="text-sm font-mono font-bold">
            {s.latency_p95_ms !== null ? `${s.latency_p95_ms}ms` : "--"}
          </p>
        </div>
        <div>
          <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">
            Errors / 24h
          </p>
          <p
            className={`text-sm font-mono font-bold ${
              s.error_count_24h > 0 ? "text-rose-500" : ""
            }`}
          >
            {s.error_count_24h}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">
            Last Check
          </p>
          <p className="text-sm font-mono font-bold">
            {s.last_checked
              ? new Date(s.last_checked).toLocaleTimeString()
              : "--:--:--"}
          </p>
        </div>
      </div>

      {s.last_error && (
        <div className="text-[9px] font-mono text-rose-500 truncate" title={s.last_error}>
          {s.last_error}
        </div>
      )}
    </div>
  );
}

export default function DataHealth() {
  const { data, error, isLoading } = useApi<Health>("/api/health");

  return (
    <div className="flex-1 p-8">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h2 className="text-2xl font-black tracking-tight text-[#e5e1e4]">
            DATA PIPELINE HEALTH
          </h2>
          <p className="text-xs text-[#e5e1e4]/50 font-mono">
            {data?.sources.length ?? 0} SOURCES
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="text-[#958da1] p-8 font-mono uppercase tracking-widest text-xs">
          Loading health data...
        </div>
      ) : error ? (
        <div className="text-rose-500 p-8 font-mono uppercase tracking-widest text-xs">
          API error: {error.message}
        </div>
      ) : !data || data.state === "no_data" ? (
        <div className="bg-[#1b1b1d] border border-dashed border-[#39393b] p-8 text-center">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#e5e1e4]/40 mb-2">
            No health checks recorded
          </p>
          <p className="text-[10px] font-mono text-[#e5e1e4]/30">
            Source-health rows are written by the ingestion runner.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
          {data.sources.map((s) => (
            <SourceCard key={s.source_name} s={s} />
          ))}
        </div>
      )}
    </div>
  );
}
