import React from 'react';

export default function Dashboard() {
  return (
    <div className="p-4 grid grid-cols-12 gap-4 flex-1">
      {/* Portfolio Overview */}
      <section className="col-span-12 lg:col-span-5 bg-[#201f21] p-6 flex flex-col gap-6">
        <div className="flex justify-between items-end">
          <h3 className="text-xs font-medium uppercase tracking-wider text-[#e5e1e4]/60">Portfolio Overview</h3>
          <span className="text-[10px] font-mono text-[#e5e1e4]/30">LAST UPDATE: 14:02:11</span>
        </div>
        <div className="flex items-baseline gap-4">
          <span className="text-3xl font-black font-mono tracking-tighter">$124,500.00</span>
          <span className="text-xs font-mono text-emerald-500 bg-emerald-500/10 px-2 py-0.5">+14.2% ROI</span>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#1b1b1d] p-4">
            <p className="text-[10px] uppercase text-[#e5e1e4]/40 mb-1">Unrealized P&L</p>
            <p className="text-lg font-mono font-bold text-emerald-500">+$12,450.20</p>
          </div>
          <div className="bg-[#1b1b1d] p-4">
            <p className="text-[10px] uppercase text-[#e5e1e4]/40 mb-1">Today's Realized</p>
            <p className="text-lg font-mono font-bold text-emerald-500">+$2,410.50</p>
          </div>
        </div>
      </section>

      {/* Active Signals */}
      <section className="col-span-12 lg:col-span-7 bg-[#201f21] flex flex-col">
        <div className="p-6 border-b border-[#1b1b1d] flex justify-between items-center">
          <h3 className="text-xs font-medium uppercase tracking-wider text-[#e5e1e4]/60">Active Signals</h3>
          <span className="bg-[#d2bbff]/10 text-[#d2bbff] text-[9px] font-mono px-2 py-0.5">3 NEW</span>
        </div>
        <div className="flex-1 overflow-y-auto max-h-[400px]">
          <div className="p-4 border-b border-[#1b1b1d] flex items-center gap-4 hover:bg-[#39393b] transition-colors relative">
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-emerald-500"></div>
            <div className="w-16 h-16 flex-shrink-0 bg-[#1b1b1d] flex items-center justify-center text-[9px] font-black uppercase text-center text-[#e5e1e4]/40 leading-tight">
              SPORTS<br/>NFL
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="bg-[#353437] text-[9px] font-bold px-1.5 py-0.5">POLYMARKET</span>
                <span className="text-[10px] font-mono text-emerald-500">+11.2¢ EDGE</span>
              </div>
              <h4 className="text-xs font-bold truncate">Will Kansas City Chiefs win Super Bowl LVIII?</h4>
            </div>
            <div className="text-right">
              <p className="text-[9px] text-[#e5e1e4]/40 uppercase mb-1">Kelly Size</p>
              <p className="text-sm font-mono font-black text-[#e5e1e4]">4.2%</p>
            </div>
          </div>
        </div>
      </section>

      {/* Open Positions */}
      <section className="col-span-12 lg:col-span-8 bg-[#201f21] flex flex-col overflow-hidden">
        <div className="p-6 border-b border-[#1b1b1d] flex justify-between items-center">
          <h3 className="text-xs font-medium uppercase tracking-wider text-[#e5e1e4]/60">Open Positions</h3>
          <span className="text-[10px] font-mono text-[#e5e1e4]/40">8 ACTIVE TRADES</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#1b1b1d] text-[10px] font-mono uppercase text-[#e5e1e4]/40">
                <th className="px-6 py-3 font-medium">Market</th>
                <th className="px-2 py-3 font-medium">Side</th>
                <th className="px-2 py-3 font-medium text-right">Contracts</th>
                <th className="px-2 py-3 font-medium text-right">Avg Entry</th>
                <th className="px-2 py-3 font-medium text-right">Unrealized P&L</th>
              </tr>
            </thead>
            <tbody className="text-[11px] font-mono divide-y divide-[#1b1b1d]">
              <tr className="hover:bg-[#39393b]/50">
                <td className="px-6 py-4 font-bold">ETH ETF Approval Q1</td>
                <td className="px-2 py-4 text-emerald-500 font-bold">YES</td>
                <td className="px-2 py-4 text-right">1,250</td>
                <td className="px-2 py-4 text-right">64.2¢</td>
                <td className="px-2 py-4 text-right text-emerald-500">+$124.50</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Model Health */}
      <section className="col-span-12 lg:col-span-4 bg-[#201f21] p-6 flex flex-col gap-6">
        <h3 className="text-xs font-medium uppercase tracking-wider text-[#e5e1e4]/60">Model Health</h3>
        <div className="space-y-4">
          <div className="space-y-1">
            <div className="flex justify-between text-[9px] font-mono">
              <span>SPORTS (BRIER)</span>
              <span className="text-emerald-500">0.14</span>
            </div>
            <div className="h-1 bg-[#1b1b1d] relative">
              <div className="absolute left-0 top-0 bottom-0 bg-emerald-500 w-[70%]"></div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
