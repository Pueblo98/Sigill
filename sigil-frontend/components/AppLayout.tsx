"use client";
import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className="flex min-h-screen bg-[#0e0e10] text-[#e5e1e4] font-sans selection:bg-[#7c3aed]/30 overflow-hidden">
      <Sidebar isSidebarOpen={isSidebarOpen} setIsSidebarOpen={setIsSidebarOpen} />
      <div className={`flex-1 flex flex-col min-h-screen transition-all duration-300 ${isSidebarOpen ? 'ml-64' : 'ml-16'}`}>
        <TopNav />
        <div className="flex-1 overflow-y-auto flex flex-col">
            {children}
        </div>
      </div>
    </div>
  );
}
