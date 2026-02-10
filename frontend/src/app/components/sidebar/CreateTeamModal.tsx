import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Check, Copy } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  Button,
  Input,
} from '@/app/components/ui';
import { useTeamStore } from '@/stores/teamStore';
import { cn } from '@/lib/utils';
import type { InviteLinkResponse } from '@/types';

interface CreateTeamModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateTeamModal({ open, onOpenChange }: CreateTeamModalProps) {
  const navigate = useNavigate();
  const { createTeam, generateInviteLink } = useTeamStore();

  const [teamName, setTeamName] = useState('');
  const [teamDescription, setTeamDescription] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [step, setStep] = useState<'create' | 'success'>('create');
  const [createdTeamId, setCreatedTeamId] = useState<string | null>(null);
  const [localInviteLink, setLocalInviteLink] = useState<InviteLinkResponse | null>(null);
  const [inviteLinkLoading, setInviteLinkLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!teamName.trim()) {
      setError('팀 이름을 입력해주세요.');
      return;
    }

    setError(null);
    setIsCreating(true);

    try {
      const team = await createTeam({
        name: teamName.trim(),
        description: teamDescription.trim() || undefined,
      });

      // 성공 시 2단계로 전환
      setCreatedTeamId(team.id);
      setStep('success');
      setTeamName('');
      setTeamDescription('');
    } catch (err) {
      setError('팀을 만들지 못했어요. 잠시 후 다시 시도해주세요.');
      console.error('Team creation error:', err);
    } finally {
      setIsCreating(false);
    }
  };

  const handleClose = () => {
    setError(null);
    setTeamName('');
    setTeamDescription('');
    setStep('create');
    setCreatedTeamId(null);
    setLocalInviteLink(null);
    setCopied(false);
    onOpenChange(false);
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

  const handleCopy = async () => {
    if (!localInviteLink) return;
    try {
      await navigator.clipboard.writeText(localInviteLink.inviteUrl);
      setCopied(true);
    } catch {
      setError('복사하지 못했어요. 링크를 직접 선택해 복사해주세요.');
    }
  };

  const handleRetryInviteLink = () => {
    if (!createdTeamId) return;
    setError(null);
    setInviteLinkLoading(true);
    generateInviteLink(createdTeamId)
      .then((link) => setLocalInviteLink(link))
      .catch(() => setError('초대 링크를 만들지 못했어요.'))
      .finally(() => setInviteLinkLoading(false));
  };

  const handleGoToTeam = () => {
    if (createdTeamId) {
      navigate(`/dashboard/teams/${createdTeamId}`);
      handleClose();
    }
  };

  // 초대링크 자동 생성
  useEffect(() => {
    if (step === 'success' && createdTeamId) {
      setInviteLinkLoading(true);
      generateInviteLink(createdTeamId)
        .then(async (link) => {
          setLocalInviteLink(link);
          try {
            await navigator.clipboard.writeText(link.inviteUrl);
            setCopied(true);
          } catch {
            // 자동 복사 실패는 무시 (수동 복사 가능)
          }
        })
        .catch(() => setError('초대 링크를 만들지 못했어요.'))
        .finally(() => setInviteLinkLoading(false));
    }
  }, [step, createdTeamId, generateInviteLink]);

  const inputBaseClasses =
    'w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-white/30 outline-none focus:border-mit-primary/50 focus:ring-2 focus:ring-mit-primary/20 transition-all';

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent variant="glass" className="max-w-md">
        {step === 'create' ? (
          <>
            <DialogHeader>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center">
                  <Users className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <DialogTitle className="text-white">새 팀 만들기</DialogTitle>
                  <DialogDescription className="text-white/50">
                    팀을 만들면 바로 회의를 시작할 수 있어요
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              {/* 팀 이름 */}
              <div>
                <label className="block text-sm font-medium text-white/70 mb-1.5">
                  팀 이름
                  <span className="text-mit-warning ml-1">*</span>
                </label>
                <Input
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                  placeholder="팀 이름을 입력해주세요 (예: 개발팀)"
                  className={inputBaseClasses}
                  disabled={isCreating}
                  required
                />
              </div>

              {/* 팀 설명 */}
              <div>
                <label className="block text-sm font-medium text-white/70 mb-1.5">
                  팀 설명
                </label>
                <textarea
                  value={teamDescription}
                  onChange={(e) => setTeamDescription(e.target.value)}
                  placeholder="팀에 대해 간단히 적어주세요"
                  rows={3}
                  disabled={isCreating}
                  className={cn(inputBaseClasses, 'resize-none')}
                />
              </div>

              {/* 에러 메시지 */}
              {error && (
                <div className="text-sm text-red-400 bg-red-400/10 px-3 py-2 rounded-lg">
                  {error}
                </div>
              )}

              {/* 액션 버튼 */}
              <div className="flex justify-end gap-3 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleClose}
                  disabled={isCreating}
                  className="text-white/40 hover:text-white/60 hover:bg-white/5"
                >
                  취소
                </Button>
                <Button
                  type="submit"
                  variant="default"
                  disabled={isCreating || !teamName.trim()}
                >
                  {isCreating ? '만드는 중...' : '팀 만들기'}
                </Button>
              </div>
            </form>
          </>
        ) : (
          <>
            <DialogHeader>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center">
                  <Check className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <DialogTitle className="text-white">팀이 만들어졌어요!</DialogTitle>
                  <DialogDescription className="text-white/50">
                    아래 링크를 팀원에게 공유해주세요
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            <div className="space-y-4 mt-4">
              {/* 에러 메시지 */}
              {error && (
                <div className="text-sm text-red-400 bg-red-400/10 px-3 py-2 rounded-lg">
                  {error}
                </div>
              )}

              {/* 초대링크 영역 */}
              <div>
                <label className="block text-sm font-medium text-white/70 mb-1.5">
                  초대 링크
                </label>
                {inviteLinkLoading ? (
                  <div className="h-10 bg-white/5 rounded-lg animate-pulse" />
                ) : error && !localInviteLink ? (
                  <Button
                    variant="ghost"
                    onClick={handleRetryInviteLink}
                    className="w-full"
                  >
                    다시 시도
                  </Button>
                ) : localInviteLink ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={localInviteLink.inviteUrl}
                        readOnly
                        className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm font-mono truncate"
                      />
                      <Button
                        variant={copied ? 'glass' : 'default'}
                        size="sm"
                        onClick={handleCopy}
                        className={cn(
                          'flex-shrink-0 transition-colors',
                          copied && 'text-green-400 border-green-500/30 bg-green-500/10 hover:bg-green-500/15'
                        )}
                      >
                        {copied ? (
                          <>
                            <Check className="w-4 h-4" />
                            복사됨!
                          </>
                        ) : (
                          <>
                            <Copy className="w-4 h-4" />
                            복사
                          </>
                        )}
                      </Button>
                    </div>
                    <p className="text-xs text-white/50">
                      {formatExpiresAt(localInviteLink.expiresAt)}
                    </p>
                  </div>
                ) : null}
              </div>

              {/* 액션 버튼 */}
              <div className="flex justify-end gap-3 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleClose}
                  className="text-white/40 hover:text-white/60 hover:bg-white/5"
                >
                  닫기
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleGoToTeam}
                >
                  팀 페이지로 이동
                </Button>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
