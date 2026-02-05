from fastapi import APIRouter

from app.api.v1.endpoints import (
    action_items,
    activity_logs,
    agendas,
    agent,
    auth,
    chat,
    comments,
    context,
    decisions,
    invite_links,
    livekit_webhooks,
    meeting_participants,
    meetings,
    minutes,
    spotlight,
    suggestions,
    team_members,
    teams,
    transcripts,
    webrtc,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(agent.router)
api_router.include_router(auth.router)
api_router.include_router(teams.router)
api_router.include_router(team_members.router)
api_router.include_router(invite_links.router)
api_router.include_router(invite_links.public_router)
api_router.include_router(meetings.team_meetings_router)
api_router.include_router(meetings.router)
api_router.include_router(meeting_participants.router)
api_router.include_router(webrtc.router)
api_router.include_router(transcripts.router)
api_router.include_router(chat.router)
api_router.include_router(livekit_webhooks.router)
api_router.include_router(decisions.router)
api_router.include_router(decisions.meetings_decisions_router)

# KG CRUD API - Phase 4
api_router.include_router(comments.router)
api_router.include_router(comments.decisions_comments_router)
api_router.include_router(suggestions.decisions_suggestions_router)
api_router.include_router(agendas.router)
api_router.include_router(action_items.router)
api_router.include_router(minutes.meetings_minutes_router)

# Context API - Real-time topic feed
api_router.include_router(context.router)

# Activity Logs API - User activity tracking
api_router.include_router(activity_logs.router)
# Spotlight API - Independent text chat
api_router.include_router(spotlight.router)
