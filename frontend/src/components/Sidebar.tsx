import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Code2,
  FolderGit2,
  LayoutDashboard,
  PlusCircle,
  MessageSquareCode,
  Bug,
  ShieldCheck,
  Settings,
  LogOut,
  User,
} from 'lucide-react';
import { useAuth } from '../features/auth/AuthContext';

export const Sidebar: React.FC<{ onOpenAddModal: () => void }> = ({ onOpenAddModal }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Repositories', path: '/repositories', icon: FolderGit2 },
  ];

  return (
    <aside className="w-64 bg-[#161b22] border-r border-[#30363d] flex flex-col h-screen select-none">
      {/* Brand Header */}
      <div className="h-16 flex items-center gap-3 px-6 border-b border-[#30363d]">
        <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <Code2 className="w-5 h-5" />
        </div>
        <div>
          <span className="font-bold text-base tracking-tight text-white flex items-center gap-1.5">
            RepoSage
            <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              v1.0
            </span>
          </span>
          <p className="text-xs text-[#8b949e]">AI Codebase Assistant</p>
        </div>
      </div>

      {/* Main Navigation */}
      <div className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[11px] font-semibold text-[#8b949e] uppercase tracking-wider">
          Workspace
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'text-[#c9d1d9] hover:bg-[#21262d] hover:text-white'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {item.name}
            </NavLink>
          );
        })}

        <div className="pt-4 pb-2 px-3 text-[11px] font-semibold text-[#8b949e] uppercase tracking-wider">
          Actions
        </div>

        <button
          onClick={onOpenAddModal}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 transition-all text-left"
        >
          <PlusCircle className="w-4 h-4 text-emerald-400" />
          Add Repository
        </button>
      </div>

      {/* User Footer */}
      <div className="p-3 border-t border-[#30363d] bg-[#0d1117]/60">
        <div className="flex items-center justify-between p-2 rounded-md bg-[#161b22] border border-[#30363d]">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs shrink-0">
              {user?.email?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="truncate">
              <div className="text-xs font-medium text-white truncate">{user?.email || 'Developer'}</div>
              <div className="text-[10px] text-emerald-400 font-mono">Active Session</div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            title="Log Out"
            className="p-1.5 text-[#8b949e] hover:text-rose-400 hover:bg-rose-500/10 rounded transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
