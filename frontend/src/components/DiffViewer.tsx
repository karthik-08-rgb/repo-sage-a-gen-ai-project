import React, { useState } from 'react';
import { Check, Copy, FileCode2, Play, Loader2, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';

interface DiffViewerProps {
  diff: string;
  filePath?: string;
  repositoryId?: string;
  onApplied?: () => void;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  diff,
  filePath,
  repositoryId,
  onApplied,
}) => {
  const [copied, setCopied] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(diff);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleApply = async () => {
    if (!repositoryId || !filePath || applying) return;
    setApplying(true);
    try {
      await api.applyApprovedDiff({
        repository_id: repositoryId,
        file_path: filePath,
        unified_diff: diff,
      });
      setApplied(true);
      if (onApplied) onApplied();
    } catch (err: any) {
      console.error('Failed to apply diff:', err);
      alert(err.response?.data?.message || 'Failed to apply diff.');
    } finally {
      setApplying(false);
    }
  };

  const lines = diff.split('\n');

  return (
    <div className="rounded-lg border border-[#30363d] bg-[#0d1117] overflow-hidden my-3">
      <div className="flex items-center justify-between px-4 py-2 bg-[#161b22] border-b border-[#30363d] text-xs font-mono text-[#8b949e]">
        <div className="flex items-center gap-2">
          <FileCode2 className="w-4 h-4 text-emerald-400" />
          <span className="text-[#c9d1d9] font-medium">{filePath || 'Suggested Unified Diff'}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#21262d] hover:bg-[#30363d] text-[#c9d1d9] transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? 'Copied' : 'Copy Diff'}
          </button>
          {repositoryId && filePath && (
            <button
              onClick={handleApply}
              disabled={applying || applied}
              className={`flex items-center gap-1.5 px-3 py-1 rounded font-sans font-semibold text-xs transition-colors shadow-sm ${
                applied
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 cursor-default'
                  : 'bg-emerald-500 hover:bg-emerald-600 text-black'
              }`}
            >
              {applying ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Applying...
                </>
              ) : applied ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" /> Applied
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" /> Approve & Apply
                </>
              )}
            </button>
          )}
        </div>
      </div>

      <div className="p-3 font-mono text-xs overflow-x-auto leading-relaxed max-h-96">
        {lines.map((line, idx) => {
          let lineStyle = 'text-[#8b949e]';
          let bgStyle = '';

          if (line.startsWith('+') && !line.startsWith('+++')) {
            lineStyle = 'text-emerald-300';
            bgStyle = 'bg-emerald-950/30';
          } else if (line.startsWith('-') && !line.startsWith('---')) {
            lineStyle = 'text-rose-300';
            bgStyle = 'bg-rose-950/30';
          } else if (line.startsWith('@@')) {
            lineStyle = 'text-sky-300 font-semibold';
            bgStyle = 'bg-sky-950/20';
          } else if (line.startsWith('diff --git') || line.startsWith('index ')) {
            lineStyle = 'text-[#8b949e] font-semibold';
          }

          return (
            <div key={idx} className={`px-2 py-0.5 rounded ${bgStyle} ${lineStyle} whitespace-pre`}>
              {line || ' '}
            </div>
          );
        })}
      </div>
    </div>
  );
};
