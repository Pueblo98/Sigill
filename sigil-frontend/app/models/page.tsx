import React from 'react';

export default function Models() {
  return (
    <div className="p-6">
      {/* Header Section */}
      <header className="flex justify-between items-center mb-8 pb-4 border-b border-[#4a4455]/10">
        <div>
          <h2 className="text-xs font-medium uppercase tracking-[0.2em] text-[#958da1] mb-1">Model Performance Analysis</h2>
          <h1 className="text-2xl font-black tracking-tight text-[#e5e1e4]">SIGIL_MODEL_ALPHA_v4</h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-[10px] uppercase font-bold text-[#958da1]/50">Last Retrain</p>
            <p className="font-mono text-xs text-[#e5e1e4]">2023-10-24 04:12 UTC</p>
          </div>
          <div className="h-8 w-px bg-[#4a4455]/20"></div>
          <button className="flex items-center gap-2 bg-[#201f21] px-4 py-2 hover:bg-[#39393b] transition-colors border border-[#4a4455]/10 text-[#e5e1e4]">
            <span className="material-symbols-outlined text-sm">filter_list</span>
            <span className="text-[10px] font-bold uppercase tracking-wider">Verticals: ALL</span>
          </button>
        </div>
      </header>

      {/* Top Row: KPI Tiles */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-[#201f21] p-6 border-l-2 border-[#7C3AED]">
          <div className="flex justify-between items-start mb-2">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#958da1]">Brier Score</h3>
            <span className="material-symbols-outlined text-[#7C3AED] text-lg">troubleshoot</span>
          </div>
          <p className="font-mono text-3xl font-bold text-[#e5e1e4]">0.162</p>
          <div className="mt-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <p className="text-[9px] font-medium text-emerald-500 uppercase">Within optimal range (-0.004 Δ)</p>
          </div>
        </div>
        <div className="bg-[#201f21] p-6 border-l-2 border-[#4a4455]/40">
          <div className="flex justify-between items-start mb-2">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#958da1]">Log Loss</h3>
            <span className="material-symbols-outlined text-[#958da1] text-lg">query_stats</span>
          </div>
          <p className="font-mono text-3xl font-bold text-[#e5e1e4]">0.412</p>
          <div className="mt-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#ffb784]"></span>
            <p className="text-[9px] font-medium text-[#ffb784] uppercase">Stable variance (0.1% drift)</p>
          </div>
        </div>
        <div className="bg-[#201f21] p-6 border-l-2 border-[#7C3AED]">
          <div className="flex justify-between items-start mb-2">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#958da1]">Calibration Error</h3>
            <span className="material-symbols-outlined text-[#7C3AED] text-lg">rule</span>
          </div>
          <p className="font-mono text-3xl font-bold text-[#e5e1e4]">0.012</p>
          <div className="mt-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <p className="text-[9px] font-medium text-emerald-500 uppercase">High Reliability (Rank: A1)</p>
          </div>
        </div>
      </div>

      {/* Center Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
        {/* Per-Vertical Performance Table */}
        <div className="lg:col-span-6 bg-[#201f21] overflow-hidden flex flex-col">
          <div className="p-4 border-b border-[#4a4455]/10 bg-[#2a2a2c]/30">
            <h3 className="text-xs font-bold uppercase tracking-widest text-[#e5e1e4]">Vertical Breakdown</h3>
          </div>
          <div className="flex-1 overflow-auto">
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-[#2a2a2c]/90 backdrop-blur z-10">
                <tr>
                  <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] tracking-tighter">Vertical</th>
                  <th className="px-2 py-3 text-[9px] font-black uppercase text-[#958da1] tracking-tighter text-right">Trades</th>
                  <th className="px-2 py-3 text-[9px] font-black uppercase text-[#958da1] tracking-tighter text-right">WR%</th>
                  <th className="px-4 py-3 text-[9px] font-black uppercase text-[#958da1] tracking-tighter text-right">Brier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#4a4455]/5">
                <tr className="hover:bg-[#39393b] transition-colors group">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 bg-emerald-500"></div>
                      <span className="text-[10px] font-bold uppercase text-[#e5e1e4]">Sports_NBA</span>
                    </div>
                  </td>
                  <td className="px-2 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">14,202</td>
                  <td className="px-2 py-3 text-right font-mono text-[10px] text-emerald-500">54.2%</td>
                  <td className="px-4 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">0.145</td>
                </tr>
                <tr className="hover:bg-[#39393b] transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 bg-emerald-500"></div>
                      <span className="text-[10px] font-bold uppercase text-[#e5e1e4]">Politics_US</span>
                    </div>
                  </td>
                  <td className="px-2 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">2,104</td>
                  <td className="px-2 py-3 text-right font-mono text-[10px] text-emerald-500">61.8%</td>
                  <td className="px-4 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">0.122</td>
                </tr>
                <tr className="hover:bg-[#39393b] transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 bg-[#ffb784]"></div>
                      <span className="text-[10px] font-bold uppercase text-[#e5e1e4]">Crypto_BTC</span>
                    </div>
                  </td>
                  <td className="px-2 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">45,901</td>
                  <td className="px-2 py-3 text-right font-mono text-[10px] text-[#ffb784]">49.1%</td>
                  <td className="px-4 py-3 text-right font-mono text-[10px] text-[#e5e1e4]">0.198</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Walk-Forward Performance Chart Placeholder */}
        <div className="lg:col-span-6 bg-[#201f21] p-6 border border-[#1b1b1d] flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <div>
                <h3 className="text-xs font-bold uppercase tracking-widest text-[#e5e1e4]">Walk-Forward P&L</h3>
                <p className="text-[10px] text-[#958da1]/60">Monthly Realized Returns</p>
                </div>
            </div>
            <div className="h-48 w-full flex items-end gap-1 px-4 relative bg-[#0e0e10]/50 border-l border-b border-[#4a4455]/30 p-2">
                <div className="flex-1 bg-[#d2bbff]/20 h-[40%] hover:bg-[#d2bbff]/40 transition-colors"></div>
                <div className="flex-1 bg-[#d2bbff]/20 h-[65%] hover:bg-[#d2bbff]/40 transition-colors"></div>
                <div className="flex-1 bg-[#d2bbff]/20 h-[55%] hover:bg-[#d2bbff]/40 transition-colors"></div>
                <div className="flex-1 bg-[#d2bbff]/20 h-[80%] hover:bg-[#d2bbff]/40 transition-colors"></div>
                <div className="flex-1 bg-[#d2bbff]/20 h-[92%] hover:bg-[#d2bbff]/40 transition-colors"></div>
                <div className="flex-1 bg-[#ffb4ab]/20 h-[15%] hover:bg-[#ffb4ab]/40 transition-colors"></div>
                <div className="flex-1 bg-[#d2bbff]/20 h-[45%] hover:bg-[#d2bbff]/40 transition-colors"></div>
                <div className="flex-1 bg-[#d2bbff]/20 h-[60%] hover:bg-[#d2bbff]/40 transition-colors"></div>
            </div>
        </div>
      </div>
    </div>
  );
}
