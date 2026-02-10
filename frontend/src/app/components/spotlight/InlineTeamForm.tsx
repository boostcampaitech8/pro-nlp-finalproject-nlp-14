import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { X, Copy, Check, Loader2, ExternalLink } from 'lucide-react';
import { useTeamStore } from '@/stores/teamStore';
import { Button, Input } from '@/app/components/ui';
import type { InviteLinkResponse } from '@/types';

interface InlineTeamFormProps {
  onClose: () => void;
}

export function InlineTeamForm({ onClose }: InlineTeamFormProps) {
  const navigate = useNavigate();
  const { createTeam, generateInviteLink } = useTeamStore();

  const [teamName, setTeamName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 성공 상태
  const [createdTeamId, setCreatedTeamId] = useState<string | null>(null);
  const [inviteLink, setInviteLink] = useState<InviteLinkResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const canSubmit = Boolean(teamName.trim());

  const handleCreate = useCallback(async () => {
    if (!canSubmit) return;

    setIsCreating(true);
    setError(null);
    try {
      const team = await createTeam({ name: teamName.trim() });
      setCreatedTeamId(team.id);
    } catch {
      setError('팀을 만들지 못했어요. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsCreating(false);
    }
  }, [canSubmit, teamName, createTeam]);

  // 팀 생성 성공 시 초대 링크 자동 생성
  useEffect(() => {
    if (!createdTeamId) return;
    generateInviteLink(createdTeamId)
      .then(async (link) => {
        setInviteLink(link);
        try {
          await navigator.clipboard.writeText(link.inviteUrl);
          setCopied(true);
        } catch {
          // 자동 복사 실패 무시
        }
      })
      .catch(() => {
        // 초대 링크 생성 실패는 무시 (팀은 이미 생성됨)
      });
  }, [createdTeamId, generateInviteLink]);

  const handleCopy = useCallback(async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink.inviteUrl);
      setCopied(true);
    } catch {
      setError('복사하지 못했어요. 링크를 직접 선택해 복사해주세요.');
    }
  }, [inviteLink]);

  const handleGoToTeam = useCallback(() => {
    if (createdTeamId) {
      navigate(`/dashboard/teams/${createdTeamId}`);
    }
  }, [createdTeamId, navigate]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey && canSubmit && !isCreating && !createdTeamId) {
        e.preventDefault();
        handleCreate();
      }
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    },
    [canSubmit, isCreating, createdTeamId, handleCreate, onClose],
  );

  // 성공 상태
  if (createdTeamId) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="pt-4 pb-1 px-1 space-y-3"
      >
        <div className="flex items-center gap-2 text-sm text-green-400" role="status">
          <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center">
            <Check className="w-3 h-3" />
          </div>
          <span>팀이 만들어졌어요!</span>
        </div>

        {/* 초대 링크 */}
        {inviteLink && (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={inviteLink.inviteUrl}
              readOnly
              className="flex-1 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white/70 text-xs font-mono truncate outline-none"
            />
            <button
              onClick={handleCopy}
              className={`flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${
                copied
                  ? 'text-green-400 border-green-500/30 bg-green-500/10'
                  : 'text-white/60 border-white/10 bg-white/5 hover:bg-white/10'
              }`}
            >
              {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              {copied ? '복사됨' : '복사'}
            </button>
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="text-white/50 hover:text-white/70 hover:bg-white/5"
          >
            닫기
          </Button>
          <Button size="sm" onClick={handleGoToTeam} className="gap-1.5">
            팀 페이지로 이동
            <ExternalLink className="w-3.5 h-3.5" />
          </Button>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.1 }}
      className="pt-4 pb-1 px-1 space-y-3"
      onKeyDown={handleKeyDown}
    >
      {/* 팀명 입력 */}
      <Input
        value={teamName}
        onChange={(e) => setTeamName(e.target.value)}
        placeholder="팀 이름을 입력해주세요 (예: 개발팀)"
        autoFocus
        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 outline-none focus:border-purple-400/40 transition-colors"
      />

      {/* 에러 */}
      {error && (
        <p className="text-xs text-red-400" role="alert">{error}</p>
      )}

      {/* 액션 버튼 */}
      <div className="flex justify-end gap-2">
        <button
          onClick={onClose}
          className="flex items-center gap-1 px-3 py-1.5 text-xs text-white/40 hover:text-white/60 transition-colors rounded-lg hover:bg-white/5"
        >
          <X className="w-3 h-3" />
          취소
        </button>
        <Button
          size="sm"
          onClick={handleCreate}
          disabled={!canSubmit || isCreating}
          className="gap-1.5 text-xs"
        >
          {isCreating ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              만드는 중...
            </>
          ) : (
            '팀 만들기'
          )}
        </Button>
      </div>
    </motion.div>
  );
}
