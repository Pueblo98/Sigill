"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useApi } from "@/lib/api/client";
import type { ApiMarket } from "@/lib/types/api";

export default function MarketBrowser() {
  const { data, error, isLoading } = useApi<ApiMarket[]>("/api/markets");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [enabledPlatforms, setEnabledPlatforms] = useState({
    kalshi: true,
    polymarket: true,
  });

  const markets = data ?? [];

  const filteredMarkets = useMemo(() => {
    return markets.filter((m) => {
      if (selectedCategory && m.taxonomy_l1?.toLowerCase() !== selectedCategory.toLowerCase()) {
        return false;
      }
      if (searchQuery && !m.title.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false;
      }
      const platformEnabled =
        (m.platform === "kalshi" && enabledPlatforms.kalshi) ||
        (m.platform === "polymarket" && enabledPlatforms.polymarket) ||
        (m.platform !== "kalshi" && m.platform !== "polymarket");
      if (!platformEnabled) return false;
      return true;
    });
  }, [markets, selectedCategory, searchQuery, enabledPlatforms]);

  return (
    <div className="flex flex-1 h-full overflow-hidden">
      {/* MARKET FILTERS SIDEBAR */}
      <aside className="w-72 bg-[#1b1b1d] border-r border-[#201f21] flex flex-col overflow-y-auto">
        <div className="p-6 space-y-8">
          {/* Categories */}
          <div>
            <h3 className="text-[10px] font-bold font-mono text-[#7C3AED] uppercase tracking-[0.2em] mb-4">
              Categories
            </h3>
            <div className="space-y-1">
              {[
                { label: "Sports", color: "text-blue-400" },
                { label: "Politics", color: "text-red-400" },
                { label: "Economics", color: "text-emerald-400" },
                { label: "Weather", color: "text-yellow-400" },
                { label: "Crypto", color: "text-purple-400" },
                { label: "Entertainment", color: "text-pink-400" },
              ].map((cat) => (
                <button
                  key={cat.label}
                  onClick={() =>
                    setSelectedCategory(
                      selectedCategory === cat.label ? null : cat.label
                    )
                  }
                  className={`w-full flex items-center justify-between p-2 hover:bg-[#39393b] transition-colors ${
                    selectedCategory === cat.label
                      ? "bg-[#39393b] border-l-2 border-[#7C3AED]"
                      : ""
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`text-xs font-bold ${cat.color}`}>•</span>
                    <span className="text-xs">{cat.label}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Exchange Filters */}
          <div>
            <h3 className="text-[10px] font-bold font-mono text-[#7C3AED] uppercase tracking-[0.2em] mb-4">
              Exchanges
            </h3>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={enabledPlatforms.kalshi}
                  onChange={(e) =>
                    setEnabledPlatforms({
                      ...enabledPlatforms,
                      kalshi: e.target.checked,
                    })
                  }
                  className="w-4 h-4 bg-[#0e0e10] border-[#39393b] text-[#7C3AED] focus:ring-0"
                />
                <span className="text-xs">Kalshi</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={enabledPlatforms.polymarket}
                  onChange={(e) =>
                    setEnabledPlatforms({
                      ...enabledPlatforms,
                      polymarket: e.target.checked,
                    })
                  }
                  className="w-4 h-4 bg-[#0e0e10] border-[#39393b] text-[#7C3AED] focus:ring-0"
                />
                <span className="text-xs">Polymarket</span>
              </label>
            </div>
          </div>
        </div>
      </aside>

      {/* MARKET GRID AREA */}
      <section className="flex-1 overflow-y-auto bg-[#0e0e10] p-8">
        <div className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-3xl font-black tracking-tight mb-2 uppercase italic text-[#e5e1e4]">
              MARKET BROWSER
            </h1>
            <p className="text-[10px] font-mono text-[#958da1] tracking-wider uppercase">
              {filteredMarkets.length} live contracts
            </p>
          </div>

          <div className="flex-1 max-w-md mx-8">
            <input
              type="text"
              placeholder="Search markets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#1b1b1d] border border-[#201f21] p-3 text-sm font-mono focus:outline-none focus:border-[#7C3AED]/50 text-[#e5e1e4] placeholder-[#958da1]/50"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-6">
          {isLoading ? (
            <div className="text-[#958da1] p-8 font-mono uppercase tracking-widest text-xs col-span-full">
              Loading markets...
            </div>
          ) : error ? (
            <div className="text-rose-500 p-8 font-mono uppercase tracking-widest text-xs col-span-full">
              API error: {error.message}
            </div>
          ) : filteredMarkets.length === 0 ? (
            <div className="text-[#958da1] p-8 font-mono uppercase tracking-widest text-xs col-span-full">
              No markets match your filters.
            </div>
          ) : (
            filteredMarkets.map((m) => (
              <Link
                key={m.id}
                href={`/trade-detail/${encodeURIComponent(m.external_id)}`}
                className="group relative bg-[#201f21] border border-[#1b1b1d] hover:border-[#7C3AED]/40 hover:shadow-[0_0_30px_rgba(124,58,237,0.1)] transition-all duration-300 p-6 flex flex-col h-[340px] cursor-pointer"
              >
                <div className="flex justify-between items-start mb-4">
                  <span className="bg-[#39393b] text-[#958da1] text-[9px] font-bold px-2 py-0.5 font-mono tracking-widest uppercase">
                    {m.market_type || "STANDARD"}
                  </span>
                  <span
                    className={`text-[9px] font-mono font-bold px-2 py-0.5 uppercase ${
                      m.platform === "kalshi"
                        ? "bg-emerald-900/30 text-emerald-400"
                        : "bg-blue-900/30 text-blue-400"
                    }`}
                  >
                    {m.platform}
                  </span>
                </div>
                <h2 className="text-lg font-bold leading-tight mb-6 group-hover:text-[#d2bbff] transition-colors line-clamp-3 text-[#e5e1e4]">
                  {m.title}
                </h2>

                <div className="mt-auto pt-4 border-t border-[#1b1b1d] flex justify-between items-center text-[10px] font-mono">
                  <div className="text-[#958da1]">
                    {m.resolution_date
                      ? new Date(m.resolution_date).toLocaleDateString()
                      : "Open-ended"}
                  </div>
                  <div className="text-[8px] text-[#958da1]/30 uppercase">
                    {m.external_id?.substring(0, 10)}…
                  </div>
                </div>
              </Link>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
