'use client';

import React from 'react';
import Link from 'next/link';

export default function MarketBrowser() {
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
                <button key={cat.label} className="w-full flex items-center justify-between p-2 hover:bg-[#39393b] transition-colors group">
                  <div className="flex items-center gap-3">
                    <span className={`material-symbols-outlined text-sm ${cat.color}`}>{cat.icon}</span>
                    <span className="text-xs">{cat.label}</span>
                  </div>
                  <span className="material-symbols-outlined text-xs text-[#958da1]">expand_more</span>
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
            <p className="text-[10px] font-mono text-[#958da1] tracking-wider uppercase">Scanning 1,402 active contracts (DEMO_MODE)</p>
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
          {/* High Edge Card Template */}
          <Link href="/trade-detail" className="group relative bg-[#201f21] border border-[#7C3AED]/40 shadow-[0_0_20px_rgba(124,58,237,0.1)] hover:shadow-[0_0_30px_rgba(124,58,237,0.25)] transition-all duration-300 p-6 flex flex-col h-[340px] block cursor-pointer">
            <div className="flex justify-between items-start mb-4">
              <span className="bg-[#7C3AED] text-[#ede0ff] text-[9px] font-bold px-2 py-0.5 font-mono tracking-widest uppercase">HIGH EDGE</span>
              <span className="bg-blue-900/30 text-blue-400 text-[9px] font-mono font-bold px-2 py-0.5">POLYMARKET</span>
            </div>
            <h2 className="text-lg font-bold leading-tight mb-6 group-hover:text-[#d2bbff] transition-colors line-clamp-2">Will the Federal Reserve cut rates by 25bps in December?</h2>
            
            <div className="flex-1 grid grid-cols-2 gap-8 items-center">
              <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-full h-full -rotate-90">
                  <circle cx="64" cy="64" fill="transparent" r="58" stroke="#131315" strokeWidth="8"></circle>
                  <circle cx="64" cy="64" fill="transparent" r="58" stroke="#7C3AED" strokeDasharray="364" strokeDashoffset="100" strokeWidth="8"></circle>
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="font-mono text-2xl font-black text-[#e5e1e4]">72%</span>
                  <span className="text-[8px] uppercase tracking-widest text-[#958da1] font-bold">Probability</span>
                </div>
              </div>
              
              <div className="space-y-4">
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-mono font-bold uppercase tracking-wider">
                    <span>Model Px</span>
                    <span className="text-[#7C3AED]">72.4¢</span>
                  </div>
                  <div className="h-2 bg-[#0e0e10] overflow-hidden"><div className="h-full bg-[#7C3AED]" style={{ width: '72%' }}></div></div>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-mono font-bold uppercase tracking-wider">
                    <span>Market Px</span>
                    <span className="text-[#e5e1e4]">58.0¢</span>
                  </div>
                  <div className="h-2 bg-[#0e0e10] overflow-hidden"><div className="h-full bg-[#39393b]" style={{ width: '58%' }}></div></div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-[#1b1b1d] flex justify-between items-center text-[10px] font-mono">
              <div className="flex items-center gap-2 text-[#958da1]">
                <span className="material-symbols-outlined text-xs">schedule</span>
                <span>12D 04H</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[#958da1] uppercase">EDGE</span>
                <span className="text-[#d2bbff] font-bold">+14.4¢</span>
              </div>
            </div>
          </Link>

          {/* Stable Edge Card */}
          <Link href="/trade-detail" className="group bg-[#201f21] border border-[#1b1b1d] hover:bg-[#2a2a2c] transition-all p-6 flex flex-col h-[340px] block cursor-pointer">
            <div className="flex justify-between items-start mb-4">
              <span className="bg-[#39393b] text-[#958da1] text-[9px] font-bold px-2 py-0.5 font-mono tracking-widest uppercase">STABLE EDGE</span>
              <span className="bg-emerald-900/30 text-emerald-400 text-[9px] font-mono font-bold px-2 py-0.5">KALSHI</span>
            </div>
            <h2 className="text-lg font-bold leading-tight mb-6 line-clamp-2 text-[#e5e1e4]">Will NYC record a daily high over 80°F before Nov 1?</h2>
            <div className="flex-1 grid grid-cols-2 gap-8 items-center">
               <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-full h-full -rotate-90">
                  <circle cx="64" cy="64" fill="transparent" r="58" stroke="#131315" strokeWidth="8"></circle>
                  <circle cx="64" cy="64" fill="transparent" r="58" stroke="#d2bbff" strokeDasharray="364" strokeDashoffset="280" strokeWidth="6"></circle>
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="font-mono text-2xl font-black text-[#e5e1e4]">23%</span>
                  <span className="text-[8px] uppercase tracking-widest text-[#958da1] font-bold">Probability</span>
                </div>
              </div>
              <div className="space-y-4 text-[#e5e1e4]">
                <div className="text-[9px] font-mono uppercase tracking-widest text-[#958da1]">Vol: $4.2k</div>
                <div className="text-[9px] font-mono uppercase tracking-widest text-[#958da1]">OI: 1.1k</div>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-[#1b1b1d] flex justify-between items-center text-[10px] font-mono">
               <div className="flex items-center gap-2 text-[#958da1]">
                <span className="material-symbols-outlined text-xs">schedule</span>
                <span>8H 12M</span>
              </div>
               <span className="text-[#d2bbff] font-bold">+2.1¢ EDGE</span>
            </div>
          </Link>

          {/* Politics Card */}
          <Link href="/trade-detail" className="group relative bg-[#201f21] border border-[#7C3AED]/40 shadow-[0_0_20px_rgba(124,58,237,0.1)] hover:shadow-[0_0_30px_rgba(124,58,237,0.25)] transition-all duration-300 p-6 flex flex-col h-[340px] block cursor-pointer">
            <div className="flex justify-between items-start mb-4">
              <span className="bg-[#7C3AED] text-[#ede0ff] text-[9px] font-bold px-2 py-0.5 font-mono tracking-widest uppercase">HIGH EDGE</span>
              <span className="bg-blue-900/30 text-blue-400 text-[9px] font-mono font-bold px-2 py-0.5">POLYMARKET</span>
            </div>
            <h2 className="text-lg font-bold leading-tight mb-6 group-hover:text-[#d2bbff] transition-colors line-clamp-2 text-[#e5e1e4]">Candidate X to win the 2024 Popular Vote?</h2>
            <div className="flex-1 grid grid-cols-2 gap-8 items-center">
              <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-full h-full -rotate-90">
                  <circle cx="64" cy="64" fill="transparent" r="58" stroke="#131315" strokeWidth="8"></circle>
                  <circle cx="64" cy="64" fill="transparent" r="58" stroke="#7C3AED" strokeDasharray="364" strokeDashoffset="180" strokeWidth="8"></circle>
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="font-mono text-2xl font-black text-[#e5e1e4]">51%</span>
                  <span className="text-[8px] uppercase tracking-widest text-[#958da1] font-bold">Probability</span>
                </div>
              </div>
              <div className="space-y-4">
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-mono font-bold uppercase tracking-wider">
                    <span>Model Px</span>
                    <span className="text-[#7C3AED]">51.2¢</span>
                  </div>
                  <div className="h-2 bg-[#0e0e10] overflow-hidden"><div className="h-full bg-[#7C3AED]" style={{ width: '51%' }}></div></div>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-mono font-bold uppercase tracking-wider text-[#e5e1e4]">
                    <span>Market Px</span>
                    <span>39.0¢</span>
                  </div>
                  <div className="h-2 bg-[#0e0e10] overflow-hidden"><div className="h-full bg-[#39393b]" style={{ width: '39%' }}></div></div>
                </div>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-[#1b1b1d] flex justify-between items-center text-[10px] font-mono">
              <div className="flex items-center gap-2 text-[#958da1]">
                <span className="material-symbols-outlined text-xs">schedule</span>
                <span>11D 20H</span>
              </div>
              <span className="text-[#d2bbff] font-bold">+12.2¢ EDGE</span>
            </div>
          </Link>
        </div>
      </section>
    </div>
  );
}
