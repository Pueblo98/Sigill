"use client";
import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { name: 'Dashboard', icon: 'dashboard', path: '/' },
  { name: 'Markets', icon: 'analytics', path: '/markets' },
  { name: 'Arb Scanner', icon: 'swap_horiz', path: '/arbitrage' },
  { name: 'Trade Detail', icon: 'receipt_long', path: '/trade-detail' },
  { name: 'Execution Log', icon: 'history_edu', path: '/execution' },
  { name: 'Models', icon: 'hub', path: '/models' },
  { name: 'Data Health', icon: 'monitor_heart', path: '/data-health' },
];

export function Sidebar({ 
  isSidebarOpen, 
  setIsSidebarOpen 
}: { 
  isSidebarOpen: boolean; 
  setIsSidebarOpen: (v: boolean) => void;
}) {
  const pathname = usePathname();
  // Ensure hydration matches server
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) return null;

  return (
    <aside 
      className={`fixed left-0 top-0 h-full bg-[#1b1b1d] border-r border-[#201f21] flex flex-col py-6 z-50 transition-all duration-300 ${
        isSidebarOpen ? 'w-64' : 'w-16'
      }`}
    >
      <div className={`px-4 mb-8 flex items-center ${isSidebarOpen ? 'justify-between' : 'justify-center'}`}>
        {isSidebarOpen ? (
          <div className="flex items-center gap-2">
            <span className="text-[#7C3AED] font-black tracking-tighter text-xl uppercase">Terminal</span>
            <span className="bg-[#7C3AED]/10 text-[#7C3AED] text-[10px] px-1 font-mono font-bold">v2.4.0</span>
          </div>
        ) : (
          <span className="text-[#7C3AED] font-black tracking-tighter text-xl uppercase">T</span>
        )}
        <button 
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="text-[#958da1] hover:text-[#e5e1e4] transition-colors"
        >
          <span className="material-symbols-outlined text-sm">
            {isSidebarOpen ? 'keyboard_double_arrow_left' : 'keyboard_double_arrow_right'}
          </span>
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto no-scrollbar px-2">
        {navItems.map((item) => {
          const isActive = pathname === item.path;
          return (
            <Link 
              key={item.path} 
              href={item.path}
              className={`flex items-center gap-3 px-3 py-3 transition-all duration-200 group ${
                isActive 
                  ? 'bg-[#201f21] border-l-4 border-[#7C3AED] text-[#e5e1e4] font-bold' 
                  : 'text-[#e5e1e4]/60 hover:text-[#e5e1e4] hover:bg-[#39393b] border-l-4 border-transparent'
              } ${!isSidebarOpen ? 'justify-center !px-0' : ''}`}
              title={!isSidebarOpen ? item.name : undefined}
            >
              <span className="material-symbols-outlined text-sm">{item.icon}</span>
              {isSidebarOpen && (
                <span className="text-[0.75rem] font-medium tracking-wide whitespace-nowrap">
                  {item.name}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 mt-auto">
        <button className={`w-full bg-[#7c3aed] text-[#ede0ff] py-3 font-bold text-xs uppercase tracking-widest hover:brightness-110 transition-all flex items-center justify-center gap-2 ${!isSidebarOpen ? '!px-0' : ''}`} title={!isSidebarOpen ? "New Trade" : undefined}>
          <span className="material-symbols-outlined text-sm">add</span>
          {isSidebarOpen && "New Trade"}
        </button>
        <div className={`mt-6 flex items-center gap-3 pt-6 border-t border-[#353437] ${!isSidebarOpen ? 'justify-center' : ''}`}>
          <div className="w-8 h-8 bg-[#2a2a2c] flex-shrink-0 flex items-center justify-center">
            <span className="material-symbols-outlined text-[#e5e1e4]/60 text-sm">person</span>
          </div>
          {isSidebarOpen && (
            <div className="overflow-hidden whitespace-nowrap">
              <p className="text-xs font-bold truncate">DEMO_USER_01</p>
              <p className="text-[10px] text-[#958da1]">Sandbox Session</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
