from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    chat,
    meeting_participants,
    meetings,
    recordings,
    team_members,
    teams,
    transcripts,
    webrtc,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(teams.router)
api_router.include_router(team_members.router)
api_router.include_router(meetings.team_meetings_router)
api_router.include_router(meetings.router)
api_router.include_router(meeting_participants.router)
api_router.include_router(webrtc.router)
api_router.include_router(recordings.router)
api_router.include_router(transcripts.router)
api_router.include_router(chat.router)
