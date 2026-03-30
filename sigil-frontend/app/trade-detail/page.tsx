import React from 'react';

export default function TradeDetail() {
  return (
    <div className="flex h-full overflow-hidden w-full">
      {/* Left Panel (60%) */}
      <section className="w-full lg:w-[60%] border-r border-[#1b1b1d] flex flex-col overflow-y-auto no-scrollbar">
        {/* Market Header */}
        <div className="p-8 bg-[#0e0e10] border-b border-[#201f21]">
          <div className="flex justify-between items-start mb-4">
            <div className="flex flex-col gap-1">
              <span className="font-mono text-[10px] text-[#7C3AED] tracking-[0.2em] uppercase font-bold">Politics / US Federal</span>
              <h1 className="text-3xl font-black tracking-tight leading-tight max-w-2xl text-[#e5e1e4]">Will there be a government shutdown in Dec 2024?</h1>
            </div>
            <div className="flex flex-col items-end">
              <span className="font-mono text-2xl font-bold text-[#d2bbff]">42.8%</span>
              <span className="font-mono text-[10px] text-[#e5e1e4]/40 uppercase tracking-tighter">Market Probability</span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-8 mt-6">
            <div className="space-y-1">
              <p className="text-[10px] uppercase font-bold tracking-widest text-[#e5e1e4]/40">Exchange</p>
              <p className="text-sm font-semibold text-[#e5e1e4]">KALSHI / POLYMARKET AGG</p>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] uppercase font-bold tracking-widest text-[#e5e1e4]/40">Resolution Criteria</p>
              <p className="text-sm font-semibold text-[#e5e1e4]">Lapse in appropriations resulting in partial closure</p>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] uppercase font-bold tracking-widest text-[#e5e1e4]/40">Settlement Source</p>
              <p className="text-sm font-semibold text-[#e5e1e4]">Federal Register / GAO Reports</p>
            </div>
          </div>
        </div>

        {/* Price History Chart Container */}
        <div className="p-8 bg-[#0e0e10] flex-1 relative min-h-[400px]">
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-bold text-xs uppercase tracking-[0.15em] flex items-center gap-2 text-[#e5e1e4]">
              <span className="material-symbols-outlined text-[16px]">show_chart</span> Probability Time-Series
            </h3>
            <div className="flex gap-4 font-mono text-[10px] text-[#e5e1e4]">
              <div className="flex items-center gap-2">
                <span className="w-3 h-[2px] bg-[#d2bbff]"></span> Market Price
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-0 border-t border-dashed border-[#7C3AED]"></span> Model Forecast
              </div>
            </div>
          </div>
          
          {/* Mock Chart Canvas */}
          <div className="relative w-full h-64 bg-[#201f21]/30 border-l border-b border-[#4a4455]/20">
            <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
              <path d="M0 180 L50 160 L100 190 L150 140 L200 155 L250 110 L300 130 L350 100 L400 115 L450 90 L500 120 L550 80 L600 95 L650 70 L700 85 L750 45" fill="none" stroke="#d2bbff" strokeWidth="2" vectorEffect="non-scaling-stroke"></path>
              <path d="M0 160 L100 150 L200 145 L300 130 L400 120 L500 115 L600 110 L750 105" fill="none" stroke="#7C3AED" strokeDasharray="4 4" strokeWidth="1" vectorEffect="non-scaling-stroke"></path>
            </svg>
          </div>

          {/* Depth Chart Visualization */}
          <div className="mt-12">
            <h3 className="font-bold text-xs uppercase tracking-[0.15em] mb-4 flex items-center gap-2 text-[#e5e1e4]">
              <span className="material-symbols-outlined text-[16px]">bar_chart</span> Liquidity Depth
            </h3>
            <div className="grid grid-cols-2 gap-px bg-[#4a4455]/20 h-32 relative">
              <div className="bg-[#201f21]/20 flex items-end">
                <div className="w-full h-[60%] bg-emerald-500/10 border-t border-emerald-500/30"></div>
              </div>
              <div className="bg-[#201f21]/20 flex items-end">
                <div className="w-full h-[85%] bg-rose-500/10 border-t border-rose-500/30"></div>
              </div>
              <div className="absolute inset-0 flex items-center justify-between px-4 pointer-events-none">
                <span className="font-mono text-[10px] text-emerald-400">BIDS: $1.42M</span>
                <span className="font-mono text-[10px] text-rose-400">ASKS: $2.18M</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Right Panel (40%) */}
      <section className="hidden lg:flex w-[40%] bg-[#1b1b1d] flex-col overflow-y-auto no-scrollbar">
        {/* Model Breakdown Section */}
        <div className="p-8 border-b border-[#4a4455]/10">
          <div className="flex justify-between items-center mb-8">
            <h3 className="font-bold text-xs uppercase tracking-[0.15em] flex items-center gap-2 text-[#e5e1e4]">
              <span className="material-symbols-outlined text-[#7C3AED] text-[18px]">psychology</span> Model Breakdown
            </h3>
            <div className="px-2 py-1 bg-[#7C3AED]/10 border border-[#7C3AED]/20">
              <span className="font-mono text-[10px] text-[#7C3AED]">SIGMA-7 ENGINE</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-8">
            <div className="bg-[#201f21] p-4 border-l-2 border-[#d2bbff]">
              <p className="text-[10px] uppercase font-bold tracking-widest text-[#e5e1e4]/40 mb-1">Confidence</p>
              <p className="font-mono text-2xl font-bold text-[#e5e1e4]">88.4<span className="text-xs text-[#e5e1e4]/40 ml-1">%</span></p>
            </div>
            <div className="bg-[#201f21] p-4 border-l-2 border-emerald-500">
              <p className="text-[10px] uppercase font-bold tracking-widest text-[#e5e1e4]/40 mb-1">Ensemble</p>
              <p className="font-mono text-2xl font-bold text-[#e5e1e4]">HIGH</p>
            </div>
          </div>
          <div className="space-y-3">
            <p className="text-[10px] uppercase font-black tracking-widest text-[#e5e1e4]/60 mb-4">Top Feature Attribution</p>
            <div className="space-y-4">
              <div className="space-y-1">
                <div className="flex justify-between font-mono text-[10px] mb-1 text-[#e5e1e4]">
                  <span>POLLING_AVG_HOUSE</span>
                  <span>34.2%</span>
                </div>
                <div className="w-full h-1 bg-[#201f21]">
                  <div className="h-full bg-[#7C3AED]" style={{ width: '34.2%' }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Trade Execution Panel */}
        <div className="p-8 bg-[#201f21] flex-1">
          <h3 className="font-bold text-xs uppercase tracking-[0.15em] mb-6 text-[#e5e1e4]">Trade Execution</h3>
          <div className="flex mb-6 p-1 bg-[#0e0e10] border border-[#4a4455]/20">
            <button className="flex-1 py-2 font-black text-xs uppercase tracking-widest bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/50">YES</button>
            <button className="flex-1 py-2 font-black text-xs uppercase tracking-widest text-[#e5e1e4]/40 hover:text-[#e5e1e4] transition-colors">NO</button>
          </div>
          <div className="space-y-6">
            <div className="space-y-2">
              <label className="font-mono text-[10px] uppercase font-bold text-[#e5e1e4]/40">Quantity (Contracts)</label>
              <input className="w-full bg-[#0e0e10] border-none focus:ring-1 focus:ring-[#7C3AED] font-mono text-xl py-4 px-4 text-[#e5e1e4]" type="text" defaultValue="5,000" />
            </div>
            <div className="space-y-4 pt-4">
              <div className="flex justify-between items-center bg-[#7C3AED]/5 p-4 border border-[#7C3AED]/20">
                <div>
                  <p className="text-[10px] font-black text-[#7C3AED] uppercase tracking-widest">Expected Value</p>
                  <p className="font-mono text-sm text-[#7C3AED]">+$842.50</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] font-bold text-[#e5e1e4]/40 uppercase">Kelly Size</p>
                  <p className="font-mono text-sm text-[#e5e1e4]">8,420</p>
                </div>
              </div>
              <button className="w-full py-5 bg-[#7C3AED] text-[#ede0ff] font-black text-sm uppercase tracking-[0.2em] shadow-lg shadow-[#7C3AED]/20 active:translate-y-px transition-all">
                  Execute Order
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
