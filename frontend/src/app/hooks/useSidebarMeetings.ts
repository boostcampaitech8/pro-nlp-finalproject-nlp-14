import { useState, useEffect, useCallback } from 'react';
import { meetingService } from '@/services/meetingService';
import type { Meeting, Team } from '@/types';

export interface SidebarMeeting extends Meeting {
  teamName: string;
}

export function useSidebarMeetings(teams: Team[]) {
  const [meetings, setMeetings] = useState<SidebarMeeting[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchAll = useCallback(async () => {
    if (teams.length === 0) {
      setMeetings([]);
      return;
    }

    setIsLoading(true);
    try {
      const results = await Promise.all(
        teams.map((team) =>
          meetingService
            .listTeamMeetings(team.id, 1, 50)
            .then((res) =>
              res.items
                .filter((m) => m.status === 'scheduled' || m.status === 'ongoing')
                .map((m) => ({ ...m, teamName: team.name })),
            )
            .catch(() => [] as SidebarMeeting[]),
        ),
      );

      const all = results.flat();
      // ongoing 먼저, 그 다음 scheduled (최신순)
      all.sort((a, b) => {
        if (a.status === 'ongoing' && b.status !== 'ongoing') return -1;
        if (a.status !== 'ongoing' && b.status === 'ongoing') return 1;
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      });

      setMeetings(all);
    } finally {
      setIsLoading(false);
    }
  }, [teams]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { meetings, isLoading, refetch: fetchAll };
}
