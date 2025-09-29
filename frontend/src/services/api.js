/**
 * API service for Order Automation System
 */

const API_BASE_URL = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

class APIService {
  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  // Order Management
  async getOrders(limit = 500) {
    return this.request(`/api/orders?limit=${limit}`);
  }

  async getOrder(orderId) {
    return this.request(`/api/orders/${orderId}`);
  }

  async createOrder(orderData, automationMethod = 'strands') {
    return this.request('/api/orders', {
      method: 'POST',
      body: JSON.stringify(orderData),
      params: { automation_method: automationMethod }
    });
  }

  async cancelOrder(orderId) {
    return this.request(`/api/orders/${orderId}/cancel`, {
      method: 'POST'
    });
  }

  async createSampleOrder(automationMethod = 'strands') {
    return this.request(`/api/test/sample-order?automation_method=${automationMethod}`, {
      method: 'POST'
    });
  }

  async compareAutomationMethods(orderData) {
    return this.request('/api/automation/compare', {
      method: 'POST',
      body: JSON.stringify(orderData)
    });
  }

  // Live View and Control
  async getLiveViewUrl(orderId) {
    return this.request(`/api/orders/${orderId}/live-view`);
  }

  async getPresignedUrl(orderId) {
    return this.request(`/api/orders/${orderId}/presigned-url`);
  }

  async changeBrowserResolution(orderId, width, height) {
    return this.request(`/api/orders/${orderId}/change-resolution`, {
      method: 'POST',
      body: JSON.stringify({ width, height })
    });
  }

  async takeManualControl(orderId) {
    return this.request(`/api/orders/${orderId}/take-control`, {
      method: 'POST'
    });
  }

  async releaseManualControl(orderId) {
    return this.request(`/api/orders/${orderId}/release-control`, {
      method: 'POST'
    });
  }

  async focusActiveTab(orderId) {
    return this.request(`/api/orders/${orderId}/focus-tab`, {
      method: 'POST'
    });
  }

  async forceDisconnectSession(orderId) {
    return this.request(`/api/orders/${orderId}/force-disconnect`, {
      method: 'POST'
    });
  }

  // Session Management
  async getSessions() {
    return this.request('/api/sessions');
  }

  // Metrics and Configuration
  async getPerformanceMetrics() {
    return this.request('/api/metrics/performance');
  }

  async getRetailerConfig() {
    return this.request('/api/config/retailers');
  }

  async getSystemStatus() {
    return this.request('/api/system/status');
  }

  // Health Check
  async healthCheck() {
    return this.request('/health');
  }

  async apiHealthCheck() {
    return this.request('/api/health');
  }
}

// WebSocket service for real-time updates
class WebSocketService {
  constructor() {
    this.ws = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect() {
    try {
      const wsUrl = `ws://localhost:8000/ws`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.notifyListeners('connected', { connected: true });
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.notifyListeners(data.type, data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.notifyListeners('connected', { connected: false });
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.notifyListeners('error', { error });
      };

    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      setTimeout(() => this.connect(), 3000 * this.reconnectAttempts);
    }
  }

  subscribe(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType).add(callback);

    // Return unsubscribe function
    return () => {
      const callbacks = this.listeners.get(eventType);
      if (callbacks) {
        callbacks.delete(callback);
      }
    };
  }

  notifyListeners(eventType, data) {
    const callbacks = this.listeners.get(eventType);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in WebSocket listener:', error);
        }
      });
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.listeners.clear();
  }
}

// Export singleton instances
export const apiService = new APIService();
export const wsService = new WebSocketService();

// Legacy exports for compatibility
export const orderAPI = apiService;
export const configAPI = apiService;
export default apiService;