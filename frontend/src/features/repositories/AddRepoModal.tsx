import React, { useState } from 'react';
import { X, Github, Upload, Loader2, AlertCircle, Check } from 'lucide-react';
import { api } from '../../api/client';
import { Repository } from '../../types';

interface AddRepoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (repo: Repository) => void;
}

export const AddRepoModal: React.FC<AddRepoModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [activeTab, setActiveTab] = useState<'github' | 'zip'>('github');
  const [repoName, setRepoName] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [accessToken, setAccessToken] = useState('');
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      let createdRepo: Repository;
      if (activeTab === 'github') {
        if (!githubUrl.trim()) throw new Error('Repository URL is required');
        createdRepo = await api.addGitHubRepo({
          name: repoName.trim() || githubUrl.split('/').pop()?.replace('.git', '') || 'repo',
          url: githubUrl.trim(),
          branch: branch.trim() || 'main',
          access_token: accessToken.trim() || undefined,
        });
      } else {
        if (!zipFile) throw new Error('Please select a ZIP file');
        const formData = new FormData();
        formData.append('name', repoName.trim() || zipFile.name.replace('.zip', ''));
        formData.append('file', zipFile);
        createdRepo = await api.uploadZipRepo(formData);
      }

      onSuccess(createdRepo);
      onClose();
    } catch (err: any) {
      console.error('Failed to add repo:', err);
      setError(err.response?.data?.message || err.message || 'Failed to add repository.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in">
      <div className="w-full max-w-lg rounded-2xl bg-[#161b22] border border-[#30363d] shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#30363d]">
          <h3 className="text-base font-semibold text-white">Add Repository to RepoSage</h3>
          <button
            onClick={onClose}
            className="p-1.5 text-[#8b949e] hover:text-white rounded-lg hover:bg-[#21262d] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-[#30363d] px-6 pt-3 gap-6 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('github')}
            className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === 'github'
                ? 'border-emerald-500 text-emerald-400'
                : 'border-transparent text-[#8b949e] hover:text-[#c9d1d9]'
            }`}
          >
            <Github className="w-4 h-4" />
            GitHub Repository
          </button>
          <button
            onClick={() => setActiveTab('zip')}
            className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === 'zip'
                ? 'border-emerald-500 text-emerald-400'
                : 'border-transparent text-[#8b949e] hover:text-[#c9d1d9]'
            }`}
          >
            <Upload className="w-4 h-4" />
            Upload ZIP Archive
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
              Repository Name
            </label>
            <input
              type="text"
              placeholder="e.g. ecommerce-backend"
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
              className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] px-3.5 py-2.5 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
            />
          </div>

          {activeTab === 'github' ? (
            <>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                  GitHub Repository URL <span className="text-rose-400">*</span>
                </label>
                <input
                  type="url"
                  required
                  placeholder="https://github.com/owner/repository"
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                  className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] px-3.5 py-2.5 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                    Branch
                  </label>
                  <input
                    type="text"
                    placeholder="main"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] px-3.5 py-2.5 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                    Access Token (Optional)
                  </label>
                  <input
                    type="password"
                    placeholder="ghp_xxxxxxxxxxxx"
                    value={accessToken}
                    onChange={(e) => setAccessToken(e.target.value)}
                    className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] px-3.5 py-2.5 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
                  />
                </div>
              </div>
            </>
          ) : (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                Upload Repository ZIP <span className="text-rose-400">*</span>
              </label>
              <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-[#30363d] border-dashed rounded-lg bg-[#0d1117]">
                <div className="space-y-2 text-center">
                  <Upload className="mx-auto h-8 w-8 text-[#8b949e]" />
                  <div className="flex text-xs text-[#8b949e]">
                    <label className="relative cursor-pointer rounded-md font-medium text-emerald-400 hover:text-emerald-300">
                      <span>Select ZIP file</span>
                      <input
                        type="file"
                        accept=".zip"
                        className="sr-only"
                        onChange={(e) => {
                          if (e.target.files && e.target.files[0]) {
                            setZipFile(e.target.files[0]);
                          }
                        }}
                      />
                    </label>
                    <p className="pl-1">or drag and drop</p>
                  </div>
                  <p className="text-[11px] text-[#8b949e]">ZIP up to 100MB (safe decompression)</p>
                  {zipFile && (
                    <div className="text-xs font-mono text-emerald-400 pt-1 font-semibold">
                      Selected: {zipFile.name} ({(zipFile.size / 1024 / 1024).toFixed(2)} MB)
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Modal Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-[#30363d]">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 rounded-lg text-xs font-medium text-[#c9d1d9] hover:bg-[#21262d] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-black font-semibold text-xs flex items-center gap-1.5 transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Registering...
                </>
              ) : (
                'Add & Start Indexing'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
