import React, { useState } from 'react';
import { Outlet, Navigate, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { AddRepoModal } from '../features/repositories/AddRepoModal';
import { useAuth } from '../features/auth/AuthContext';
import { Loader2 } from 'lucide-react';

export const MainLayout: React.FC = () => {
  const { isAuthenticated, loading } = useAuth();
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="h-screen w-screen bg-[#0d1117] flex items-center justify-center text-xs text-[#8b949e] gap-2">
        <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
        Initializing RepoSage...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen w-screen bg-[#0d1117] text-[#c9d1d9] overflow-hidden">
      {/* Fixed Sidebar */}
      <Sidebar onOpenAddModal={() => setIsAddModalOpen(true)} />

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto bg-[#0d1117]">
        <Outlet context={{ openAddModal: () => setIsAddModalOpen(true) }} />
      </main>

      {/* Global Add Repository Modal */}
      <AddRepoModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={(repo) => {
          navigate(`/repositories/${repo.id}`);
        }}
      />
    </div>
  );
};
