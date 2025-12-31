import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { LoginForm } from '@/components/auth/LoginForm';
import { useAuth } from '@/hooks/useAuth';

export function LoginPage() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Mit</h1>
          <p className="mt-2 text-gray-600">Welcome back! Please login to continue.</p>
        </div>

        <div className="bg-white p-8 rounded-xl shadow-md">
          <LoginForm />
        </div>
      </div>
    </div>
  );
}
