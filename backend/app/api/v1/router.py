from fastapi import APIRouter

from app.api.v1.endpoints import (
    agent,
    auth,
    chat,
    decisions,
    livekit_webhooks,
    meeting_participants,
    meetings,
    recordings,
    team_members,
    teams,
    transcripts,
    transcripts_,
    webrtc,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(agent.router)
api_router.include_router(auth.router)
api_router.include_router(teams.router)
api_router.include_router(team_members.router)
api_router.include_router(meetings.team_meetings_router)
api_router.include_router(meetings.router)
api_router.include_router(meeting_participants.router)
api_router.include_router(webrtc.router)
api_router.include_router(recordings.router)
api_router.include_router(transcripts.router)
api_router.include_router(transcripts_.router)
api_router.include_router(chat.router)
api_router.include_router(livekit_webhooks.router)
api_router.include_router(decisions.router)
api_router.include_router(decisions.meetings_decisions_router)
