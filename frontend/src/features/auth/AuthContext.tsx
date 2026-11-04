import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../../types';
import { api } from '../../api/client';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem('reposage_access_token');
        if (token) {
          const profile = await api.getMe();
          setUser(profile);
        } else {
          // Check if server provides a demo user fallback
          try {
            const profile = await api.getMe();
            setUser(profile);
          } catch {
            setUser(null);
          }
        }
      } catch (err) {
        localStorage.removeItem('reposage_access_token');
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    checkAuth();
  }, []);

  const login = async (email: string, pass: string) => {
    const data = await api.login(email, pass);
    localStorage.setItem('reposage_access_token', data.access_token);
    const profile = await api.getMe();
    setUser(profile);
  };

  const register = async (email: string, pass: string) => {
    await api.register(email, pass);
    await login(email, pass);
  };

  const logout = () => {
    localStorage.removeItem('reposage_access_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
