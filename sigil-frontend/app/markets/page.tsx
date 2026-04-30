'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

export default function MarketBrowser() {
  const [markets, setMarkets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const filteredMarkets = markets.filter(m => {
    // Exact match if category is selected
    if (selectedCategory && m.taxonomy_l1 !== selectedCategory.toLowerCase()) {
      return false;
    }
    // Case-insensitive substring match for search
    if (searchQuery && !m.title.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  useEffect(() => {
    async function fetchMarkets() {
      try {
        const res = await fetch('http://localhost:8000/api/markets');
        const json = await res.json();
        setMarkets(json);
      } catch (e) {
        console.error("Failed to fetch markets", e);
      } finally {
        setLoading(false);
      }
    }
    fetchMarkets();
  }, []);
  return (
    <div className="flex flex-1 h-full overflow-hidden">
      {/* MARKET FILTERS SIDEBAR */}
      <aside className="w-72 bg-[#1b1b1d] border-r border-[#201f21] flex flex-col overflow-y-auto">
        <div className="p-6 space-y-8">
          {/* Categories */}
          <div>
            <h3 className="text-[10px] font-bold font-mono text-[#7C3AED] uppercase tracking-[0.2em] mb-4">Categories</h3>
            <div className="space-y-1">
              {[
                { label: 'Sports', icon: 'sports_basketball', color: 'text-blue-400' },
                { label: 'Politics', icon: 'gavel', color: 'text-red-400' },
                { label: 'Economics', icon: 'trending_up', color: 'text-emerald-400' },
                { label: 'Weather', icon: 'wb_sunny', color: 'text-yellow-400' },
                { label: 'Crypto', icon: 'currency_bitcoin', color: 'text-purple-400' },
                { label: 'Entertainment', icon: 'movie', color: 'text-pink-400' }
              ].map((cat) => (
                <button 
                  key={cat.label} 
                  onClick={() => setSelectedCategory(selectedCategory === cat.label ? null : cat.label)}
                  className={`w-full flex items-center justify-between p-2 hover:bg-[#39393b] transition-colors group ${selectedCategory === cat.label ? 'bg-[#39393b] border-l-2 border-[#7C3AED]' : ''}`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`material-symbols-outlined text-sm ${cat.color}`}>{cat.icon}</span>
                    <span className="text-xs">{cat.label}</span>
                  </div>
                  <span className="material-symbols-outlined text-xs text-[#958da1]">
                    {selectedCategory === cat.label ? 'check' : 'expand_more'}
                  </span>
                </button>
              ))}
            </div>
          </div>
          
          {/* Exchange Filters */}
          <div>
            <h3 className="text-[10px] font-bold font-mono text-[#7C3AED] uppercase tracking-[0.2em] mb-4">Exchanges</h3>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer group">
                <input type="checkbox" defaultChecked className="w-4 h-4 bg-[#0e0e10] border-[#39393b] text-[#7C3AED] focus:ring-0" />
                <span className="text-xs group-hover:text-[#d2bbff] transition-colors">Kalshi</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer group">
                <input type="checkbox" defaultChecked className="w-4 h-4 bg-[#0e0e10] border-[#39393b] text-[#7C3AED] focus:ring-0" />
                <span className="text-xs group-hover:text-[#d2bbff] transition-colors">Polymarket</span>
              </label>
            </div>
          </div>

          {/* Edge Slider */}
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-[10px] font-bold font-mono text-[#7C3AED] uppercase tracking-[0.2em]">Minimum Edge</h3>
              <span className="font-mono text-[10px] text-[#d2bbff]">12.4¢</span>
            </div>
            <input className="w-full h-1 bg-[#0e0e10] appearance-none cursor-pointer accent-[#7C3AED]" max="20" min="0" step="0.1" type="range" defaultValue="12.4" />
            <div className="flex justify-between mt-2 font-mono text-[8px] text-[#958da1]/40">
              <span>0¢</span>
              <span>20¢</span>
            </div>
          </div>
        </div>
      </aside>

      {/* MARKET GRID AREA */}
      <section className="flex-1 overflow-y-auto bg-[#0e0e10] p-8">
        {/* Sorting & Controls */}
        <div className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-3xl font-black tracking-tight mb-2 uppercase italic text-[#e5e1e4]">MARKET BROWSER</h1>
            <p className="text-[10px] font-mono text-[#958da1] tracking-wider uppercase">Scanning {filteredMarkets.length} active live contracts</p>
          </div>
          
          {/* SEARCH BAR */}
          <div className="flex-1 max-w-md mx-8">
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#958da1]">search</span>
              <input 
                type="text" 
                placeholder="Search markets..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#1b1b1d] border border-[#201f21] p-3 pl-10 text-sm font-mono focus:outline-none focus:border-[#7C3AED]/50 text-[#e5e1e4] placeholder-[#958da1]/50" 
              />
            </div>
          </div>
          <div className="flex gap-4">
            <div className="flex items-center bg-[#1b1b1d] border border-[#201f21]">
              <span className="px-3 text-[9px] font-mono text-[#958da1] border-r border-[#201f21]">SORT BY</span>
              <select className="bg-transparent border-none text-[10px] font-mono py-2 px-4 focus:ring-0 cursor-pointer text-[#e5e1e4]">
                <option>EXPECTED EDGE</option>
                <option>RESOLUTION DATE</option>
                <option>24H VOLUME</option>
              </select>
            </div>
            <button className="bg-[#1b1b1d] border border-[#201f21] p-2 hover:bg-[#39393b] transition-colors">
              <span className="material-symbols-outlined text-sm">filter_list</span>
            </button>
          </div>
        </div>

        {/* Bento Grid Markets */}
        <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-6">
          {loading ? (
             <div className="text-[#958da1] p-8 font-mono uppercase tracking-widest text-xs col-span-full">INITIALIZING SIGIL DATABASE...</div>
          ) : filteredMarkets.length === 0 ? (
             <div className="text-[#958da1] p-8 font-mono uppercase tracking-widest text-xs col-span-full">NO MARKETS FOUND MATCHING "{searchQuery}" OR SELECTED CATEGORIES</div>
          ) : filteredMarkets.map((m: any) => (
            <Link key={m.external_id || m.id} href={`/trade-detail/${m.external_id}`} className="group relative bg-[#201f21] border border-[#1b1b1d] hover:border-[#7C3AED]/40 hover:shadow-[0_0_30px_rgba(124,58,237,0.1)] transition-all duration-300 p-6 flex flex-col h-[340px] block cursor-pointer">
              <div className="flex justify-between items-start mb-4">
                <span className="bg-[#39393b] text-[#958da1] text-[9px] font-bold px-2 py-0.5 font-mono tracking-widest uppercase">{m.market_type || 'STANDARD'}</span>
                <span className={`text-[9px] font-mono font-bold px-2 py-0.5 uppercase ${m.platform === 'kalshi' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-blue-900/30 text-blue-400'}`}>{m.platform}</span>
              </div>
              <h2 className="text-lg font-bold leading-tight mb-6 group-hover:text-[#d2bbff] transition-colors line-clamp-2 text-[#e5e1e4]">{m.title}</h2>
              
              <div className="flex-1 flex flex-col justify-center items-center text-[#958da1]/40 border border-dashed border-[#1b1b1d] mb-4">
                 <span className="material-symbols-outlined text-4xl mb-2">query_stats</span>
                 <span className="text-[9px] font-mono uppercase tracking-widest">Model evaluation pending</span>
              </div>

              <div className="mt-auto pt-4 border-t border-[#1b1b1d] flex justify-between items-center text-[10px] font-mono">
                <div className="flex items-center gap-2 text-[#958da1]">
                  <span className="material-symbols-outlined text-xs">schedule</span>
                  <span>{m.resolution_date ? new Date(m.resolution_date).toLocaleDateString() : 'N/A'}</span>
                </div>
                <div className="flex items-center gap-2 text-[8px] text-[#958da1]/30 uppercase">
                  ID: {m.external_id?.substring(0,10)}...
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
