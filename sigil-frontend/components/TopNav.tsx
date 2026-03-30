import React from 'react';

export function TopNav() {
  return (
    <header className="h-14 bg-[#0e0e10] border-b border-[#1b1b1d] flex justify-between items-center px-6 sticky top-0 z-40">
      <div className="flex items-center gap-8 flex-1">
        <h1 className="text-xl font-black tracking-tighter text-[#7c3aed]">SIGIL</h1>
        <div className="relative w-full max-w-md hidden md:block">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#958da1] text-sm">search</span>
          <input 
            className="w-full bg-[#1b1b1d] border-none text-[10px] font-mono py-2 pl-10 pr-4 focus:ring-1 focus:ring-[#7C3AED] placeholder:text-[#958da1]/40 text-[#e5e1e4]" 
            placeholder="SEARCH MARKETS OR SYMBOLS..." 
            type="text"
          />
        </div>
      </div>
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 bg-[#1b1b1d] p-1">
          <button className="px-3 py-1 text-[9px] font-mono font-bold bg-[#7C3AED]/20 text-[#d2bbff] ring-1 ring-[#7C3AED] shadow-[0_0_15px_rgba(124,58,237,0.3)]">PAPER MODE</button>
          <button className="px-3 py-1 text-[9px] font-mono font-bold text-[#958da1]/50 cursor-not-allowed" title="Live mode disabled in demo">LIVE MODE</button>
        </div>
        <div className="flex items-center gap-4 text-[#958da1]">
          <button className="hover:bg-[#39393b] p-2 transition-colors duration-150 relative text-[#e5e1e4]">
            <span className="material-symbols-outlined text-sm">notifications</span>
            <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-[#7C3AED]"></span>
          </button>
          <button className="hover:bg-[#39393b] p-2 transition-colors duration-150 text-[#e5e1e4]">
            <span className="material-symbols-outlined text-sm">person</span>
          </button>
        </div>
      </div>
    </header>
  );
}
