import React, { useState } from 'react';
import {
  Bug,
  AlertTriangle,
  FileCode2,
  CheckCircle2,
  Sparkles,
  Loader2,
  ArrowRight,
} from 'lucide-react';
import { DebugAnalyzeResponse } from '../../types';
import { api } from '../../api/client';
import { DiffViewer } from '../../components/DiffViewer';

interface DebugPanelProps {
  repositoryId: string;
  onCitationClick: (filePath: string, startLine: number, endLine: number) => void;
}

export const DebugPanel: React.FC<DebugPanelProps> = ({ repositoryId, onCitationClick }) => {
  const [errorMessage, setErrorMessage] = useState('');
  const [stackTrace, setStackTrace] = useState('');
  const [relevantFile, setRelevantFile] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DebugAnalyzeResponse | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!errorMessage.trim() || loading) return;

    setLoading(true);
    try {
      const data = await api.analyzeDebug({
        repository_id: repositoryId,
        error_message: errorMessage.trim(),
        stack_trace: stackTrace.trim() || undefined,
        relevant_file: relevantFile.trim() || undefined,
      });
      setResult(data);
    } catch (err: any) {
      console.error('Debug analysis error:', err);
      alert(err.response?.data?.message || 'Failed to analyze error.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Input Form Card */}
      <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#30363d]">
          <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <Bug className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">AI Debugging Assistant</h3>
            <p className="text-xs text-[#8b949e]">
              Paste stack traces and runtime errors to locate affected files and generate unified diff fixes.
            </p>
          </div>
        </div>

        <form onSubmit={handleAnalyze} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
              Error Message <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. AttributeError: 'NoneType' object has no attribute 'verify_password'"
              value={errorMessage}
              onChange={(e) => setErrorMessage(e.target.value)}
              className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] px-3.5 py-2.5 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                Target File (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. app/services/auth/auth_service.py"
                value={relevantFile}
                onChange={(e) => setRelevantFile(e.target.value)}
                className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] px-3.5 py-2 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                Expected Behavior (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Return 401 response instead of crashing with 500"
                className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] px-3.5 py-2 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
              Stack Trace (Optional)
            </label>
            <textarea
              rows={4}
              placeholder="Traceback (most recent call last):&#10;  File &quot;app/api/v1/auth.py&quot;, line 42, in login&#10;    user = auth_service.authenticate_user(email, password)"
              value={stackTrace}
              onChange={(e) => setStackTrace(e.target.value)}
              className="w-full bg-[#0d1117] text-xs font-mono text-[#c9d1d9] p-3 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none leading-relaxed"
            />
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={loading || !errorMessage.trim()}
              className="px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-40 text-black font-semibold text-xs flex items-center gap-2 transition-colors shadow-sm"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing Root Cause...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Analyze & Suggest Fix
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Analysis Results Display */}
      {result && (
        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-6 space-y-6">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
            <CheckCircle2 className="w-4 h-4" />
            Root Cause Diagnosis & Suggested Fix
          </div>

          {/* Root cause box */}
          <div className="p-4 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-2">
            <div className="text-xs font-semibold text-rose-400 flex items-center gap-1.5 uppercase tracking-wider">
              <AlertTriangle className="w-3.5 h-3.5" />
              Potential Root Cause
            </div>
            <p className="text-xs text-[#e6edf3] leading-relaxed">{result.potential_root_cause}</p>
          </div>

          {/* Affected files */}
          <div>
            <div className="text-xs font-semibold text-[#8b949e] uppercase tracking-wider mb-2">
              Affected Files in Codebase
            </div>
            <div className="flex flex-wrap gap-2">
              {result.affected_files.map((file, i) => (
                <button
                  key={i}
                  onClick={() => onCitationClick(file, 1, 30)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#0d1117] border border-[#30363d] hover:border-emerald-500/40 text-xs font-mono text-emerald-400 transition-colors"
                >
                  <FileCode2 className="w-3.5 h-3.5" />
                  {file}
                </button>
              ))}
            </div>
          </div>

          {/* Suggested Diff */}
          {result.suggested_fixes.map((fix, idx) => (
            <div key={idx} className="space-y-2">
              <div className="flex items-center justify-between text-xs font-semibold text-[#c9d1d9]">
                <span>Proposed Fix: {fix.description}</span>
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px]">
                  Confidence: {fix.confidence}
                </span>
              </div>
              <DiffViewer
                diff={fix.unified_diff}
                filePath={fix.file_path}
                repositoryId={repositoryId}
              />
            </div>
          ))}

          {/* Validation Steps */}
          {result.tests_to_validate && result.tests_to_validate.length > 0 && (
            <div className="p-4 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-2">
              <div className="text-xs font-semibold text-sky-400 uppercase tracking-wider">
                Recommended Verification Tests
              </div>
              <ul className="list-disc list-inside text-xs text-[#8b949e] space-y-1 font-mono">
                {result.tests_to_validate.map((test, i) => (
                  <li key={i}>{test}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
