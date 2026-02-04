import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';

import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { teamService } from '@/services/teamService';
import { useTeamStore } from '@/stores/teamStore';
import type { InvitePreviewResponse } from '@/types';

export function InviteAcceptPage() {
  const { inviteCode } = useParams<{ inviteCode: string }>();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const { acceptInvite } = useTeamStore();

  const [preview, setPreview] = useState<InvitePreviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!inviteCode) return;

    const fetchPreview = async () => {
      setLoading(true);
      try {
        const data = await teamService.previewInvite(inviteCode);
        setPreview(data);
      } catch {
        setError('초대 링크가 만료되었거나 유효하지 않습니다.');
      } finally {
        setLoading(false);
      }
    };

    fetchPreview();
  }, [inviteCode]);

  const handleJoin = async () => {
    if (!inviteCode) return;

    setJoining(true);
    setError(null);
    try {
      const result = await acceptInvite(inviteCode);
      navigate(`/dashboard/teams/${result.teamId}`, { replace: true });
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.data?.detail?.message) {
        setError(err.response.data.detail.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('팀 가입에 실패했습니다.');
      }
      setJoining(false);
    }
  };

  const handleLoginAndJoin = () => {
    if (inviteCode) {
      sessionStorage.setItem('pendingInviteCode', inviteCode);
    }
    navigate('/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen gradient-bg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-mit-primary mx-auto mb-4" />
          <p className="text-white/60">초대 정보를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error && !preview) {
    return (
      <div className="min-h-screen gradient-bg flex items-center justify-center">
        <div className="glass-card p-8 max-w-md w-full mx-4 text-center">
          <div className="text-red-400 text-5xl mb-4">!</div>
          <h2 className="text-xl font-bold text-white mb-2">유효하지 않은 초대</h2>
          <p className="text-white/60 mb-6">{error}</p>
          <Button onClick={() => navigate(isAuthenticated ? '/dashboard' : '/login')}>
            {isAuthenticated ? '대시보드로 이동' : '로그인 페이지로 이동'}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen gradient-bg flex items-center justify-center">
      <div className="glass-card p-8 max-w-md w-full mx-4">
        <div className="text-center mb-6">
          <h2 className="text-2xl font-bold text-white mb-2">팀 초대</h2>
          <p className="text-white/60">다음 팀에 초대되었습니다</p>
        </div>

        {preview && (
          <div className="bg-white/5 rounded-lg p-4 mb-6 space-y-2">
            <h3 className="text-lg font-semibold text-white">{preview.teamName}</h3>
            {preview.teamDescription && (
              <p className="text-white/60 text-sm">{preview.teamDescription}</p>
            )}
            <p className="text-white/40 text-sm">
              멤버 {preview.memberCount}/{preview.maxMembers}명
            </p>
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        {isAuthenticated ? (
          <div className="space-y-3">
            {user && (
              <p className="text-white/60 text-sm text-center">
                <strong className="text-white">{user.name}</strong>({user.email})으로 가입합니다
              </p>
            )}
            <Button
              onClick={handleJoin}
              isLoading={joining}
              className="w-full"
            >
              팀 가입하기
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-white/60 text-sm text-center">
              팀에 가입하려면 먼저 로그인해주세요
            </p>
            <Button
              onClick={handleLoginAndJoin}
              className="w-full"
            >
              로그인하여 가입하기
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
