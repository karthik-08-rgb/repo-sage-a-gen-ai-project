import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  FolderGit2,
  FileCode2,
  MessageSquareCode,
  Bug,
  ShieldCheck,
  Activity,
  ArrowLeft,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  GitBranch,
  GitCommit,
  Clock,
  Layers,
} from 'lucide-react';
import { Repository, RepositoryFileItem, RepositoryStatus } from '../types';
import { api } from '../api/client';
import { CodeViewer } from '../features/code-viewer/CodeViewer';
import { ChatPanel } from '../features/chat/ChatPanel';
import { DebugPanel } from '../features/debugging/DebugPanel';
import { ReviewPanel } from '../features/code-review/ReviewPanel';

export const RepoDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [repo, setRepo] = useState<Repository | null>(null);
  const [statusInfo, setStatusInfo] = useState<RepositoryStatus | null>(null);
  const [files, setFiles] = useState<RepositoryFileItem[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'files' | 'chat' | 'debug' | 'review' | 'activity'>('overview');
  const [loading, setLoading] = useState<boolean>(true);
  const [reindexing, setReindexing] = useState<boolean>(false);

  // Jump-to-code state for Monaco Editor
  const [viewerPath, setViewerPath] = useState<string | undefined>(undefined);
  const [viewerLine, setViewerLine] = useState<number | undefined>(undefined);
  const [viewerHighlight, setViewerHighlight] = useState<[number, number] | undefined>(undefined);

  const loadData = async () => {
    if (!id) return;
    try {
      const [repoData, statusData, filesData] = await Promise.all([
        api.getRepository(id),
        api.getRepositoryStatus(id),
        api.getRepositoryFiles(id),
      ]);
      setRepo(repoData);
      setStatusInfo(statusData);
      setFiles(filesData);
    } catch (err) {
      console.error('Failed to load repo details:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(async () => {
      if (id) {
        const s = await api.getRepositoryStatus(id);
        setStatusInfo(s);
        if (s.status === 'ready' && repo?.status !== 'ready') {
          loadData();
        }
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [id]);

  const handleReindex = async () => {
    if (!id) return;
    setReindexing(true);
    try {
      await api.reindexRepository(id);
      await loadData();
    } catch (err) {
      console.error('Reindexing failed:', err);
    } finally {
      setReindexing(false);
    }
  };

  const handleCitationClick = (filePath: string, startLine: number, endLine: number) => {
    setViewerPath(filePath);
    setViewerLine(startLine);
    setViewerHighlight([startLine, endLine]);
    setActiveTab('files');
  };

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center text-xs text-[#8b949e] gap-2">
        <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
        Loading repository workspace...
      </div>
    );
  }

  if (!repo) {
    return (
      <div className="p-12 text-center text-sm text-[#8b949e]">
        Repository not found.
        <button onClick={() => navigate('/repositories')} className="block mx-auto mt-4 text-emerald-400 underline text-xs">
          Back to Repositories
        </button>
      </div>
    );
  }

  const tabs = [
    { key: 'overview', label: 'Overview', icon: FolderGit2 },
    { key: 'files', label: `Files (${files.length})`, icon: FileCode2 },
    { key: 'chat', label: 'Ask Codebase', icon: MessageSquareCode },
    { key: 'debug', label: 'Debug Assistant', icon: Bug },
    { key: 'review', label: 'Code Review', icon: ShieldCheck },
    { key: 'activity', label: 'Indexing Activity', icon: Activity },
  ];

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Top Breadcrumb & Actions */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/repositories')}
          className="flex items-center gap-1.5 text-xs text-[#8b949e] hover:text-[#c9d1d9] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Repositories
        </button>

        <div className="flex items-center gap-3">
          <button
            onClick={handleReindex}
            disabled={reindexing || statusInfo?.status === 'indexing'}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#21262d] hover:bg-[#30363d] disabled:opacity-50 text-xs font-medium text-[#c9d1d9] transition-colors border border-[#30363d]"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${reindexing || statusInfo?.status === 'indexing' ? 'animate-spin text-emerald-400' : ''}`} />
            Re-index Codebase
          </button>
        </div>
      </div>

      {/* Repo Title Header Card */}
      <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-6 space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-white tracking-tight">{repo.name}</h1>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-mono uppercase">
                {repo.primary_language || 'Codebase'}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${
                  statusInfo?.status === 'ready'
                    ? 'bg-emerald-500/15 text-emerald-400'
                    : statusInfo?.status === 'indexing'
                    ? 'bg-amber-500/15 text-amber-400'
                    : 'bg-rose-500/15 text-rose-400'
                }`}
              >
                {statusInfo?.status === 'ready' ? 'Ready & Indexed' : statusInfo?.status === 'indexing' ? 'Indexing...' : 'Pending'}
              </span>
            </div>

            <p className="text-xs text-[#8b949e] mt-1 font-mono">{repo.source_url || 'Uploaded ZIP Repository'}</p>
          </div>

          <div className="flex items-center gap-4 text-xs text-[#8b949e] font-mono">
            <span className="flex items-center gap-1">
              <GitBranch className="w-3.5 h-3.5 text-emerald-400" />
              {repo.default_branch}
            </span>
            {repo.commit_sha && (
              <span className="flex items-center gap-1">
                <GitCommit className="w-3.5 h-3.5 text-sky-400" />
                {repo.commit_sha.substring(0, 7)}
              </span>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[#30363d] pt-2 gap-2 overflow-x-auto text-xs font-medium">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as any)}
                className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors whitespace-nowrap ${
                  isActive
                    ? 'border-emerald-500 text-emerald-400 font-semibold'
                    : 'border-transparent text-[#8b949e] hover:text-[#c9d1d9]'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Panels */}
      <div>
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 space-y-6">
              <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-6 space-y-4">
                <h3 className="text-sm font-semibold text-white">Repository Overview</h3>
                <p className="text-xs text-[#8b949e] leading-relaxed">
                  RepoSage has parsed and indexed this repository using AST and language-aware chunking.
                  Dense vector similarity and full-text keyword retrieval are active.
                </p>

                <div className="grid grid-cols-3 gap-4 pt-2">
                  <div className="p-4 rounded-lg bg-[#0d1117] border border-[#30363d] text-center">
                    <div className="text-[11px] text-[#8b949e] uppercase font-mono">Total Files</div>
                    <div className="text-xl font-bold text-white mt-1 font-mono">{repo.total_files}</div>
                  </div>
                  <div className="p-4 rounded-lg bg-[#0d1117] border border-[#30363d] text-center">
                    <div className="text-[11px] text-[#8b949e] uppercase font-mono">Code Chunks</div>
                    <div className="text-xl font-bold text-emerald-400 mt-1 font-mono">{repo.total_chunks}</div>
                  </div>
                  <div className="p-4 rounded-lg bg-[#0d1117] border border-[#30363d] text-center">
                    <div className="text-[11px] text-[#8b949e] uppercase font-mono">Primary Language</div>
                    <div className="text-xl font-bold text-sky-400 mt-1 uppercase font-mono">
                      {repo.primary_language || 'Generic'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-6 space-y-4">
                <h3 className="text-sm font-semibold text-white">Suggested Assistant Tasks</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <button
                    onClick={() => setActiveTab('chat')}
                    className="p-4 rounded-lg bg-[#0d1117] hover:bg-[#21262d] border border-[#30363d] text-left transition-colors group"
                  >
                    <MessageSquareCode className="w-5 h-5 text-emerald-400 mb-2" />
                    <div className="text-xs font-semibold text-white group-hover:text-emerald-400">Ask Architecture</div>
                    <div className="text-[11px] text-[#8b949e] mt-1">Get grounded explanations of project modules.</div>
                  </button>

                  <button
                    onClick={() => setActiveTab('debug')}
                    className="p-4 rounded-lg bg-[#0d1117] hover:bg-[#21262d] border border-[#30363d] text-left transition-colors group"
                  >
                    <Bug className="w-5 h-5 text-rose-400 mb-2" />
                    <div className="text-xs font-semibold text-white group-hover:text-rose-400">Debug Exceptions</div>
                    <div className="text-[11px] text-[#8b949e] mt-1">Paste stack traces to find root causes.</div>
                  </button>

                  <button
                    onClick={() => setActiveTab('review')}
                    className="p-4 rounded-lg bg-[#0d1117] hover:bg-[#21262d] border border-[#30363d] text-left transition-colors group"
                  >
                    <ShieldCheck className="w-5 h-5 text-amber-400 mb-2" />
                    <div className="text-xs font-semibold text-white group-hover:text-amber-400">Code Review</div>
                    <div className="text-[11px] text-[#8b949e] mt-1">Audit security, null handling, and quality.</div>
                  </button>
                </div>
              </div>
            </div>

            {/* Sidebar Metadata Card */}
            <div className="space-y-6">
              <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-6 space-y-4">
                <h3 className="text-xs font-semibold text-[#8b949e] uppercase tracking-wider">Repository Details</h3>
                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-[#8b949e] block text-[11px]">Repository ID</span>
                    <span className="font-mono text-[#c9d1d9] text-[11px] truncate block">{repo.id}</span>
                  </div>
                  <div>
                    <span className="text-[#8b949e] block text-[11px]">Ingestion Source</span>
                    <span className="capitalize text-[#c9d1d9]">{repo.source_type}</span>
                  </div>
                  <div>
                    <span className="text-[#8b949e] block text-[11px]">Last Indexed</span>
                    <span className="text-[#c9d1d9]">
                      {repo.last_indexed_at ? new Date(repo.last_indexed_at).toLocaleString() : 'Never'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'files' && (
          <CodeViewer
            repositoryId={repo.id}
            files={files}
            selectedPath={viewerPath}
            targetLine={viewerLine}
            highlightRange={viewerHighlight}
            onSelectFile={(p) => setViewerPath(p)}
          />
        )}

        {activeTab === 'chat' && (
          <ChatPanel repositoryId={repo.id} onCitationClick={handleCitationClick} />
        )}

        {activeTab === 'debug' && (
          <DebugPanel repositoryId={repo.id} onCitationClick={handleCitationClick} />
        )}

        {activeTab === 'review' && (
          <ReviewPanel repositoryId={repo.id} files={files} onCitationClick={handleCitationClick} />
        )}

        {activeTab === 'activity' && (
          <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-6 space-y-6">
            <h3 className="text-sm font-semibold text-white">Indexing Activity & Pipeline Status</h3>

            <div className="p-4 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#8b949e]">Current Stage: <span className="font-mono text-emerald-400">{statusInfo?.current_stage || 'idle'}</span></span>
                <span className="font-mono text-white font-bold">{statusInfo?.progress || 100}%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-[#21262d] overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all duration-500 rounded-full"
                  style={{ width: `${statusInfo?.progress || 100}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-xs font-semibold text-[#8b949e] uppercase tracking-wider">Pipeline Steps Executed</div>
              <div className="space-y-2 text-xs font-mono text-[#c9d1d9]">
                <div className="p-2.5 rounded bg-[#0d1117] border border-[#30363d] flex items-center justify-between">
                  <span>1. Repository Acquisition & URL/ZIP Validation</span>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="p-2.5 rounded bg-[#0d1117] border border-[#30363d] flex items-center justify-between">
                  <span>2. File Discovery & Sensitive Secret Filtering</span>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="p-2.5 rounded bg-[#0d1117] border border-[#30363d] flex items-center justify-between">
                  <span>3. Source Code Parsing & AST Symbol Extraction</span>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="p-2.5 rounded bg-[#0d1117] border border-[#30363d] flex items-center justify-between">
                  <span>4. Code-Aware Hierarchical Chunking</span>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="p-2.5 rounded bg-[#0d1117] border border-[#30363d] flex items-center justify-between">
                  <span>5. Batch Vector Embedding Generation</span>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="p-2.5 rounded bg-[#0d1117] border border-[#30363d] flex items-center justify-between">
                  <span>6. PostgreSQL / pgvector Storage & Full-Text Indexing</span>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
