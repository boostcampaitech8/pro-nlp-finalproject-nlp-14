// 회의 생성 모달 컴포넌트
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, Users } from 'lucide-react';
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

interface MeetingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialData?: {
    title?: string;
    description?: string;
    scheduledAt?: string;
    teamId?: string;
  };
}

export function MeetingModal({ open, onOpenChange, initialData }: MeetingModalProps) {
  const navigate = useNavigate();
  const { teams, fetchTeams, createMeeting, meetingsLoading } = useTeamStore();

  const [title, setTitle] = useState(initialData?.title || '');
  const [description, setDescription] = useState(initialData?.description || '');
  const [scheduledAt, setScheduledAt] = useState(initialData?.scheduledAt || '');
  const [selectedTeamId, setSelectedTeamId] = useState(initialData?.teamId || '');
  const [error, setError] = useState<string | null>(null);

  // 팀 목록 로드
  useEffect(() => {
    if (open && teams.length === 0) {
      fetchTeams();
    }
  }, [open, teams.length, fetchTeams]);

  // 첫 번째 팀 자동 선택
  useEffect(() => {
    if (teams.length > 0 && !selectedTeamId) {
      setSelectedTeamId(teams[0].id);
    }
  }, [teams, selectedTeamId]);

  // initialData 변경 시 폼 업데이트
  useEffect(() => {
    if (initialData) {
      setTitle(initialData.title || '');
      setDescription(initialData.description || '');
      setScheduledAt(initialData.scheduledAt || '');
      if (initialData.teamId) {
        setSelectedTeamId(initialData.teamId);
      }
    }
  }, [initialData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      setError('회의 제목을 입력해주세요.');
      return;
    }

    if (!selectedTeamId) {
      setError('팀을 선택해주세요.');
      return;
    }

    setError(null);

    try {
      const meeting = await createMeeting(selectedTeamId, {
        title: title.trim(),
        description: description.trim() || undefined,
        scheduledAt: scheduledAt || undefined,
      });

      // 모달 닫기
      onOpenChange(false);

      // 폼 초기화
      setTitle('');
      setDescription('');
      setScheduledAt('');

      // 회의실로 이동
      navigate(`/dashboard/meetings/${meeting.id}/room`);
    } catch (err) {
      setError('회의 생성에 실패했습니다. 다시 시도해주세요.');
      console.error('Meeting creation error:', err);
    }
  };

  const handleClose = () => {
    setError(null);
    onOpenChange(false);
  };

  const inputBaseClasses =
    'w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-white/30 outline-none focus:border-mit-primary/50 focus:ring-2 focus:ring-mit-primary/20 transition-all';

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent variant="glass" className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-mit-primary/20 to-mit-secondary/20 flex items-center justify-center">
              <span className="text-xl">🎯</span>
            </div>
            <div>
              <DialogTitle className="text-white">새 회의 만들기</DialogTitle>
              <DialogDescription className="text-white/50">
                회의 정보를 입력하고 바로 시작하세요
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          {/* 팀 선택 */}
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">
              <Users className="w-4 h-4 inline-block mr-1.5" />
              팀 선택
              <span className="text-mit-warning ml-1">*</span>
            </label>
            <select
              value={selectedTeamId}
              onChange={(e) => setSelectedTeamId(e.target.value)}
              className={cn(inputBaseClasses, 'cursor-pointer')}
              required
            >
              <option value="" className="bg-slate-800">
                팀을 선택하세요
              </option>
              {teams.map((team) => (
                <option key={team.id} value={team.id} className="bg-slate-800">
                  {team.name}
                </option>
              ))}
            </select>
          </div>

          {/* 회의 제목 */}
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">
              회의 제목
              <span className="text-mit-warning ml-1">*</span>
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="예: 주간 팀 미팅"
              className={inputBaseClasses}
              required
            />
          </div>

          {/* 회의 설명 */}
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">
              회의 안건
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="회의에서 다룰 주요 안건을 입력하세요"
              rows={3}
              className={cn(inputBaseClasses, 'resize-none')}
            />
          </div>

          {/* 예정 시간 */}
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">
              <Calendar className="w-4 h-4 inline-block mr-1.5" />
              예정 시간
            </label>
            <input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              className={inputBaseClasses}
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
              disabled={meetingsLoading}
            >
              취소
            </Button>
            <Button
              type="submit"
              variant="glass-primary"
              disabled={meetingsLoading || !title.trim() || !selectedTeamId}
            >
              {meetingsLoading ? '생성 중...' : '회의 시작'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
