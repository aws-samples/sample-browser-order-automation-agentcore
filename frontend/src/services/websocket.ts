/**
 * WebSocket service for real-time updates
 */

import { io, Socket } from 'socket.io-client';
import { OrderProgress } from '../types/order';

class WebSocketService {
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  connect(url: string = 'ws://localhost:8000'): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        // Create WebSocket connection (not socket.io for this simple case)
        const wsUrl = url.replace('http://', 'ws://').replace('https://', 'wss://');
        const ws = new WebSocket(`${wsUrl}/ws`);

        ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          resolve();
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        ws.onclose = () => {
          console.log('WebSocket disconnected');
          this.handleReconnect();
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };

        // Store reference (cast to any to avoid type issues)
        this.socket = ws as any;

      } catch (error) {
        reject(error);
      }
    });
  }

  private handleMessage(data: any) {
    switch (data.type) {
      case 'order_progress':
        this.onOrderProgress?.(data.data);
        break;
      case 'session_update':
        this.onSessionUpdate?.(data.data);
        break;
      case 'thumbnail_update':
        this.onThumbnailUpdate?.(data.data);
        break;
      default:
        console.log('Unknown message type:', data.type);
    }
  }

  private handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      
      setTimeout(() => {
        this.connect().catch(console.error);
      }, this.reconnectDelay * this.reconnectAttempts);
    } else {
      console.error('Max reconnection attempts reached');
    }
  }

  disconnect() {
    if (this.socket) {
      (this.socket as any).close();
      this.socket = null;
    }
  }

  // Event handlers - can be set by components
  onOrderProgress?: (progress: OrderProgress) => void;
  onSessionUpdate?: (sessionData: any) => void;
  onThumbnailUpdate?: (thumbnailData: any) => void;

  // Send message (for keep-alive or other purposes)
  send(message: any) {
    if (this.socket && (this.socket as any).readyState === WebSocket.OPEN) {
      (this.socket as any).send(JSON.stringify(message));
    }
  }

  isConnected(): boolean {
    return this.socket !== null && (this.socket as any).readyState === WebSocket.OPEN;
  }
}

// Create singleton instance
const websocketService = new WebSocketService();

export default websocketService;