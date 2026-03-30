import React from 'react';

export default function ExecutionLog() {
  return (
    <div className="flex-1 overflow-auto p-8">
      <div className="mb-8">
        <h2 className="text-3xl font-black uppercase italic text-[#e5e1e4]">EXECUTION LOG</h2>
        <p className="text-[10px] font-mono text-[#e5e1e4]/40 uppercase tracking-widest mt-1">Audit trail of all automated trades</p>
      </div>

      <div className="bg-[#201f21] border border-[#1b1b1d]">
          <table className="w-full text-left border-collapse">
              <thead>
                  <tr className="bg-[#1b1b1d] text-[10px] font-mono text-[#e5e1e4]/40 uppercase border-b border-[#201f21]">
                      <th className="px-6 py-4 font-medium">Timestamp</th>
                      <th className="px-4 py-4 font-medium">Event</th>
                      <th className="px-4 py-4 font-medium">Action</th>
                      <th className="px-4 py-4 font-medium text-right">Size</th>
                      <th className="px-4 py-4 font-medium text-right text-emerald-500">Result</th>
                  </tr>
              </thead>
              <tbody className="text-[11px] font-mono divide-y divide-[#1b1b1d]">
                  <tr className="hover:bg-[#39393b] transition-colors">
                      <td className="px-6 py-4 text-[#e5e1e4]/40">2026-03-29 14:02:11</td>
                      <td className="px-4 py-4">FED_RATE_CUT_DEC</td>
                      <td className="px-4 py-4 font-bold text-emerald-500">BUY_YES</td>
                      <td className="px-4 py-4 text-right">$500.00</td>
                      <td className="px-4 py-4 text-right text-emerald-500">SUCCESS</td>
                  </tr>
              </tbody>
          </table>
      </div>
    </div>
  );
}
