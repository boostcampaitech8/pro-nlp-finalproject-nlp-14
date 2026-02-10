// 추천 명령어 컴포넌트
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Video, Search, Calendar, Users, HelpCircle, ArrowRight, type LucideIcon } from 'lucide-react';
import { useCommandStore } from '@/app/stores/commandStore';
import { useTeamStore } from '@/stores/teamStore';
import { useCommand } from '@/app/hooks/useCommand';
import { SUGGESTIONS_DISPLAY_LIMIT } from '@/app/constants';
import { InlineMeetingForm } from './InlineMeetingForm';
import { InlineTeamForm } from './InlineTeamForm';
import type { Suggestion } from '@/app/types/command';

// 아이콘 이름 -> Lucide 컴포넌트 매핑
const iconMap: Record<string, LucideIcon> = {
  video: Video,
  search: Search,
  calendar: Calendar,
  users: Users,
  help: HelpCircle,
};

type CardVariant = 'primary' | 'accent' | 'default';

interface SuggestionCardProps {
  suggestion: Suggestion;
  variant?: CardVariant;
  expanded?: boolean;
  onSelect: (command: string, category?: string) => void;
  children?: React.ReactNode;
}

const variantStyles: Record<CardVariant, {
  card: string;
  icon: string;
  title: string;
  desc: string;
}> = {
  primary: {
    card: 'bg-gradient-to-br from-mit-primary/20 via-purple-500/15 to-purple-600/5 border-purple-400/25 shadow-[0_4px_20px_rgba(168,85,247,0.1)] hover:border-purple-400/40 hover:shadow-[0_16px_48px_rgba(168,85,247,0.2)]',
    icon: 'bg-gradient-to-br from-mit-primary to-mit-purple shadow-[0_0_16px_rgba(168,85,247,0.25)] group-hover:shadow-[0_0_28px_rgba(168,85,247,0.4)]',
    title: 'text-white/50',
    desc: 'text-white font-medium group-hover:text-white',
  },
  accent: {
    card: 'bg-gradient-to-br from-sky-500/10 via-cyan-500/5 to-transparent border-sky-400/15 hover:border-sky-400/30 hover:shadow-[0_12px_36px_rgba(56,189,248,0.1)]',
    icon: 'bg-sky-500/15 border border-sky-400/20 group-hover:bg-sky-500/25 group-hover:border-sky-400/30',
    title: 'text-white/45 group-hover:text-white/60',
    desc: 'text-white/80 font-medium group-hover:text-white',
  },
  default: {
    card: 'bg-white/[0.03] border-white/[0.06] hover:bg-purple-500/[0.08] hover:border-purple-400/20 hover:shadow-[0_12px_36px_rgba(168,85,247,0.12)]',
    icon: 'bg-white/[0.06] border border-white/[0.08] group-hover:bg-purple-500/15 group-hover:border-purple-400/20',
    title: 'text-white/40 group-hover:text-white/55',
    desc: 'text-white/70 font-medium group-hover:text-white/90',
  },
};

function SuggestionCard({ suggestion, variant = 'default', expanded, onSelect, children }: SuggestionCardProps) {
  const IconComponent = iconMap[suggestion.icon];
  const styles = variantStyles[variant];

  const glowOverlay = (
    <div className="absolute inset-0 rounded-xl overflow-hidden pointer-events-none">
      <div className="absolute -inset-full w-[200%] h-[200%] opacity-0 group-hover:animate-[glow-sweep_0.6s_ease-out_forwards] bg-gradient-to-br from-transparent via-purple-400/15 to-transparent" />
    </div>
  );

  return (
    <motion.div
      layout
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className={expanded ? 'col-span-1 sm:col-span-3' : ''}
    >
      <button
        onClick={() => !expanded && onSelect(suggestion.command, suggestion.category)}
        className={`relative w-full p-4 rounded-xl backdrop-blur-lg border ${styles.card} ${!expanded ? 'hover:-translate-y-1' : ''} transition-all duration-300 text-left group ${expanded ? '' : 'overflow-hidden'}`}
      >
        {glowOverlay}
        <div className="relative flex items-start gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-all duration-300 ${styles.icon}`}>
            {IconComponent ? (
              <IconComponent className="w-4 h-4 text-white/80" />
            ) : (
              <span className="text-lg">{suggestion.icon}</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className={`text-[11px] mb-1 transition-colors duration-200 ${styles.title}`}>
              {suggestion.title}
            </h3>
            <p className={`text-sm leading-snug transition-colors duration-200 line-clamp-2 ${styles.desc}`}>
              {suggestion.description}
            </p>
          </div>
          {variant === 'primary' && !expanded && (
            <ArrowRight className="w-4 h-4 text-white/30 group-hover:text-white/60 group-hover:translate-x-1 transition-all duration-300 flex-shrink-0" />
          )}
        </div>

        {/* 인라인 폼 영역 */}
        <AnimatePresence>
          {expanded && children && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
              className="overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              {children}
            </motion.div>
          )}
        </AnimatePresence>
      </button>
    </motion.div>
  );
}

export function CommandSuggestions() {
  const { suggestions } = useCommandStore();
  const { submitCommand } = useCommand();
  const { teams, teamsLoading } = useTeamStore();

  const [expandedId, setExpandedId] = useState<string | null>(null);
  // 카드 확장 시점의 폼 타입을 고정 (팀 생성 후 자동 전환 방지)
  const [expandedForm, setExpandedForm] = useState<'meeting' | 'team' | null>(null);

  const hasTeams = !teamsLoading && teams.length > 0;

  const handleSelect = (command: string, category?: string) => {
    if (category === 'meeting') {
      const meetingSuggestion = displaySuggestions.find((s) => s.category === 'meeting');
      if (meetingSuggestion) {
        const isClosing = expandedId === meetingSuggestion.id;
        setExpandedId(isClosing ? null : meetingSuggestion.id);
        setExpandedForm(isClosing ? null : (hasTeams ? 'meeting' : 'team'));
      }
      return;
    }
    submitCommand(command);
  };

  const displaySuggestions = suggestions.slice(0, SUGGESTIONS_DISPLAY_LIMIT).map((s) => {
    if (s.category === 'meeting' && !hasTeams) {
      return { ...s, title: '팀 만들기', description: '팀을 만들면 바로 회의를 시작할 수 있어요', icon: 'users' };
    }
    return s;
  });

  if (displaySuggestions.length === 0) {
    return null;
  }

  // 확장된 카드를 맨 앞으로 정렬 → 상단에 렌더링
  const sortedSuggestions = expandedId
    ? [
        ...displaySuggestions.filter((s) => s.id === expandedId),
        ...displaySuggestions.filter((s) => s.id !== expandedId),
      ]
    : displaySuggestions;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <h2 className="text-section-header text-center mb-4">
        무엇을 도와드릴까요?
      </h2>

      <motion.div
        layout
        className={
          expandedId
            ? 'grid grid-cols-1 sm:grid-cols-3 gap-3'
            : 'grid grid-cols-1 sm:grid-cols-2 gap-3'
        }
      >
        {sortedSuggestions.map((suggestion) => {
          const isMeetingCategory = suggestion.category === 'meeting';
          const isExpanded = expandedId === suggestion.id;
          const variant: CardVariant = isMeetingCategory
            ? 'primary'
            : suggestion.category === 'help'
              ? 'accent'
              : 'default';

          return (
            <SuggestionCard
              key={suggestion.id}
              suggestion={suggestion}
              variant={variant}
              expanded={isExpanded}
              onSelect={handleSelect}
            >
              {isMeetingCategory && isExpanded && (
                expandedForm === 'meeting' ? (
                  <InlineMeetingForm onClose={() => { setExpandedId(null); setExpandedForm(null); }} />
                ) : (
                  <InlineTeamForm onClose={() => { setExpandedId(null); setExpandedForm(null); }} />
                )
              )}
            </SuggestionCard>
          );
        })}
      </motion.div>
    </div>
  );
}
