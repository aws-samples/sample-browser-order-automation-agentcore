import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Container,
  Header,
  StatusIndicator,
  Alert,
  Spinner,
  Box,
  SpaceBetween,
  Button
} from '@cloudscape-design/components';
import '@cloudscape-design/global-styles/index.css';

const LiveBrowserViewer = ({ orderId }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [sessionId, setSessionId] = useState('');
  // eslint-disable-next-line no-unused-vars
  const [authToken, setAuthToken] = useState('');
  const [dcvLoaded, setDcvLoaded] = useState(false);
  const [connection, setConnection] = useState(null);
  const [currentResolution, setCurrentResolution] = useState('900p'); // Default to 1600x900
  const authRef = useRef(null);
  const dcvViewerRef = useRef(null);
  const connectionRef = useRef(null);

  // Load DCV SDK
  useEffect(() => {
    const loadDCVSDK = async () => {
      try {
        // Check if DCV is already loaded
        if (window.dcv) {
          setDcvLoaded(true);
          return;
        }

        // Override URL constructor to force absolute paths for DCV worker files
        const originalURL = window.URL;
        window.URL = function(url, base) {
          // If this is a DCV worker file request, force it to use origin
          if (typeof url === 'string' && url.includes('dcv-sdk/dcvjs-umd/dcv/')) {
            console.log('Intercepting DCV worker URL:', url);
            if (!url.startsWith('http')) {
              // Convert relative path to absolute
              const absoluteUrl = window.location.origin + '/' + url.replace(/^\/+/, '');
              console.log('Converted to absolute URL:', absoluteUrl);
              return new originalURL(absoluteUrl);
            }
          }
          return new originalURL(url, base);
        };
        
        // Copy static properties
        Object.setPrototypeOf(window.URL, originalURL);
        Object.defineProperty(window.URL, 'prototype', {
          value: originalURL.prototype,
          writable: false
        });

        // Load DCV Web Client SDK
        const dcvScript = document.createElement('script');
        dcvScript.src = '/dcv-sdk/dcvjs-umd/dcv.js';
        dcvScript.type = 'text/javascript';
        dcvScript.onload = () => {
          console.log('DCV Web Client SDK loaded successfully');
          
          // Restore original URL constructor
          window.URL = originalURL;
          console.log('Restored original URL constructor');
          
          // Configure DCV worker path like in simple_browser_viewer.py
          window.dcvWorkerPath = window.location.origin + '/dcv-sdk/dcvjs-umd/dcv/';
          console.log('DCV worker path set to:', window.dcvWorkerPath);
          
          // Set worker path immediately after loading with absolute URL
          if (window.dcv && window.dcv.setWorkerPath) {
            window.dcv.setWorkerPath(window.location.origin + '/dcv-sdk/dcvjs-umd/dcv/');
            console.log('DCV setWorkerPath called with absolute URL');
          }
          
          // Also try setting baseUrl
          if (window.dcv && window.dcv.setBaseUrl) {
            window.dcv.setBaseUrl(window.location.origin + '/dcv-sdk/dcvjs-umd');
            console.log('DCV setBaseUrl called with absolute URL');
          }
          
          // Log DCV SDK info for debugging
          if (window.dcv) {
            console.log('DCV SDK version:', window.dcv.version || 'Unknown');
            console.log('DCV SDK methods:', Object.keys(window.dcv));
          }
          
          setDcvLoaded(true);
        };
        dcvScript.onerror = (err) => {
          console.error('Failed to load DCV Web Client SDK:', err);
          setError('Failed to load DCV SDK');
          setLoading(false);
          
          // Restore original URL constructor on error
          window.URL = originalURL;
          console.log('Restored original URL constructor on error');
        };
        document.head.appendChild(dcvScript);

      } catch (err) {
        console.error('Error loading DCV SDK:', err);
        setError('Failed to initialize DCV SDK');
        setLoading(false);
      }
    };

    loadDCVSDK();
  }, []);

  const connectToDCV = useCallback((serverUrl, sessionId, authToken, retryCount = 0) => {
    // Check if dcv-display element exists
    const dcvElement = document.getElementById('dcv-display');
    if (!dcvElement) {
      if (retryCount < 10) { // Max 10 retries (1 second total)
        console.error(`dcv-display element not found! Retrying in 100ms... (${retryCount + 1}/10)`);
        setTimeout(() => connectToDCV(serverUrl, sessionId, authToken, retryCount + 1), 100);
        return;
      } else {
        console.error('dcv-display element not found after 10 retries. Giving up.');
        setError('Failed to find display element. Please refresh the page.');
        setLoading(false);
        return;
      }
    }
    
    console.log('dcv-display element found:', dcvElement);
    
    // Set DCV worker path before connecting - use complete absolute URL
    const fullWorkerPath = window.location.origin + '/dcv-sdk/dcvjs-umd/dcv/';
    const fullBaseUrl = window.location.origin + '/dcv-sdk/dcvjs-umd';
    
    if (window.dcv && window.dcv.setWorkerPath) {
      window.dcv.setWorkerPath(fullWorkerPath);
      console.log('DCV worker path set to:', fullWorkerPath);
    }
    
    if (window.dcv && window.dcv.setBaseUrl) {
      window.dcv.setBaseUrl(fullBaseUrl);
      console.log('DCV base URL set to:', fullBaseUrl);
    }
    
    // Configure DCV similar to simple_browser_viewer.py
    const dcvConfig = {
      url: serverUrl,
      sessionId,
      authToken,
      divId: 'dcv-display',
      baseUrl: fullBaseUrl,
      observers: {  // ← callbacks에서 observers로 변경!
        httpExtraSearchParams: (method, url, body) => {
          // Use presigned URL parameters for connection
          const searchParams = new URL(serverUrl).searchParams;
          return searchParams;
        },
        displayLayout: (layout) => {
          console.log('Display layout changed:', layout);
        },
        firstFrame: () => {
          console.log('DCV first frame received! Connection is working.');
          // If we get first frame, connection is actually successful
          setAuthenticated(true);
          setLoading(false);
          setError(null);
        },
        error: (error) => {
          console.error('DCV connection error:', error);
        }
      }
    };
    
    console.log('DCV connect config:', dcvConfig);
    
    window.dcv.connect(dcvConfig)
    .then((conn) => {
      console.log('Connection established');
      connectionRef.current = conn;
      setConnection(conn);
      setSessionId(sessionId);
      setAuthToken(authToken);
      setAuthenticated(true);
      setLoading(false);
    })
    .catch((error) => {
      console.error('Connection failed:', error);
      
      // Handle connection limit reached error with retry
      if (error.code === 12 || error.message?.includes('Connection limit reached')) {
        setError('Connection limit reached. The DCV server has reached its maximum concurrent connections. Please try again in a few moments.');
      } else {
        setError(`Connection failed: ${error.message}`);
      }
      setLoading(false);
    });
  }, []);

  const connectToSession = useCallback((serverUrl, sessionId, authToken) => {
    console.log('[LiveBrowserViewer] Connecting to session:', sessionId);
    
    const connectOptions = {
      url: serverUrl,
      sessionId: sessionId,
      authToken: authToken,
      divId: 'dcv-display',
      baseUrl: window.location.origin + '/dcv-sdk/dcvjs-umd',
      observers: {  // ← callbacks에서 observers로 변경!
        httpExtraSearchParams: (method, url, body) => {
          console.log('[LiveBrowserViewer] httpExtraSearchParams called:', { method, url });
          const parsedUrl = new URL(serverUrl);
          const params = parsedUrl.searchParams;
          console.log('[LiveBrowserViewer] Returning auth params:', params.toString());
          return params;
        },
        displayLayout: (serverWidth, serverHeight, heads) => {
          console.log(`[LiveBrowserViewer] Display layout callback: ${serverWidth}x${serverHeight}`);
          const display = document.getElementById('dcv-display');
          
          if (display) {
            // Let DCV SDK handle the sizing - just ensure container fills available space
            display.style.width = '100%';
            display.style.height = '100%';
            display.style.transform = 'none';
            display.style.transformOrigin = 'initial';
            
            console.log(`[LiveBrowserViewer] Set display to fill container, server size: ${serverWidth}x${serverHeight}`);
          }
        },
        firstFrame: () => {
          console.log('[LiveBrowserViewer] First frame received!');
          
          // Request display layout again after first frame
          if (connectionRef.current && connectionRef.current.requestDisplayLayout) {
            const resolutions = {
              '720p': { width: 1280, height: 720 },
              '900p': { width: 1600, height: 900 },
              '1080p': { width: 1920, height: 1080 },
              '1440p': { width: 2560, height: 1440 }
            };
            const resolution = resolutions[currentResolution];
            console.log(`[LiveBrowserViewer] Requesting display layout after first frame: ${resolution.width}x${resolution.height}`);
            
            setTimeout(() => {
              connectionRef.current.requestDisplayLayout([{
                name: "Main Display",
                rect: {
                  x: 0,
                  y: 0,
                  width: resolution.width,
                  height: resolution.height
                },
                primary: true
              }]);
            }, 1000); // Wait 1 second after first frame
          }
        },
        error: (error) => {
          console.error('[LiveBrowserViewer] Connection error:', error);
          setError(`Connection failed: ${error.message || error}`);
          setLoading(false);
        }
      }
    };
    
    console.log('[LiveBrowserViewer] Connect options:', connectOptions);
    
    window.dcv.connect(connectOptions)
      .then(connection => {
        console.log('[LiveBrowserViewer] Connection established:', connection);
        connectionRef.current = connection;
        setConnection(connection);
        
        // Request display layout based on current resolution - multiple attempts
        if (connection && connection.requestDisplayLayout) {
          const resolutions = {
            '720p': { width: 1280, height: 720 },
            '900p': { width: 1600, height: 900 },
            '1080p': { width: 1920, height: 1080 },
            '1440p': { width: 2560, height: 1440 }
          };
          const resolution = resolutions[currentResolution];
          console.log(`[LiveBrowserViewer] Requesting initial display layout: ${resolution.width}x${resolution.height}`);
          
          // Request immediately
          connection.requestDisplayLayout([{
            name: "Main Display",
            rect: {
              x: 0,
              y: 0,
              width: resolution.width,
              height: resolution.height
            },
            primary: true
          }]);
          
          // Request again after a short delay
          setTimeout(() => {
            connection.requestDisplayLayout([{
              name: "Main Display",
              rect: {
                x: 0,
                y: 0,
                width: resolution.width,
                height: resolution.height
              },
              primary: true
            }]);
          }, 500);
          
          // And once more after 2 seconds
          setTimeout(() => {
            connection.requestDisplayLayout([{
              name: "Main Display",
              rect: {
                x: 0,
                y: 0,
                width: resolution.width,
                height: resolution.height
              },
              primary: true
            }]);
          }, 2000);
        }
      })
      .catch(error => {
        console.error('[LiveBrowserViewer] Connect failed:', error);
        setError(`Connection failed: ${error.message || error}`);
        setLoading(false);
      });
  }, [currentResolution]);

  const startAndConnect = useCallback(async () => {
    if (!orderId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      // Get presigned URL following AWS tutorial pattern
      const response = await fetch(`/api/orders/${orderId}/presigned-url`);
      if (!response.ok) {
        if (response.status === 503) {
          throw new Error('Live view not available - AgentCore session not active');
        } else if (response.status === 400) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Order not in processing state');
        } else {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
      }
      
      const presignedData = await response.json();
      console.log('Presigned URL response:', presignedData);
      
      // Check for errors
      if (presignedData.error || !presignedData.presignedUrl) {
        throw new Error(presignedData.error || 'No presigned URL available');
      }
      
      // Check if this is development mode
      if (presignedData.development_mode || presignedData.presignedUrl?.includes('dcv-server.example.com')) {
        console.log('Development mode detected - using mock DCV connection');
        // In development mode, simulate successful connection
        setTimeout(() => {
          setSessionId(presignedData.sessionId);
          setAuthToken(presignedData.authToken);
          setAuthenticated(true);
          setConnection({ mock: true });
          setLoading(false);
        }, 1000);
        return;
      }

      // Real DCV server - use AWS DCV Web SDK
      if (!window.dcv) {
        throw new Error('AWS DCV Web SDK not loaded');
      }

      const { presignedUrl } = presignedData;
      
      // Set log level for debugging
      if (window.dcv.setLogLevel && window.dcv.LogLevel) {
        window.dcv.setLogLevel(window.dcv.LogLevel.DEBUG);
        console.log('DCV log level set to DEBUG');
      }
      
      // Follow simple_browser_viewer.py pattern: authenticate first, then connect
      console.log('Starting DCV authentication...');
      
      let authSuccessful = false; // Flag to track successful authentication
      
      authRef.current = window.dcv.authenticate(presignedUrl, {
        promptCredentials: (authType, callback) => {
          console.log('Credentials prompted:', authType);
          // For presigned URLs, credentials should be embedded
          callback(null, null);
        },
        error: (auth, error) => {
          // Ignore error if authentication was already successful
          if (authSuccessful) {
            console.log('Ignoring error callback after successful authentication:', error);
            return;
          }
          
          console.error('Authentication failed:', error);
          
          let errorMessage = 'Unknown authentication error';
          if (error) {
            if (error.message) {
              errorMessage = error.message;
            } else if (typeof error === 'object' && error.code) {
              errorMessage = `Error code ${error.code}: ${error.message || 'Failed to communicate with server'}`;
            } else {
              errorMessage = error.toString();
            }
          }
          
          setError(`Authentication failed: ${errorMessage}`);
          setLoading(false);
          authRef.current = null;
          
          // Stop any further connection attempts
          return;
        },
        success: (auth, result) => {
          console.log('Authentication successful:', result);
          authSuccessful = true; // Mark authentication as successful
          
          if (result && result[0]) {
            const { sessionId: authSessionId, authToken: authAuthToken } = result[0];
            console.log('Session ID:', authSessionId);
            console.log('Auth token received:', authAuthToken ? 'Yes' : 'No');
            
            // First update UI state to render dcv-display element
            setSessionId(authSessionId);
            setAuthToken(authAuthToken);
            setAuthenticated(true);
            setLoading(false);
            setError(null);
            
            // Then wait for DOM to update and connect
            setTimeout(() => {
              connectToSession(presignedUrl, authSessionId, authAuthToken);
            }, 100);
            
          } else {
            console.error('No session data in auth result');
            setError('Authentication succeeded but no session data received');
            setLoading(false);
          }
        },
        httpExtraSearchParams: (method, url, body) => {
          // Use presigned URL parameters
          const searchParams = new URL(presignedUrl).searchParams;
          return searchParams;
        }
      });
      
    } catch (err) {
      console.error('Error starting DCV connection:', err);
      setError(`Failed to start connection: ${err.message}`);
      setLoading(false);
    }
  }, [connectToSession, orderId]);

  // Start connection when DCV is loaded and we have an order ID
  useEffect(() => {
    if (dcvLoaded && orderId && !authenticated && !authRef.current) {
      startAndConnect();
    }
  }, [dcvLoaded, orderId, authenticated, startAndConnect]);

  // Cleanup connections on unmount
  useEffect(() => {
    return () => {
      console.log('LiveBrowserViewer unmounting - cleaning up connections');
      
      // Close DCV connection
      if (connectionRef.current) {
        try {
          connectionRef.current.close();
          console.log('DCV connection closed');
        } catch (err) {
          console.warn('Error closing DCV connection:', err);
        }
        connectionRef.current = null;
      }
      
      // Cancel authentication if in progress
      if (authRef.current) {
        try {
          authRef.current.cancel();
          console.log('DCV authentication cancelled');
        } catch (err) {
          console.warn('Error cancelling DCV authentication:', err);
        }
        authRef.current = null;
      }
    };
  }, []);

  // Show error state
  if (error) {
    const isConnectionLimitError = error.includes('Connection limit reached');
    
    return (
      <Container
        header={
          <Header
            variant="h2"
            description="Real-time browser automation view powered by AWS DCV"
          >
            Live Browser View
          </Header>
        }
      >
        <SpaceBetween direction="vertical" size="m">
          <Alert 
            type="error" 
            header="Connection Error"
            action={
              <Button
                variant="primary"
                onClick={async () => {
                  setLoading(true);
                  setError(null);
                  
                  // If connection limit error, try to force disconnect existing sessions
                  if (isConnectionLimitError) {
                    try {
                      console.log('Attempting to force disconnect existing sessions...');
                      const disconnectResponse = await fetch(`/api/orders/${orderId}/force-disconnect`, {
                        method: 'POST'
                      });
                      
                      if (disconnectResponse.ok) {
                        const disconnectData = await disconnectResponse.json();
                        console.log('Force disconnect result:', disconnectData);
                        
                        // Wait a moment for cleanup
                        await new Promise(resolve => setTimeout(resolve, 1000));
                      }
                    } catch (disconnectError) {
                      console.warn('Failed to force disconnect:', disconnectError);
                    }
                  }
                  
                  // Reset state and retry
                  setAuthenticated(false);
                  setConnection(null);
                  connectionRef.current = null;
                  authRef.current = null;
                  startAndConnect();
                }}
              >
                {isConnectionLimitError ? 'Force Disconnect & Retry' : 'Retry Connection'}
              </Button>
            }
          >
            {error}
            {isConnectionLimitError && (
              <Box margin={{ top: 's' }}>
                <div style={{ fontSize: '14px', color: '#666' }}>
                  This usually happens when multiple browser sessions are active. 
                  Wait a moment and try again, or close other browser tabs with live views.
                </div>
              </Box>
            )}
          </Alert>
        </SpaceBetween>
      </Container>
    );
  }

  // Show DCV viewer when connected
  if (authenticated && connection) {
    return (
      <Container
        header={
          <Header
            variant="h2"
            description="Real-time browser automation view powered by AWS DCV"
          >
            Live Browser View
          </Header>
        }
      >
        <SpaceBetween direction="vertical" size="m">
          <StatusIndicator type="success">
            Connected to live view (Session: {sessionId ? sessionId.substring(0, 12) : 'Unknown'})
          </StatusIndicator>
          
          {/* Resolution Control */}
          <Box>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '15px',
              padding: '10px',
              backgroundColor: '#f9f9f9',
              borderRadius: '8px',
              border: '1px solid #e1e1e1'
            }}>
              <span style={{ fontSize: '14px', fontWeight: '500', color: '#333' }}>Display Size:</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                {[
                  { text: '720p', id: '720p', full: '1280×720' },
                  { text: '900p', id: '900p', full: '1600×900' },
                  { text: '1080p', id: '1080p', full: '1920×1080' },
                  { text: '1440p', id: '1440p', full: '2560×1440' }
                ].map((item) => (
                  <Button
                    key={item.id}
                    variant={currentResolution === item.id ? 'primary' : 'normal'}
                    size="small"
                    onClick={async () => {
                      const resolutions = {
                        '720p': { width: 1280, height: 720 },
                        '900p': { width: 1600, height: 900 },
                        '1080p': { width: 1920, height: 1080 },
                        '1440p': { width: 2560, height: 1440 }
                      };
                      const resolution = resolutions[item.id];
                      if (resolution && connectionRef.current) {
                        console.log(`[LiveBrowserViewer] Changing resolution to: ${resolution.width}x${resolution.height}`);
                        setCurrentResolution(item.id);
                        
                        try {
                          // First, change the actual browser resolution via backend API
                          console.log(`[LiveBrowserViewer] Calling backend API to change browser resolution...`);
                          const response = await fetch(`/api/orders/${orderId}/change-resolution`, {
                            method: 'POST',
                            headers: {
                              'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                              width: resolution.width,
                              height: resolution.height
                            })
                          });
                          
                          if (response.ok) {
                            const result = await response.json();
                            console.log(`[LiveBrowserViewer] Browser resolution changed successfully:`, result);
                            
                            // Wait a moment for the browser to resize
                            await new Promise(resolve => setTimeout(resolve, 1000));
                          } else {
                            const error = await response.json();
                            console.warn(`[LiveBrowserViewer] Failed to change browser resolution:`, error);
                          }
                        } catch (error) {
                          console.warn(`[LiveBrowserViewer] Error calling resolution API:`, error);
                        }
                        
                        // Then, request new DCV display layout
                        connectionRef.current.requestDisplayLayout([{
                          name: "Main Display",
                          rect: {
                            x: 0,
                            y: 0,
                            width: resolution.width,
                            height: resolution.height
                          },
                          primary: true
                        }]);
                        
                        // Also update container size dynamically
                        const container = document.querySelector('[data-dcv-container]');
                        if (container) {
                          // Calculate aspect ratio and set appropriate container height
                          const aspectRatio = resolution.height / resolution.width;
                          const containerWidth = container.clientWidth;
                          const newHeight = Math.min(containerWidth * aspectRatio, 1000); // Max 1000px height
                          container.style.height = `${newHeight}px`;
                        }
                      }
                    }}
                    title={item.full}
                  >
                    {item.text}
                  </Button>
                ))}
              </div>
              <span style={{ fontSize: '12px', color: '#666', marginLeft: 'auto' }}>
                Current: {currentResolution === '720p' ? '1280×720' : 
                         currentResolution === '900p' ? '1600×900' : 
                         currentResolution === '1080p' ? '1920×1080' : '2560×1440'}
              </span>
            </div>
          </Box>
          <Box>
            {connection.mock ? (
              // Development mode display
              <div
                style={{
                  width: '100%',
                  height: '600px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  backgroundColor: '#f5f5f5',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <div style={{ textAlign: 'center', padding: '20px' }}>
                  <div style={{ fontSize: '24px', marginBottom: '16px' }}>🔧</div>
                  <div style={{ fontSize: '18px', marginBottom: '16px' }}>
                    Development Mode
                  </div>
                  <div style={{ fontSize: '14px', marginBottom: '8px' }}>
                    Session ID: {sessionId}
                  </div>
                  <div style={{ fontSize: '12px', opacity: 0.6, maxWidth: '400px' }}>
                    In production, this would show the live browser automation session.
                    The browser is currently running on AWS AgentCore.
                  </div>
                </div>
              </div>
            ) : (
              // Real DCV display
              <div
                data-dcv-container
                style={{
                  width: '100%',
                  height: '900px',  // Initial height, will be adjusted dynamically
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  backgroundColor: '#000',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                <div
                  id="dcv-display"
                  ref={dcvViewerRef}
                  style={{
                    width: '100%',
                    height: '100%',
                    position: 'absolute',
                    top: 0,
                    left: 0
                  }}
                />
              </div>
            )}
          </Box>
        </SpaceBetween>
      </Container>
    );
  }

  // Loading state
  if (loading) {
    return (
      <Container
        header={
          <Header
            variant="h2"
            description="Real-time browser automation view powered by AWS DCV"
          >
            Live Browser View
          </Header>
        }
      >
        <Box textAlign="center" padding="l">
          <Spinner size="large" />
          <Box variant="p" padding={{ top: "s" }}>
            {!dcvLoaded ? 'Loading DCV SDK...' :
              'Connecting to live view...'}
          </Box>
        </Box>
      </Container>
    );
  }

  // Default state
  return (
    <Container
      header={
        <Header
          variant="h2"
          description="Real-time browser automation view powered by AWS DCV"
        >
          Live Browser View
        </Header>
      }
    >
      <Box padding="l" textAlign="center">
        <StatusIndicator type="warning">
          Live view unavailable
        </StatusIndicator>
        <Box variant="p" padding={{ top: "s" }}>
          No active agent found for this order
        </Box>
      </Box>
    </Container>
  );
};

export default LiveBrowserViewer;