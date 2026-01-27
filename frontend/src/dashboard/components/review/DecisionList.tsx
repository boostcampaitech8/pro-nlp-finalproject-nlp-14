/**
 * Agenda별 Decision 목록 컴포넌트
 *
 * 아젠다별로 결정사항 그룹화하여 표시
 */

import type { PRAgenda, PRParticipant } from '@/types';
import { DecisionCard } from './DecisionCard';

interface DecisionListProps {
  agendas: PRAgenda[];
  currentUserId?: string;
  participants: PRParticipant[];
}

export function DecisionList({
  agendas,
  currentUserId,
  participants,
}: DecisionListProps) {
  if (agendas.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No decisions to review.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {agendas.map((agenda, index) => (
        <div key={agenda.id} className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
              Agenda {index + 1}
            </span>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            {agenda.topic}
          </h3>

          {agenda.decisions.length === 0 ? (
            <p className="text-gray-500 text-sm">
              No decisions for this agenda.
            </p>
          ) : (
            <div className="space-y-4">
              {agenda.decisions.map((decision) => (
                <DecisionCard
                  key={decision.id}
                  decision={decision}
                  currentUserId={currentUserId}
                  participants={participants}
                />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
