/**
 * WebSocket Service for Real-Time Score Updates
 * 
 * Connects to the server's WebSocket endpoint to receive live score broadcasts.
 * Enables instant tabulator updates without polling.
 */

import { ref, type Ref } from 'vue';

// ============= Types =============

export interface ScoreMessage {
  type: 'score_submitted';
  competition_id: string;
  entry_id: string;
  judge_id: string;
  value: number;
  timestamp: string;
}

export interface ResultsUpdatedMessage {
  type: 'results_updated';
  competition_id: string;
}

export interface SubscribedMessage {
  type: 'subscribed' | 'unsubscribed';
  competition_id: string;
}

export interface PingPongMessage {
  type: 'ping' | 'pong';
}

export type WebSocketMessage = 
  | ScoreMessage 
  | ResultsUpdatedMessage 
  | SubscribedMessage 
  | PingPongMessage;

export type ScoreHandler = (score: ScoreMessage) => void;
export type ResultsHandler = (msg: ResultsUpdatedMessage) => void;

// ============= WebSocket Service =============

export class ScoreSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000; // Start with 1 second
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private currentCompetitionId: string | null = null;
  
  // Reactive state
  public isConnected: Ref<boolean> = ref(false);
  public connectionStatus: Ref<'disconnected' | 'connecting' | 'connected' | 'reconnecting'> = ref('disconnected');
  
  // Event handlers
  private scoreHandlers: Set<ScoreHandler> = new Set();
  private resultsHandlers: Set<ResultsHandler> = new Set();

  /**
   * Build the WebSocket URL based on current location.
   * Handles both development (localhost) and production deployments.
   */
  private getWebSocketUrl(competitionId?: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    
    let url = `${protocol}//${host}/ws/scores`;
    
    if (competitionId) {
      url += `?competition_id=${encodeURIComponent(competitionId)}`;
    }
    
    return url;
  }

  /**
   * Connect to the WebSocket server.
   * Optionally subscribe to a specific competition immediately.
   */
  connect(competitionId?: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      // Already connected - just subscribe to new competition if needed
      if (competitionId && competitionId !== this.currentCompetitionId) {
        this.subscribeToCompetition(competitionId);
      }
      return;
    }

    if (this.ws?.readyState === WebSocket.CONNECTING) {
      return; // Connection in progress
    }

    this.connectionStatus.value = 'connecting';
    this.currentCompetitionId = competitionId ?? null;

    try {
      const url = this.getWebSocketUrl(competitionId);
      console.log(`🔌 Connecting to WebSocket: ${url}`);
      
      this.ws = new WebSocket(url);
      
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from the WebSocket server.
   */
  disconnect(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnected');
      this.ws = null;
    }

    this.isConnected.value = false;
    this.connectionStatus.value = 'disconnected';
    this.currentCompetitionId = null;
    this.reconnectAttempts = 0;
  }

  /**
   * Subscribe to updates for a specific competition.
   */
  subscribeToCompetition(competitionId: string): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      // Not connected - will subscribe when we connect
      this.currentCompetitionId = competitionId;
      return;
    }

    // Unsubscribe from previous competition if different
    if (this.currentCompetitionId && this.currentCompetitionId !== competitionId) {
      this.ws.send(JSON.stringify({
        type: 'unsubscribe',
        competition_id: this.currentCompetitionId
      }));
    }

    this.ws.send(JSON.stringify({
      type: 'subscribe',
      competition_id: competitionId
    }));

    this.currentCompetitionId = competitionId;
    console.log(`📡 Subscribed to competition: ${competitionId}`);
  }

  /**
   * Unsubscribe from a competition.
   */
  unsubscribeFromCompetition(competitionId: string): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(JSON.stringify({
      type: 'unsubscribe',
      competition_id: competitionId
    }));

    if (this.currentCompetitionId === competitionId) {
      this.currentCompetitionId = null;
    }
  }

  /**
   * Register a handler for score updates.
   */
  onScore(handler: ScoreHandler): () => void {
    this.scoreHandlers.add(handler);
    return () => this.scoreHandlers.delete(handler);
  }

  /**
   * Register a handler for results updated messages.
   */
  onResultsUpdated(handler: ResultsHandler): () => void {
    this.resultsHandlers.add(handler);
    return () => this.resultsHandlers.delete(handler);
  }

  // ============= Private Methods =============

  private handleOpen(): void {
    console.log('✅ WebSocket connected');
    this.isConnected.value = true;
    this.connectionStatus.value = 'connected';
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;

    // Start ping/pong keepalive
    this.startPingInterval();
  }

  private handleClose(event: CloseEvent): void {
    console.log(`WebSocket closed: ${event.code} ${event.reason}`);
    this.isConnected.value = false;
    
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }

    // Don't reconnect if we intentionally closed
    if (event.code !== 1000) {
      this.scheduleReconnect();
    } else {
      this.connectionStatus.value = 'disconnected';
    }
  }

  private handleError(event: Event): void {
    console.error('WebSocket error:', event);
    // Close event will handle reconnection
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      
      switch (message.type) {
        case 'score_submitted':
          console.log(`📥 Score received: ${message.value} for entry ${message.entry_id}`);
          for (const handler of this.scoreHandlers) {
            handler(message as ScoreMessage);
          }
          break;
        
        case 'results_updated':
          console.log(`📊 Results updated for competition ${message.competition_id}`);
          for (const handler of this.resultsHandlers) {
            handler(message as ResultsUpdatedMessage);
          }
          break;
        
        case 'subscribed':
          console.log(`✓ Subscribed to competition ${message.competition_id}`);
          break;
        
        case 'unsubscribed':
          console.log(`✓ Unsubscribed from competition ${message.competition_id}`);
          break;
        
        case 'ping':
          // Server pinged us - respond with pong
          this.ws?.send(JSON.stringify({ type: 'pong' }));
          break;
        
        case 'pong':
          // Server responded to our ping - connection is healthy
          break;
        
        default:
          console.log('Unknown message type:', message);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached. Giving up.');
      this.connectionStatus.value = 'disconnected';
      return;
    }

    this.connectionStatus.value = 'reconnecting';
    this.reconnectAttempts++;
    
    // Exponential backoff with jitter
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1) + Math.random() * 1000,
      30000 // Max 30 seconds
    );

    console.log(`🔄 Reconnecting in ${Math.round(delay / 1000)}s (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.connect(this.currentCompetitionId ?? undefined);
    }, delay);
  }

  private startPingInterval(): void {
    // Send ping every 30 seconds to keep connection alive
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }
}

// Export singleton instance
export const scoreSocket = new ScoreSocketService();

