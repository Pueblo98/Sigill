'use client';
import React, { useState, useEffect } from 'react';

export default function ArbitrageScanner() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch('http://localhost:8000/api/arbitrage');
        const json = await res.json();
        setData(json);
      } catch (e) {
        console.error("Failed to fetch arbitrage data", e);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  return (
    <div className="flex-1 overflow-auto p-8 h-full">
      <div className="mb-8 flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-black uppercase italic text-[#e5e1e4]">CROSS-PLATFORM DISCREPANCIES</h2>
          <p className="text-[10px] font-mono text-[#e5e1e4]/40 uppercase tracking-widest mt-1">Automatic detection of risk-free yields across Kalshi & Polymarket</p>
        </div>
        <div className="flex gap-2">
          <button className="bg-[#1b1b1d] border border-[#201f21] px-4 py-2 text-[10px] font-mono hover:bg-[#39393b]">MIN_PROFIT: 2%</button>
          <button className="bg-[#7C3AED] text-white px-4 py-2 text-[10px] font-mono font-bold">EXECUTE_ALL_ARBS</button>
        </div>
      </div>

      <div className="bg-[#201f21] border border-[#1b1b1d]">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-[#1b1b1d] text-[10px] font-mono text-[#e5e1e4]/40 uppercase border-b border-[#201f21]">
              <th className="px-6 py-4 font-medium">Event / Matched Market</th>
              <th className="px-4 py-4 font-medium">Platform A Liquidity</th>
              <th className="px-4 py-4 font-medium">Platform B Liquidity</th>
              <th className="px-4 py-4 font-medium text-right">Implied Sum</th>
              <th className="px-4 py-4 font-medium text-right text-emerald-500">Net Arb %</th>
              <th className="px-6 py-4 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="text-[11px] font-mono divide-y divide-[#1b1b1d]">
            {loading ? (
               <tr><td colSpan={6} className="px-6 py-5 text-center text-[#958da1]">INITIALIZING LIVE FEEDS...</td></tr>
            ) : data.length === 0 ? (
               <tr><td colSpan={6} className="px-6 py-5 text-center text-[#958da1]">NO ARBITRAGE OPPORTUNITIES DETECTED</td></tr>
            ) : data.map((arb: any, idx) => (
              <tr key={idx} className="hover:bg-[#39393b] transition-colors">
                <td className="px-6 py-5">
                  <div className="font-bold text-[#e5e1e4] mb-1">{arb.event}</div>
                  <div className="flex gap-2 opacity-40 text-[9px]">{arb.kalshi_ticker} :: {arb.poly_ticker}</div>
                </td>
                <td className="px-4 py-5">
                  <div className="flex flex-col gap-1">
                      <span className="text-[9px] bg-emerald-900/30 text-emerald-400 px-1.5 py-0.5 font-bold self-start mb-1">KALSHI (YES)</span>
                      <div className="flex justify-between w-32 items-center">
                          <span className="text-[#958da1]">Bid:</span>
                          <span className="font-bold text-[#e5e1e4]">{arb.kalshi_bid.toFixed(1)}¢ <span className="text-[#958da1] text-[9px] font-normal font-mono ml-1">min ${arb.kalshi_min_size}</span></span>
                      </div>
                      <div className="flex justify-between w-32 items-center">
                          <span className="text-[#958da1]">Ask:</span>
                          <span className="font-bold text-[#e5e1e4]">{arb.kalshi_ask.toFixed(1)}¢ <span className="text-[#958da1] text-[9px] font-normal font-mono ml-1">min ${arb.kalshi_min_size}</span></span>  
                      </div>
                  </div>
                </td>
                <td className="px-4 py-5">
                  <div className="flex flex-col gap-1">
                      <span className="text-[9px] bg-blue-900/30 text-blue-400 px-1.5 py-0.5 font-bold self-start mb-1">POLYMARKET (NO)</span>
                      <div className="flex justify-between w-32 items-center">
                          <span className="text-[#958da1]">Bid:</span>
                          <span className="font-bold text-[#e5e1e4]">{arb.poly_bid.toFixed(1)}¢ <span className="text-[#958da1] text-[9px] font-normal font-mono ml-1">min ${arb.poly_min_size}</span></span>
                      </div>
                      <div className="flex justify-between w-32 items-center">
                          <span className="text-[#958da1]">Ask:</span>
                          <span className="font-bold text-[#e5e1e4]">{arb.poly_ask.toFixed(1)}¢ <span className="text-[#958da1] text-[9px] font-normal font-mono ml-1">min ${arb.poly_min_size}</span></span>
                      </div>
                  </div>
                </td>
                <td className="px-4 py-5 text-right font-bold text-[#e5e1e4]/40">{arb.implied_sum.toFixed(1)}¢</td>
                <td className="px-4 py-5 text-right">
                  <div className="text-emerald-500 font-bold">+{arb.net_arb.toFixed(1)}%</div>
                  <div className="text-[9px] text-[#e5e1e4]/40">After Fees</div>
                </td>
                <td className="px-6 py-5 text-right">
                  <button className="bg-[#7C3AED]/10 text-[#7C3AED] border border-[#7C3AED]/20 px-4 py-1.5 hover:bg-[#7C3AED] hover:text-[#ede0ff] transition-all font-bold">EXECUTE</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Visualizer Section */}
      <div className="mt-12 grid grid-cols-12 gap-6 pb-8">
          <div className="col-span-12 lg:col-span-8 bg-[#201f21] p-6 border border-[#1b1b1d]">
              <div className="flex justify-between items-center mb-6">
                  <h3 className="text-xs font-bold uppercase font-mono tracking-widest text-on-surface/60">Arb Opportunity Visualizer</h3>
                  <div className="flex gap-4">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 bg-emerald-500"></div>
                          <span className="text-[9px] font-mono">KALSHI_PX</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 bg-blue-500"></div>
                          <span className="text-[9px] font-mono">POLY_PX</span>
                        </div>
                  </div>
              </div>
              <div className="h-64 flex items-end gap-12 px-8">
                  {/* Chart Bar 1 */}
                  <div className="flex-1 flex flex-col items-center gap-2">
                      <div className="w-full flex gap-1">
                          <div className="flex-1 bg-emerald-500/80" style={{ height: "180px" }}></div>
                          <div className="flex-1 bg-blue-500/80" style={{ height: "120px" }}></div>
                      </div>
                      <span className="text-[9px] font-mono text-on-surface-variant uppercase">FED_DEC</span>
                  </div>
                  {/* Chart Bar 2 */}
                  <div className="flex-1 flex flex-col items-center gap-2">
                      <div className="w-full flex gap-1">
                          <div className="flex-1 bg-emerald-500/80" style={{ height: "220px" }}></div>
                          <div className="flex-1 bg-blue-500/80" style={{ height: "140px" }}></div>
                      </div>
                      <span className="text-[9px] font-mono text-on-surface-variant uppercase">BTC_100K</span>
                  </div>
              </div>
          </div>

          <div className="col-span-12 lg:col-span-4 bg-[#201f21] p-6 border border-[#1b1b1d] flex flex-col gap-6">
              <h3 className="text-xs font-bold uppercase font-mono tracking-widest text-on-surface/60">Execution Stats</h3>
              <div className="space-y-4">
                  <div className="bg-[#0e0e10] p-4">
                      <p className="text-[9px] font-mono text-on-surface-variant mb-1 uppercase">Avg Arb Yield</p>
                      <p className="text-2xl font-black font-mono text-emerald-500">3.82%</p>
                  </div>
                  <div className="bg-[#0e0e10] p-4">
                      <p className="text-[9px] font-mono text-on-surface-variant mb-1 uppercase">Daily Arb Cap</p>
                      <p className="text-2xl font-black font-mono text-on-surface">$12,400</p>
                  </div>
              </div>
          </div>
      </div>
    </div>
  );
}
