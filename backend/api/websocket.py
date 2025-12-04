"""
WebSocket Manager for Real-Time Score Broadcasting

Enables real-time score updates on the local network without polling.
Judges submit scores → Server broadcasts to all connected tabulators.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time score broadcasting.
    
    Supports:
    - Global broadcasts (all clients)
    - Competition-specific rooms (only clients watching that competition)
    - Graceful reconnection handling
    """
    
    def __init__(self):
        # All active connections
        self.active_connections: List[WebSocket] = []
        
        # Competition-specific subscriptions: competition_id -> set of connections
        self.competition_subscriptions: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, competition_id: str | None = None):
        """Accept a new WebSocket connection and optionally subscribe to a competition."""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if competition_id:
            await self.subscribe_to_competition(websocket, competition_id)
        
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection and clean up subscriptions."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from all competition subscriptions
        for comp_id in list(self.competition_subscriptions.keys()):
            self.competition_subscriptions[comp_id].discard(websocket)
            # Clean up empty rooms
            if not self.competition_subscriptions[comp_id]:
                del self.competition_subscriptions[comp_id]
        
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def subscribe_to_competition(self, websocket: WebSocket, competition_id: str):
        """Subscribe a connection to updates for a specific competition."""
        if competition_id not in self.competition_subscriptions:
            self.competition_subscriptions[competition_id] = set()
        
        self.competition_subscriptions[competition_id].add(websocket)
        logger.debug(f"Subscribed to competition {competition_id}")
    
    async def unsubscribe_from_competition(self, websocket: WebSocket, competition_id: str):
        """Unsubscribe a connection from a specific competition."""
        if competition_id in self.competition_subscriptions:
            self.competition_subscriptions[competition_id].discard(websocket)
    
    async def broadcast_to_competition(self, competition_id: str, message: dict):
        """Send a message to all clients subscribed to a specific competition."""
        if competition_id not in self.competition_subscriptions:
            return
        
        dead_connections = []
        
        for connection in self.competition_subscriptions[competition_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                dead_connections.append(connection)
        
        # Clean up dead connections
        for conn in dead_connections:
            self.disconnect(conn)
    
    async def broadcast_all(self, message: dict):
        """Send a message to all connected clients."""
        dead_connections = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                dead_connections.append(connection)
        
        # Clean up dead connections
        for conn in dead_connections:
            self.disconnect(conn)
    
    async def broadcast_score(self, score_data: dict):
        """
        Broadcast a new score submission.
        
        Args:
            score_data: {
                "type": "score_submitted",
                "competition_id": str,
                "entry_id": str,
                "judge_id": str,
                "value": float,
                "timestamp": str
            }
        """
        message = {
            "type": "score_submitted",
            **score_data
        }
        
        # Broadcast to competition subscribers
        competition_id = score_data.get("competition_id")
        if competition_id:
            await self.broadcast_to_competition(competition_id, message)
        
        logger.debug(f"Broadcasted score for competition {competition_id}")
    
    async def broadcast_results_updated(self, competition_id: str):
        """Notify clients that results have been recalculated."""
        message = {
            "type": "results_updated",
            "competition_id": competition_id,
        }
        await self.broadcast_to_competition(competition_id, message)
    
    def get_stats(self) -> dict:
        """Get connection statistics for monitoring."""
        return {
            "total_connections": len(self.active_connections),
            "subscribed_competitions": len(self.competition_subscriptions),
            "subscriptions_by_competition": {
                comp_id: len(subs) 
                for comp_id, subs in self.competition_subscriptions.items()
            }
        }


# Global connection manager instance
manager = ConnectionManager()

