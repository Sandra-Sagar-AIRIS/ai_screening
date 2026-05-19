"""
LiveKit service — room name derivation and access token generation.

LiveKit tokens are short-lived signed JWTs that grant a specific user access
to a specific room.  They are generated server-side using the API secret and
sent to the frontend, which uses them to connect directly to the LiveKit
server over WebSocket (no further backend involvement in the media path).

Setup (add to backend/.env):
  LIVEKIT_API_KEY=APIxxxxxxxxxxxxxxx
  LIVEKIT_API_SECRET=<your-secret>
  LIVEKIT_WS_URL=wss://your-project.livekit.cloud   # canonical name
  # LIVEKIT_URL=wss://...                            # also accepted as alias

LiveKit Cloud free tier: https://cloud.livekit.io
Self-hosted docs:        https://docs.livekit.io/home/self-hosting/local/

Dependency: livekit-api (already installed)
"""
from __future__ import annotations

from datetime import timedelta
from uuid import UUID


def get_room_name(interview_id: UUID) -> str:
    """Derive a stable, URL-safe LiveKit room name from the interview ID."""
    return f"airis-interview-{interview_id}"


def generate_token(
    api_key: str,
    api_secret: str,
    room_name: str,
    participant_identity: str,
    participant_name: str,
    ttl_seconds: int = 14400,  # 4 hours — long enough for any interview
) -> str:
    """
    Generate a LiveKit access token granting room join permission.

    Uses ``livekit-api`` (installed via pip).
    The token is returned as a signed JWT string ready for the frontend SDK.
    """
    from livekit.api import AccessToken, VideoGrants  # noqa: PLC0415

    token = (
        AccessToken(api_key, api_secret)
        .with_identity(participant_identity)
        .with_name(participant_name)
        .with_ttl(timedelta(seconds=ttl_seconds))
        .with_grants(VideoGrants(room_join=True, room=room_name))
    )
    return token.to_jwt()
