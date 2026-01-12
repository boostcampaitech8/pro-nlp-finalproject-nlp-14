import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/hooks/useAuth';
import { useTeamStore } from '@/stores/teamStore';
import logger from '@/utils/logger';

export function HomePage() {
  logger.log('[HomePage] Rendering...');
  const { user, logout, isLoading: authLoading } = useAuth();
  const {
    teams,
    teamsLoading,
    teamError,
    fetchTeams,
    createTeam,
  } = useTeamStore();
  logger.log('[HomePage] user:', user?.email || 'null', 'authLoading:', authLoading);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTeamName, setNewTeamName] = useState('');
  const [newTeamDescription, setNewTeamDescription] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchTeams();
  }, [fetchTeams]);

  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeamName.trim()) return;

    setCreating(true);
    try {
      await createTeam({
        name: newTeamName.trim(),
        description: newTeamDescription.trim() || undefined,
      });
      setNewTeamName('');
      setNewTeamDescription('');
      setShowCreateForm(false);
    } catch {
      // 에러는 스토어에서 처리
    } finally {
      setCreating(false);
    }
  };

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
            <Button variant="outline" onClick={logout} isLoading={authLoading}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">My Teams</h2>
          <Button onClick={() => setShowCreateForm(!showCreateForm)}>
            {showCreateForm ? 'Cancel' : 'Create Team'}
          </Button>
        </div>

        {/* 팀 생성 폼 */}
        {showCreateForm && (
          <div className="bg-white rounded-xl shadow-md p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">Create New Team</h3>
            <form onSubmit={handleCreateTeam} className="space-y-4">
              <Input
                label="Team Name"
                value={newTeamName}
                onChange={(e) => setNewTeamName(e.target.value)}
                placeholder="Enter team name"
                required
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description (optional)
                </label>
                <textarea
                  value={newTeamDescription}
                  onChange={(e) => setNewTeamDescription(e.target.value)}
                  placeholder="Enter team description (Shift+Enter: new line)"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" isLoading={creating}>
                  Create
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowCreateForm(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* 에러 메시지 */}
        {teamError && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-6">
            {teamError}
          </div>
        )}

        {/* 로딩 */}
        {teamsLoading && teams.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            Loading teams...
          </div>
        )}

        {/* 팀 목록 */}
        {!teamsLoading && teams.length === 0 ? (
          <div className="bg-white rounded-xl shadow-md p-8 text-center">
            <p className="text-gray-600 mb-4">
              You don't have any teams yet.
            </p>
            <Button onClick={() => setShowCreateForm(true)}>
              Create Your First Team
            </Button>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {teams.map((team) => (
              <Link
                key={team.id}
                to={`/teams/${team.id}`}
                className="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow"
              >
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {team.name}
                </h3>
                {team.description && (
                  <p className="text-gray-600 text-sm mb-4 line-clamp-2">
                    {team.description}
                  </p>
                )}
                <p className="text-xs text-gray-400">
                  Created {new Date(team.createdAt).toLocaleDateString()}
                </p>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
