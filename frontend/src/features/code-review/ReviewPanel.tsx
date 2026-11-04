import React, { useState } from 'react';
import {
  ShieldCheck,
  AlertOctagon,
  AlertTriangle,
  Info,
  FileCode2,
  CheckCircle2,
  Loader2,
  ExternalLink,
} from 'lucide-react';
import { RepositoryFileItem, CodeReviewResponse, ReviewFinding } from '../../types';
import { api } from '../../api/client';

interface ReviewPanelProps {
  repositoryId: string;
  files: RepositoryFileItem[];
  onCitationClick: (filePath: string, startLine: number, endLine: number) => void;
}

export const ReviewPanel: React.FC<ReviewPanelProps> = ({
  repositoryId,
  files,
  onCitationClick,
}) => {
  const [selectedFile, setSelectedFile] = useState<string>(files[0]?.file_path || '');
  const [customSnippet, setCustomSnippet] = useState<string>('');
  const [useSnippet, setUseSnippet] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [reviewResult, setReviewResult] = useState<CodeReviewResponse | null>(null);

  const handleReview = async () => {
    setLoading(true);
    try {
      const data = await api.reviewCode({
        repository_id: repositoryId,
        file_path: useSnippet ? undefined : selectedFile,
        code_snippet: useSnippet ? customSnippet : undefined,
      });
      setReviewResult(data);
    } catch (err: any) {
      console.error('Review failed:', err);
      alert(err.response?.data?.message || 'Code review analysis failed.');
    } finally {
      setLoading(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <AlertOctagon className="w-3 h-3" /> Critical
          </span>
        );
      case 'high':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-3 h-3" /> High
          </span>
        );
      case 'medium':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-sky-500/20 text-sky-400 border border-sky-500/30">
            <Info className="w-3 h-3" /> Medium
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-zinc-500/20 text-zinc-400 border border-zinc-500/30">
            Low
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Review Trigger Card */}
      <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#30363d]">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">AI Code Review & Security Audit</h3>
            <p className="text-xs text-[#8b949e]">
              Analyze code for potential bugs, null safety, SQL/command injection, and maintainability.
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex gap-4 text-xs font-medium">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="reviewType"
                checked={!useSnippet}
                onChange={() => setUseSnippet(false)}
                className="text-emerald-500 focus:ring-0"
              />
              <span>Review Repository File</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="reviewType"
                checked={useSnippet}
                onChange={() => setUseSnippet(true)}
                className="text-emerald-500 focus:ring-0"
              />
              <span>Review Custom Snippet</span>
            </label>
          </div>

          {!useSnippet ? (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                Select File to Review
              </label>
              <select
                value={selectedFile}
                onChange={(e) => setSelectedFile(e.target.value)}
                className="w-full bg-[#0d1117] text-xs font-mono text-[#c9d1d9] px-3.5 py-2.5 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
              >
                {files.map((f) => (
                  <option key={f.id} value={f.file_path}>
                    {f.file_path}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                Paste Code Snippet
              </label>
              <textarea
                rows={5}
                placeholder="Paste code snippet to review..."
                value={customSnippet}
                onChange={(e) => setCustomSnippet(e.target.value)}
                className="w-full bg-[#0d1117] text-xs font-mono text-[#c9d1d9] p-3 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
              />
            </div>
          )}

          <div className="flex justify-end pt-2">
            <button
              onClick={handleReview}
              disabled={loading || (!useSnippet && !selectedFile) || (useSnippet && !customSnippet.trim())}
              className="px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-40 text-black font-semibold text-xs flex items-center gap-2 transition-colors shadow-sm"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Running Review...
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  Start Code Review
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Review Results */}
      {reviewResult && (
        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-6 space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-[#30363d]">
            <div>
              <h4 className="text-sm font-semibold text-white">Review Summary</h4>
              <p className="text-xs text-[#8b949e] mt-0.5">{reviewResult.summary}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded bg-[#0d1117] border border-[#30363d] text-xs text-[#c9d1d9] font-mono">
                {reviewResult.total_findings} findings
              </span>
            </div>
          </div>

          {/* Findings List */}
          <div className="space-y-3">
            {reviewResult.findings.map((finding: ReviewFinding, idx: number) => (
              <div
                key={idx}
                className="p-4 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-2 hover:border-[#484f58] transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    {getSeverityBadge(finding.severity)}
                    <span className="text-xs font-semibold text-[#e6edf3]">{finding.title}</span>
                  </div>
                  <button
                    onClick={() => onCitationClick(finding.file_path, finding.start_line, finding.end_line)}
                    className="flex items-center gap-1 text-[11px] font-mono text-emerald-400 hover:underline shrink-0"
                  >
                    <span>
                      {finding.file_path}:{finding.start_line}
                    </span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>

                <p className="text-xs text-[#8b949e] leading-relaxed">{finding.description}</p>

                {finding.evidence && (
                  <div className="px-3 py-2 rounded bg-[#161b22] border border-[#30363d] text-[11px] font-mono text-[#c9d1d9] overflow-x-auto">
                    <code>{finding.evidence}</code>
                  </div>
                )}

                <div className="text-xs text-emerald-300/90 pt-1 flex items-start gap-1.5">
                  <span className="font-semibold text-emerald-400 shrink-0">Remediation:</span>
                  <span>{finding.suggested_improvement}</span>
                </div>
              </div>
            ))}

            {reviewResult.findings.length === 0 && (
              <div className="p-8 text-center text-xs text-emerald-400 flex items-center justify-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                No critical or high-severity vulnerabilities detected in analyzed target.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
