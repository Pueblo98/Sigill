import React from 'react';

export default function DataHealth() {
  return (
    <div className="flex-1 p-8">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h2 className="text-2xl font-black tracking-tight text-[#e5e1e4]">DATA PIPELINE HEALTH</h2>
          <p className="text-xs text-[#e5e1e4]/50 font-mono">LATENCY_THRESHOLD: 250MS | TOTAL_SOURCES: 12</p>
        </div>
        <div className="flex gap-2">
          <button className="px-4 py-2 bg-[#201f21] border border-[#4a4455]/20 text-[10px] font-bold hover:bg-[#39393b] transition-colors">REBOOT ALL</button>
          <button className="px-4 py-2 bg-[#7c3aed] text-[#ede0ff] text-[10px] font-bold hover:opacity-90 transition-opacity">EXPORT LOGS</button>
        </div>
      </div>

      {/* Grid of Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
        {/* ESPN API Card */}
        <div className="bg-[#201f21] p-4 flex flex-col gap-4 border border-transparent hover:border-[#d2bbff]/20 transition-all group">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#d2bbff]/80 font-mono">SPORTS_VERT</p>
              <h3 className="text-lg font-black tracking-tight">ESPN API</h3>
            </div>
            <div className="flex items-center gap-1.5 bg-emerald-500/10 px-2 py-0.5">
              <span className="w-1.5 h-1.5 bg-emerald-500"></span>
              <span className="text-[9px] font-bold text-emerald-500 uppercase">Healthy</span>
            </div>
          </div>
          <div className="h-10 flex items-end gap-0.5">
            <div className="flex-1 bg-emerald-500/20 h-4"></div>
            <div className="flex-1 bg-emerald-500/20 h-6"></div>
            <div className="flex-1 bg-emerald-500/20 h-5"></div>
            <div className="flex-1 bg-emerald-500/20 h-7"></div>
            <div className="flex-1 bg-emerald-500/20 h-4"></div>
            <div className="flex-1 bg-emerald-500/20 h-3"></div>
            <div className="flex-1 bg-emerald-500/20 h-8"></div>
            <div className="flex-1 bg-emerald-500/40 h-10 border-t border-emerald-500"></div>
          </div>
          <div className="grid grid-cols-2 gap-4 mt-auto">
            <div>
              <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">Records Today</p>
              <p className="text-sm font-mono font-bold">142,891</p>
            </div>
            <div className="text-right">
              <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">Last Fetch</p>
              <p className="text-sm font-mono font-bold">14:02:11</p>
            </div>
          </div>
        </div>

        {/* The Odds API Card */}
        <div className="bg-[#201f21] p-4 flex flex-col gap-4 border border-transparent hover:border-[#d2bbff]/20 transition-all group">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#d2bbff]/80 font-mono">FINANCE_VERT</p>
              <h3 className="text-lg font-black tracking-tight">The Odds API</h3>
            </div>
            <div className="flex items-center gap-1.5 bg-yellow-500/10 px-2 py-0.5">
              <span className="w-1.5 h-1.5 bg-yellow-500"></span>
              <span className="text-[9px] font-bold text-yellow-500 uppercase">Degraded</span>
            </div>
          </div>
          <div className="h-10 flex items-end gap-0.5">
            <div className="flex-1 bg-yellow-500/20 h-4"></div>
            <div className="flex-1 bg-yellow-500/20 h-9"></div>
            <div className="flex-1 bg-rose-500/40 h-10 border-t border-rose-500"></div>
            <div className="flex-1 bg-yellow-500/20 h-7"></div>
            <div className="flex-1 bg-yellow-500/20 h-8"></div>
            <div className="flex-1 bg-yellow-500/20 h-6"></div>
            <div className="flex-1 bg-yellow-500/20 h-5"></div>
            <div className="flex-1 bg-yellow-500/40 h-6 border-t border-yellow-500"></div>
          </div>
          <div className="grid grid-cols-2 gap-4 mt-auto">
            <div>
              <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">Records Today</p>
              <p className="text-sm font-mono font-bold">884,102</p>
            </div>
            <div className="text-right">
              <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">Last Fetch</p>
              <p className="text-sm font-mono font-bold">13:58:44</p>
            </div>
          </div>
        </div>

        {/* Metaculus Card */}
        <div className="bg-[#201f21] p-4 flex flex-col gap-4 border border-transparent hover:border-[#d2bbff]/20 transition-all group">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#d2bbff]/80 font-mono">PRED_VERT</p>
              <h3 className="text-lg font-black tracking-tight">Metaculus</h3>
            </div>
            <div className="flex items-center gap-1.5 bg-rose-500/10 px-2 py-0.5">
              <span className="w-1.5 h-1.5 bg-rose-500"></span>
              <span className="text-[9px] font-bold text-rose-500 uppercase">Failing</span>
            </div>
          </div>
          <div className="h-10 flex items-end gap-0.5">
            <div className="flex-1 bg-rose-500/20 h-10 border-t border-rose-500"></div>
            <div className="flex-1 bg-rose-500/20 h-10 border-t border-rose-500"></div>
            <div className="flex-1 bg-rose-500/20 h-10 border-t border-rose-500"></div>
            <div className="flex-1 bg-rose-500/20 h-10 border-t border-rose-500"></div>
            <div className="flex-1 bg-rose-500/20 h-10 border-t border-rose-500"></div>
            <div className="flex-1 bg-rose-500/20 h-10 border-t border-rose-500"></div>
            <div className="flex-1 bg-rose-500/20 h-10 border-t border-rose-500"></div>
            <div className="flex-1 bg-rose-500/40 h-10 border-t border-rose-500"></div>
          </div>
          <div className="grid grid-cols-2 gap-4 mt-auto">
            <div>
              <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">Records Today</p>
              <p className="text-sm font-mono font-bold text-rose-500">0</p>
            </div>
            <div className="text-right">
              <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">Last Fetch</p>
              <p className="text-sm font-mono font-bold text-rose-500">--:--:--</p>
            </div>
          </div>
        </div>

        {/* Polymarket Card */}
        <div className="bg-[#201f21] p-4 flex flex-col gap-4 border border-transparent hover:border-[#d2bbff]/20 transition-all group">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#d2bbff]/80 font-mono">PRED_VERT</p>
              <h3 className="text-lg font-black tracking-tight">Polymarket</h3>
            </div>
            <div className="flex items-center gap-1.5 bg-emerald-500/10 px-2 py-0.5">
              <span className="w-1.5 h-1.5 bg-emerald-500"></span>
              <span className="text-[9px] font-bold text-emerald-500 uppercase">Healthy</span>
            </div>
          </div>
          <div className="h-10 flex items-end gap-0.5">
            <div className="flex-1 bg-emerald-500/20 h-6"></div>
            <div className="flex-1 bg-emerald-500/20 h-5"></div>
            <div className="flex-1 bg-emerald-500/20 h-7"></div>
            <div className="flex-1 bg-emerald-500/20 h-6"></div>
            <div className="flex-1 bg-emerald-500/20 h-8"></div>
            <div className="flex-1 bg-emerald-500/20 h-6"></div>
            <div className="flex-1 bg-emerald-500/20 h-7"></div>
            <div className="flex-1 bg-emerald-500/40 h-6 border-t border-emerald-500"></div>
          </div>
          <div className="grid grid-cols-2 gap-4 mt-auto">
            <div>
              <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">Records Today</p>
              <p className="text-sm font-mono font-bold">459,211</p>
            </div>
            <div className="text-right">
              <p className="text-[9px] font-mono text-[#e5e1e4]/40 uppercase">Last Fetch</p>
              <p className="text-sm font-mono font-bold">14:01:30</p>
            </div>
          </div>
        </div>
      </div>

      {/* Anomaly Alerts Section */}
      <div className="bg-[#1b1b1d] p-6 border-t-2 border-[#7C3AED]">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-sm font-black tracking-widest uppercase flex items-center gap-2">
            <span className="material-symbols-outlined text-rose-500">warning</span>
            Anomaly Alerts
          </h3>
          <div className="flex gap-4">
            <span className="text-[10px] font-mono text-[#e5e1e4]/40">3 TOTAL FLAG(S)</span>
          </div>
        </div>
        <div className="space-y-2">
          {/* Alert 1 */}
          <div className="bg-[#201f21] flex items-center justify-between p-3 border-l-2 border-rose-500 hover:bg-[#39393b] transition-colors">
            <div className="flex items-center gap-6">
              <div className="bg-rose-500/10 px-2 py-1">
                <span className="text-[10px] font-mono font-bold text-rose-500">&gt;3σ OUTLIER</span>
              </div>
              <div>
                <p className="text-xs font-bold">ETH/BTC Spread Anomaly</p>
                <p className="text-[10px] font-mono text-[#e5e1e4]/40">Source: CoinGecko | Value: 0.0842 (Expected: 0.0410)</p>
              </div>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-1 bg-rose-500/20 text-rose-500 text-[10px] font-bold uppercase hover:bg-rose-500 hover:text-white transition-colors">Investigate</button>
              <button className="px-3 py-1 text-[#e5e1e4]/40 text-[10px] font-bold uppercase hover:text-[#e5e1e4] transition-colors">Dismiss</button>
            </div>
          </div>
          {/* Alert 2 */}
          <div className="bg-[#201f21] flex items-center justify-between p-3 border-l-2 border-yellow-500 hover:bg-[#39393b] transition-colors">
            <div className="flex items-center gap-6">
              <div className="bg-yellow-500/10 px-2 py-1">
                <span className="text-[10px] font-mono font-bold text-yellow-500">CROSS_PLATFORM</span>
              </div>
              <div>
                <p className="text-xs font-bold">Unmatched Event ID: NFL_2024_W4_KC_LAC</p>
                <p className="text-[10px] font-mono text-[#e5e1e4]/40">ESPN vs The Odds API | Mapping failure detected.</p>
              </div>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-1 bg-yellow-500/20 text-yellow-500 text-[10px] font-bold uppercase hover:bg-yellow-500 hover:text-black transition-colors">Resolve</button>
              <button className="px-3 py-1 text-[#e5e1e4]/40 text-[10px] font-bold uppercase hover:text-[#e5e1e4] transition-colors">Dismiss</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
