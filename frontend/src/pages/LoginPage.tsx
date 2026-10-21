import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Code2, Lock, Mail, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '../features/auth/AuthContext';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(email, password);
      navigate('/');
    } catch (err: any) {
      console.error('Login failed:', err);
      setError(err.response?.data?.message || err.message || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0d1117] flex flex-col justify-center items-center px-4 select-none">
      <div className="w-full max-w-sm space-y-6">
        {/* Brand */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center mx-auto">
            <Code2 className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight">Sign in to RepoSage</h1>
          <p className="text-xs text-[#8b949e]">Understand, debug, and navigate any codebase with AI</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-[#30363d] bg-[#161b22] p-6 shadow-xl space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-[#8b949e] absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  placeholder="developer@reposage.dev"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] pl-9 pr-3.5 py-2.5 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b949e] mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-[#8b949e] absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] pl-9 pr-3.5 py-2.5 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-black font-semibold text-xs flex items-center justify-center gap-2 transition-colors shadow-sm"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Sign In'}
            </button>
          </form>

          {/* Quick Demo Fill Button */}
          <div className="pt-2 border-t border-[#30363d]/60 text-center">
            <button
              type="button"
              onClick={() => {
                setEmail('demo@reposage.dev');
                setPassword('RepoSage123!');
              }}
              className="text-[11px] text-emerald-400 hover:text-emerald-300 font-medium"
            >
              Click to use Demo Credentials
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-[#8b949e]">
          Don't have an account?{' '}
          <Link to="/register" className="text-emerald-400 hover:underline font-medium">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
};
