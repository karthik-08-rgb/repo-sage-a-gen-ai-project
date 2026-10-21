import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderGit2,
  FileCode2,
  Layers,
  Activity,
  PlusCircle,
  ExternalLink,
  RefreshCw,
  Trash2,
  ArrowRight,
  Loader2,
  CheckCircle2,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { Repository } from '../types';
import { api } from '../api/client';

export const DashboardPage: React.FC<{ onOpenAddModal: () => void }> = ({ onOpenAddModal }) => {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [reindexingId, setReindexingId] = useState<string | null>(null);
  const navigate = useNavigate();

  const loadRepositories = async () => {
    try {
      const data = await api.getRepositories();
      setRepositories(data);
    } catch (err) {
      console.error('Failed to load repositories:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRepositories();
    const interval = setInterval(loadRepositories, 6000); // Poll status updates during indexing
    return () => clearInterval(interval);
  }, []);

  const handleReindex = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setReindexingId(id);
    try {
      await api.reindexRepository(id);
      await loadRepositories();
    } catch (err) {
      console.error('Reindexing failed:', err);
    } finally {
      setReindexingId(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string, name: string) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to delete repository '${name}'?`)) return;
    try {
      await api.deleteRepository(id);
      await loadRepositories();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  // Aggregated Stats
  const totalRepos = repositories.length;
  const readyRepos = repositories.filter((r) => r.status === 'ready').length;
  const totalFiles = repositories.reduce((acc, r) => acc + (r.total_files || 0), 0);
  const totalChunks = repositories.reduce((acc, r) => acc + (r.total_chunks || 0), 0);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ready':
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> Ready
          </span>
        );
      case 'indexing':
      case 'cloning':
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Loader2 className="w-3 h-3 animate-spin" /> Indexing
          </span>
        );
      case 'failed':
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="w-3 h-3" /> Failed
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-[#30363d] text-[#8b949e]">
            <Clock className="w-3 h-3" /> Pending
          </span>
        );
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Codebase Intelligence Dashboard</h1>
          <p className="text-xs text-[#8b949e] mt-1">
            Grounded code understanding, vector indexing, and AI-assisted debugging across your repositories.
          </p>
        </div>
        <button
          onClick={onOpenAddModal}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-black font-semibold text-xs transition-colors shadow-sm"
        >
          <PlusCircle className="w-4 h-4" />
          Add Repository
        </button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-[#161b22] border border-[#30363d]">
          <div className="flex items-center justify-between text-[#8b949e]">
            <span className="text-xs font-semibold uppercase tracking-wider">Repositories</span>
            <FolderGit2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2 font-mono">{totalRepos}</div>
          <div className="text-[11px] text-emerald-400 mt-1">{readyRepos} indexed & ready</div>
        </div>

        <div className="p-5 rounded-xl bg-[#161b22] border border-[#30363d]">
          <div className="flex items-center justify-between text-[#8b949e]">
            <span className="text-xs font-semibold uppercase tracking-wider">Indexed Files</span>
            <FileCode2 className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2 font-mono">{totalFiles}</div>
          <div className="text-[11px] text-[#8b949e] mt-1">Across all repositories</div>
        </div>

        <div className="p-5 rounded-xl bg-[#161b22] border border-[#30363d]">
          <div className="flex items-center justify-between text-[#8b949e]">
            <span className="text-xs font-semibold uppercase tracking-wider">Code Chunks</span>
            <Layers className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2 font-mono">{totalChunks}</div>
          <div className="text-[11px] text-purple-400 mt-1">Hierarchical AST chunks</div>
        </div>

        <div className="p-5 rounded-xl bg-[#161b22] border border-[#30363d]">
          <div className="flex items-center justify-between text-[#8b949e]">
            <span className="text-xs font-semibold uppercase tracking-wider">Retrieval Mode</span>
            <Activity className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-xl font-bold text-white mt-2">Hybrid Search</div>
          <div className="text-[11px] text-emerald-400 mt-1">Dense + Keyword RRF</div>
        </div>
      </div>

      {/* Repositories Table / Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">Your Repositories</h2>
          <span className="text-xs text-[#8b949e]">{repositories.length} total</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-xs text-[#8b949e] flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
            Loading repositories...
          </div>
        ) : repositories.length === 0 ? (
          <div className="p-12 rounded-xl border border-dashed border-[#30363d] bg-[#161b22]/50 text-center space-y-4">
            <FolderGit2 className="w-10 h-10 text-[#8b949e] mx-auto opacity-40" />
            <div>
              <h3 className="text-sm font-semibold text-white">No repositories indexed yet</h3>
              <p className="text-xs text-[#8b949e] mt-1">
                Add a public GitHub repo or upload a project ZIP to begin code intelligence and debugging.
              </p>
            </div>
            <button
              onClick={onOpenAddModal}
              className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-black font-semibold text-xs inline-flex items-center gap-1.5 transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              Add First Repository
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {repositories.map((repo) => (
              <div
                key={repo.id}
                onClick={() => navigate(`/repositories/${repo.id}`)}
                className="group p-5 rounded-xl bg-[#161b22] border border-[#30363d] hover:border-emerald-500/40 hover:bg-[#21262d]/50 transition-all cursor-pointer flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold text-white group-hover:text-emerald-400 transition-colors truncate">
                      {repo.name}
                    </h3>
                    {getStatusBadge(repo.status)}
                  </div>

                  <p className="text-xs text-[#8b949e] mt-1 font-mono truncate">
                    {repo.source_url || `Uploaded Archive (${repo.source_type})`}
                  </p>
                </div>

                <div className="grid grid-cols-3 gap-2 py-2 border-y border-[#30363d]/60 text-center font-mono">
                  <div>
                    <div className="text-[10px] text-[#8b949e] uppercase">Files</div>
                    <div className="text-xs font-semibold text-[#c9d1d9]">{repo.total_files}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-[#8b949e] uppercase">Chunks</div>
                    <div className="text-xs font-semibold text-[#c9d1d9]">{repo.total_chunks}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-[#8b949e] uppercase">Language</div>
                    <div className="text-xs font-semibold text-emerald-400 uppercase truncate">
                      {repo.primary_language || 'Generic'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs pt-1">
                  <span className="text-[11px] text-[#8b949e]">Branch: {repo.default_branch}</span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => handleReindex(e, repo.id)}
                      title="Re-index Codebase"
                      className="p-1.5 text-[#8b949e] hover:text-emerald-400 hover:bg-[#30363d] rounded transition-colors"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${reindexingId === repo.id ? 'animate-spin text-emerald-400' : ''}`} />
                    </button>
                    <button
                      onClick={(e) => handleDelete(e, repo.id, repo.name)}
                      title="Delete Repository"
                      className="p-1.5 text-[#8b949e] hover:text-rose-400 hover:bg-rose-500/10 rounded transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <span className="p-1 text-emerald-400 group-hover:translate-x-0.5 transition-transform">
                      <ArrowRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
