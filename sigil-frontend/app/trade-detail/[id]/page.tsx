'use client';
import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';

export default function TradeDetail() {
  const { id } = useParams();
  const [market, setMarket] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchSpecificMarket() {
      try {
        const res = await fetch(`http://localhost:8000/api/markets/${id}`);
        if (!res.ok) throw new Error("Not Found");
        const json = await res.json();
        setMarket(json);
      } catch (e) {
        console.error("Failed to fetch specific market", e);
      } finally {
        setLoading(false);
      }
    }
    if (id) fetchSpecificMarket();
  }, [id]);

  if (loading) {
    return <div className="p-12 font-mono text-xs uppercase text-[#958da1] tracking-widest">Loading Sigil Engine Datapoints...</div>;
  }

  if (!market) {
    return (
      <div className="p-12">
        <h1 className="text-3xl font-black text-red-500 mb-4">404: TARGET LOST</h1>
        <p className="font-mono text-[#958da1] text-xs">The market ID was not found in the ingestion engine.</p>
        <Link href="/markets" className="mt-8 font-mono text-[10px] uppercase text-[#7C3AED] hover:text-[#d2bbff] underline inline-block">Return to Grid</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#0e0e10] p-8 text-[#e5e1e4] overflow-y-auto w-full">
      
      {/* HEADER SECTION */}
      <div className="mb-12 max-w-5xl">
        <div className="flex items-center gap-4 mb-4">
          <Link href="/markets" className="text-[#958da1] hover:text-[#e5e1e4] transition-colors material-symbols-outlined text-sm">
            arrow_back
          </Link>
          <span className={`text-[10px] font-mono font-bold px-3 py-1 uppercase tracking-widest ${market.platform === 'kalshi' ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-900' : 'bg-blue-900/30 text-blue-400 border border-blue-900'}`}>
            {market.platform} | {market.taxonomy_l1 || 'GENERAL'}
          </span>
          <span className="text-[10px] font-mono text-[#958da1] border border-[#201f21] px-2 py-1">
            EX-ID: {market.external_id}
          </span>
        </div>
        
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-black leading-none tracking-tight mb-8">
          {market.title}
        </h1>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pb-8 border-b border-[#201f21]">
          <div className="bg-[#1b1b1d] border border-[#201f21] p-4 flex flex-col items-center justify-center gap-1 group">
             <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-[#958da1] group-hover:text-[#7C3AED] transition-colors">Current Ask</span>
             <span className="text-3xl font-mono text-[#e5e1e4]">{market.ask ? (market.ask * 100).toFixed(1) + '¢' : '--'}</span>
          </div>
          <div className="bg-[#1b1b1d] border border-[#201f21] p-4 flex flex-col items-center justify-center gap-1 group">
             <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-[#958da1] group-hover:text-[#7C3AED] transition-colors">Current Bid</span>
             <span className="text-3xl font-mono text-[#e5e1e4]">{market.bid ? (market.bid * 100).toFixed(1) + '¢' : '--'}</span>
          </div>
          <div className="bg-[#1b1b1d] border border-[#201f21] p-4 flex flex-col items-center justify-center gap-1 group">
             <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-[#958da1] group-hover:text-[#7C3AED] transition-colors">Last Trade</span>
             <span className="text-3xl font-mono text-[#7C3AED]">{market.last_price ? (market.last_price * 100).toFixed(1) + '¢' : '--'}</span>
          </div>
          <div className="bg-[#1b1b1d] border border-[#201f21] p-4 flex flex-col items-center justify-center gap-1 group">
             <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-[#958da1] group-hover:text-[#7C3AED] transition-colors">24H Volume</span>
             <span className="text-3xl font-mono text-[#e5e1e4]">${(market.volume_24h || 0).toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* DYNAMIC METRICS SECTION (TEMPORARY STRUCTURAL VIEW) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 max-w-5xl flex-1">
        
        {/* ARBITRAGE SCANNER PLUG */}
        <div className="lg:col-span-2 bg-[#1b1b1d] border border-[#201f21] p-8 flex flex-col">
          <h2 className="text-[12px] font-mono font-bold text-[#7C3AED] uppercase tracking-[0.3em] mb-6">Cross-Venue Arbitrage Metrics</h2>
          
          <div className="flex-1 flex items-center justify-center text-center p-12 border border-dashed border-[#201f21]">
            <div>
              <span className="material-symbols-outlined text-5xl text-[#958da1]/30 mb-4 block">sync_problem</span>
              <p className="font-mono text-xs text-[#958da1] uppercase tracking-widest leading-relaxed">
                Advanced structural charts deferred to Phase 2.<br/> Currently reading raw db telemetry.
              </p>
            </div>
          </div>
        </div>

        {/* METADATA ATTACHMENTS */}
        <div className="bg-[#1b1b1d] border border-[#201f21] p-8 flex flex-col gap-8">
           <div>
             <h3 className="text-[10px] font-mono font-bold text-[#7C3AED] uppercase tracking-[0.2em] mb-4">Resolution Target</h3>
             <p className="font-mono text-sm text-[#e5e1e4] uppercase">{market.resolution_date ? new Date(market.resolution_date).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'}) : 'Open-Ended Engine'}</p>
           </div>
           
           <div>
             <h3 className="text-[10px] font-mono font-bold text-[#7C3AED] uppercase tracking-[0.2em] mb-4">Contract State</h3>
             <div className="flex items-center gap-2">
                 <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                 <p className="font-mono text-xs text-emerald-400 uppercase tracking-widest">Accepting Orders</p>
             </div>
           </div>
           
           <div>
             <h3 className="text-[10px] font-mono font-bold text-[#7C3AED] uppercase tracking-[0.2em] mb-4">Last Websocket Sync</h3>
             <p className="font-mono text-xs text-[#958da1] uppercase tracking-wider">{market.last_updated ? new Date(market.last_updated).toLocaleTimeString() : 'N/A'}</p>
           </div>
        </div>

      </div>
    </div>
  );
}
