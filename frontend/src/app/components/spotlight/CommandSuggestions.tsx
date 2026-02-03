// 추천 명령어 컴포넌트
import { Video, Search, Calendar, Users, type LucideIcon } from 'lucide-react';
import { useCommandStore } from '@/app/stores/commandStore';
import { useCommand } from '@/app/hooks/useCommand';
import { SUGGESTIONS_DISPLAY_LIMIT } from '@/app/constants';
import type { Suggestion } from '@/app/types/command';

// 아이콘 이름 -> Lucide 컴포넌트 매핑
const iconMap: Record<string, LucideIcon> = {
  video: Video,
  search: Search,
  calendar: Calendar,
  users: Users,
};

interface SuggestionCardProps {
  suggestion: Suggestion;
  onSelect: (command: string) => void;
}

function SuggestionCard({ suggestion, onSelect }: SuggestionCardProps) {
  const IconComponent = iconMap[suggestion.icon];

  return (
    <button
      onClick={() => onSelect(suggestion.command)}
      className="glass-card-hover p-4 text-left w-full group"
    >
      <div className="flex items-start gap-3">
        <div className="icon-container-sm flex-shrink-0 group-hover:scale-105 transition-transform">
          {IconComponent ? (
            <IconComponent className="w-5 h-5 text-mit-primary" />
          ) : (
            <span className="text-lg">{suggestion.icon}</span>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-card-title mb-1 group-hover:text-mit-primary transition-colors">
            {suggestion.title}
          </h3>
          <p className="text-card-desc line-clamp-2">
            {suggestion.description}
          </p>
        </div>
      </div>
    </button>
  );
}

export function CommandSuggestions() {
  const { suggestions } = useCommandStore();
  const { submitCommand } = useCommand();

  const handleSelect = (command: string) => {
    submitCommand(command);
  };

  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div className="w-full max-w-4xl mx-auto">
      <h2 className="text-section-header text-center mb-4">
        빠른 명령
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {suggestions.slice(0, SUGGESTIONS_DISPLAY_LIMIT).map((suggestion) => (
          <SuggestionCard
            key={suggestion.id}
            suggestion={suggestion}
            onSelect={handleSelect}
          />
        ))}
      </div>
    </div>
  );
}
