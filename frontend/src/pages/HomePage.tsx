import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';

export function HomePage() {
  const { user, logout, isLoading } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">Mit</h1>

          <div className="flex items-center gap-4">
            {user && (
              <span className="text-gray-600">
                Hello, <strong>{user.name}</strong>
              </span>
            )}
            <Button variant="outline" onClick={logout} isLoading={isLoading}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="bg-white rounded-xl shadow-md p-8 text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            Welcome to Mit
          </h2>
          <p className="text-gray-600 mb-6">
            Git manages the truth of code. Mit manages the truth of organizational meetings.
          </p>
          <p className="text-sm text-gray-500">
            Meeting features coming soon...
          </p>
        </div>
      </main>
    </div>
  );
}
