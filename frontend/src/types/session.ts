/**
 * Browser session-related type definitions
 */

export enum SessionStatus {
  INITIALIZING = "initializing",
  ACTIVE = "active",
  BUSY = "busy",
  IDLE = "idle",
  ERROR = "error",
  TERMINATED = "terminated"
}

export enum SessionType {
  NOVA_ACT = "nova_act",
  PLAYWRIGHT_MCP = "playwright_mcp"
}

export interface BrowserSession {
  id: string;
  type: SessionType;
  status: SessionStatus;
  
  // AgentCore Browser details
  browser_id?: string;
  agentcore_session_id?: string;
  
  // Order association
  order_id?: string;
  retailer?: string;
  
  // Timing
  created_at: string;
  started_at?: string;
  last_activity?: string;
  
  // Progress tracking
  current_url?: string;
  current_step?: string;
  progress_percentage: number;
  
  // Screenshots and monitoring
  latest_screenshot?: string;
  thumbnail_url?: string;
  
  // Performance metrics
  page_load_time?: number;
  total_processing_time?: number;
  
  // Error handling
  error_count: number;
  last_error?: string;
  
  // Metadata
  metadata: Record<string, any>;
}

export interface SessionThumbnail {
  session_id: string;
  image_data: string; // base64 encoded
  timestamp: string;
  width: number;
  height: number;
}

export interface SessionMetrics {
  session_id: string;
  
  // Performance
  average_page_load_time?: number;
  total_actions: number;
  successful_actions: number;
  failed_actions: number;
  
  // Resource usage
  memory_usage?: number;
  cpu_usage?: number;
  
  // Network
  requests_count: number;
  data_transferred?: number; // bytes
  
  // Timing
  session_duration?: number;
  idle_time?: number;
  
  // Error tracking
  error_rate?: number;
  common_errors: string[];
}

export interface SessionEvent {
  session_id: string;
  event_type: string; // "action", "error", "status_change", etc.
  message: string;
  timestamp: string;
  data?: Record<string, any>;
  screenshot_url?: string;
}