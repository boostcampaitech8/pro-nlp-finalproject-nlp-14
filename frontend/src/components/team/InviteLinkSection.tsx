import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { useTeamStore } from '@/stores/teamStore';

interface InviteLinkSectionProps {
  teamId: string;
  canManageMembers: boolean;
}

export function InviteLinkSection({ teamId, canManageMembers }: InviteLinkSectionProps) {
  const {
    inviteLink,
    inviteLinkLoading,
    generateInviteLink,
    fetchInviteLink,
    deactivateInviteLink,
  } = useTeamStore();

  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchInviteLink(teamId);
  }, [teamId, fetchInviteLink]);

  const handleGenerate = async () => {
    setError(null);
    try {
      await generateInviteLink(teamId);
    } catch {
      setError('초대 링크 생성에 실패했습니다.');
    }
  };

  const handleDeactivate = async () => {
    if (!confirm('초대 링크를 비활성화하시겠습니까?')) return;
    setError(null);
    try {
      await deactivateInviteLink(teamId);
    } catch {
      setError('초대 링크 비활성화에 실패했습니다.');
    }
  };

  const handleCopy = async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink.inviteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('클립보드 복사에 실패했습니다.');
    }
  };

  const formatExpiresAt = (expiresAt: string) => {
    const expires = new Date(expiresAt);
    const now = new Date();
    const diffMs = expires.getTime() - now.getTime();

    if (diffMs <= 0) return '만료됨';

    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `${diffMin}분 후 만료`;
    const diffHour = Math.floor(diffMin / 60);
    return `${diffHour}시간 ${diffMin % 60}분 후 만료`;
  };

  if (!canManageMembers) return null;

  return (
    <div className="mt-6">
      <h4 className="text-lg font-semibold text-white mb-3">Invite Link</h4>

      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}

      {inviteLink ? (
        <div className="glass-card p-4 space-y-3">
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={inviteLink.inviteUrl}
              className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm font-mono truncate"
            />
            <Button
              variant="outline"
              onClick={handleCopy}
              className="shrink-0"
            >
              {copied ? 'Copied!' : 'Copy'}
            </Button>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-white/50">
              {formatExpiresAt(inviteLink.expiresAt)}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={handleGenerate}
                isLoading={inviteLinkLoading}
                className="text-sm"
              >
                Regenerate
              </Button>
              <Button
                variant="outline"
                onClick={handleDeactivate}
                isLoading={inviteLinkLoading}
                className="text-sm text-red-400 border-red-500/30 hover:bg-red-500/20"
              >
                Deactivate
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <Button
          onClick={handleGenerate}
          isLoading={inviteLinkLoading}
        >
          Generate Invite Link
        </Button>
      )}
    </div>
  );
}
