import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useOutletContext } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './features/auth/AuthContext';
import { MainLayout } from './layouts/MainLayout';
import { DashboardPage } from './pages/DashboardPage';
import { RepoDetailsPage } from './pages/RepoDetailsPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';

const queryClient = new QueryClient();

// Wrapper to pass context to DashboardPage
const DashboardWrapper: React.FC = () => {
  const { openAddModal } = useOutletContext<{ openAddModal: () => void }>();
  return <DashboardPage onOpenAddModal={openAddModal} />;
};

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route element={<MainLayout />}>
              <Route path="/" element={<DashboardWrapper />} />
              <Route path="/repositories" element={<DashboardWrapper />} />
              <Route path="/repositories/:id" element={<RepoDetailsPage />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
