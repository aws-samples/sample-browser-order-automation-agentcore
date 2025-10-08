import React, { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Header,
  Box,
  Button,
  SpaceBetween,
  StatusIndicator,
  Modal,
  Alert,
  KeyValuePairs
} from '@cloudscape-design/components';

const SessionReplayViewer = ({ order, isVisible, onClose }) => {
  const [replayInfo, setReplayInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);


  const fetchReplayInfo = useCallback(async () => {
    if (!order?.id) return;
    
    setLoading(true);
    setError(null);
    
    try {
      // Try the new detailed status endpoint first
      let response = await fetch(`/api/orders/${order.id}/session-replay/status`);
      
      if (!response.ok) {
        // Fallback to the original endpoint
        response = await fetch(`/api/orders/${order.id}/session-replay`);
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Session replay not available');
        }
      }
      
      const data = await response.json();
      
      if (!data.replay_available) {
        throw new Error(data.reason || 'Session replay not available for this order');
      }
      
      setReplayInfo(data);
      
    } catch (err) {
      console.error('Failed to fetch session replay info:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [order?.id]);

  useEffect(() => {
    if (isVisible) {
      fetchReplayInfo();
    }
  }, [isVisible, order?.id, fetchReplayInfo]);

  const handleRefresh = () => {
    fetchReplayInfo();
  };



  const openReplayInNewTab = () => {
    if (replayInfo?.cli_commands) {
      const instructions = `
Session Replay CLI Commands
===========================

View Specific Session:
${replayInfo.cli_commands.view_specific}

View Latest Recording:
${replayInfo.cli_commands.view_latest}

Interactive Browser Session:
${replayInfo.cli_commands.interactive}

Setup Instructions:
1. Install the Amazon Bedrock AgentCore SDK
2. Configure AWS credentials with S3 access
3. Run any of the commands above

Documentation: ${replayInfo.documentation_url || 'https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-browser-observability.html'}
      `;
      
      navigator.clipboard.writeText(instructions.trim());
      console.log('Session replay CLI commands copied to clipboard!');
    } else if (replayInfo?.s3_bucket && replayInfo?.s3_prefix) {
      // Fallback for older API response format
      const instructions = `
Session Replay CLI Commands
===========================

View Specific Session:
python view_recordings.py --bucket ${replayInfo.s3_bucket} --prefix ${replayInfo.s3_prefix} --session ${replayInfo.session_id}

View Latest Recording:
python view_recordings.py --bucket ${replayInfo.s3_bucket} --prefix ${replayInfo.s3_prefix}
      `;
      
      navigator.clipboard.writeText(instructions.trim());
      console.log('Session replay CLI commands copied to clipboard!');
    }
  };

  if (!isVisible) return null;

  return (
    <Modal
      visible={isVisible}
      onDismiss={onClose}
      header="Session Replay"
      size="large"
      closeAriaLabel="Close session replay viewer"
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button 
              variant="link" 
              onClick={onClose}
            >
              Close
            </Button>
            <Button 
              onClick={handleRefresh}
              disabled={loading}
              iconName="refresh"
            >
              Refresh
            </Button>
            {replayInfo && (
              <Button 
                variant="primary" 
                onClick={openReplayInNewTab}
                iconName="external"
              >
                Copy Instructions
              </Button>
            )}
          </SpaceBetween>
        </Box>
      }
    >
      <SpaceBetween size="l">
        {/* Order Information */}
        <Container>
          <KeyValuePairs
            columns={3}
            items={[
              { label: 'Order ID', value: order?.id || 'N/A' },
              { label: 'Status', value: order?.status || 'N/A' },
              { label: 'Automation Method', value: order?.automation_method || 'N/A' }
            ]}
          />
        </Container>

        {/* Session Replay Content */}
        <Container>
          {loading && (
            <Box textAlign="center" padding="xxl">
              <SpaceBetween size="m">
                <StatusIndicator type="loading">
                  <Box fontSize="heading-s">Loading session replay info...</Box>
                </StatusIndicator>
                <Box variant="p" color="text-body-secondary">
                  Checking for available session recordings
                </Box>
              </SpaceBetween>
            </Box>
          )}

          {error && (
            <Alert type="warning" header="Session Replay Not Available">
              {error}
              <Box margin={{ top: 's' }}>
                <Box variant="p">
                  Session replay is only available for orders processed with recording enabled.
                  This feature captures browser interactions for debugging and analysis purposes.
                </Box>
                <Box margin={{ top: 's' }}>
                  <Button onClick={handleRefresh} iconName="refresh">
                    Check Again
                  </Button>
                </Box>
              </Box>
            </Alert>
          )}

          {!loading && !error && replayInfo && (
            <SpaceBetween size="m">
              <Alert type="success" header="Session Replay Available">
                A session recording is available for this order. The recording includes browser interactions,
                DOM changes, and network activity during the automation process.
              </Alert>

              <Container header={<Header variant="h3">Replay Information</Header>}>
                <KeyValuePairs
                  columns={2}
                  items={[
                    { label: 'Session ID', value: replayInfo.session_id || 'N/A' },
                    { label: 'S3 Bucket', value: replayInfo.s3_bucket || 'N/A' },
                    { label: 'S3 Prefix', value: replayInfo.s3_prefix || 'N/A' },
                    { label: 'Replay Available', value: replayInfo.replay_available ? 'Yes' : 'No' },
                    { label: 'Automation Method', value: replayInfo.automation_method || 'N/A' }
                  ]}
                />
              </Container>

              <Container header={<Header variant="h3">Session Replay Viewer</Header>}>
                <SpaceBetween size="m">
                  <Alert type="info">
                    <Box variant="p">
                      Session replay captures all browser interactions during the automation process.
                      This includes page navigation, form filling, clicks, and DOM changes.
                    </Box>
                  </Alert>

                  {/* Embedded replay viewer placeholder */}
                  <Box 
                    padding="xl" 
                    backgroundColor="grey-50" 
                    textAlign="center"
                    style={{ 
                      border: '2px dashed #d1d5db', 
                      borderRadius: '8px',
                      minHeight: '400px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'center',
                      alignItems: 'center'
                    }}
                  >
                    <SpaceBetween size="m" alignItems="center">
                      <Box fontSize="heading-m" color="text-body-secondary">
                        🎬 Session Replay Player
                      </Box>
                      <Box variant="p" color="text-body-secondary">
                        Session replay data is stored in S3 and can be viewed using the AgentCore SDK tools.
                      </Box>
                      <SpaceBetween direction="horizontal" size="s">
                        <Button 
                          variant="primary" 
                          onClick={openReplayInNewTab}
                          iconName="copy"
                        >
                          Copy CLI Commands
                        </Button>
                        <Button 
                          variant="normal"
                          iconName="external"
                          onClick={() => window.open('https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-browser-observability.html', '_blank')}
                        >
                          View Documentation
                        </Button>
                      </SpaceBetween>
                    </SpaceBetween>
                  </Box>
                </SpaceBetween>
              </Container>

              <Container header={<Header variant="h3">CLI Commands</Header>}>
                <SpaceBetween size="m">
                  <Box variant="p">
                    Use these commands with the Amazon Bedrock AgentCore SDK to view the session replay:
                  </Box>
                  
                  <Box variant="h4">View Specific Session</Box>
                  <Box fontFamily="monospace" padding="s" backgroundColor="grey-100" style={{ borderRadius: '4px' }}>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '12px' }}>
{`python view_recordings.py \\
  --bucket ${replayInfo.s3_bucket} \\
  --prefix ${replayInfo.s3_prefix} \\
  --session ${replayInfo.session_id}`}
                    </pre>
                  </Box>

                  <Box variant="h4">View Latest Recording</Box>
                  <Box fontFamily="monospace" padding="s" backgroundColor="grey-100" style={{ borderRadius: '4px' }}>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '12px' }}>
{`python view_recordings.py \\
  --bucket ${replayInfo.s3_bucket} \\
  --prefix ${replayInfo.s3_prefix}`}
                    </pre>
                  </Box>

                  <Box variant="h4">Interactive Browser Session</Box>
                  <Box fontFamily="monospace" padding="s" backgroundColor="grey-100" style={{ borderRadius: '4px' }}>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '12px' }}>
{`python -m live_view_sessionreplay.browser_interactive_session`}
                    </pre>
                  </Box>

                  <Alert type="info" header="Setup Instructions">
                    <SpaceBetween size="s">
                      <Box variant="p">
                        1. Install the Amazon Bedrock AgentCore SDK
                      </Box>
                      <Box variant="p">
                        2. Configure your AWS credentials with access to the S3 bucket
                      </Box>
                      <Box variant="p">
                        3. Run the commands above to view the session replay
                      </Box>
                    </SpaceBetween>
                  </Alert>
                </SpaceBetween>
              </Container>
            </SpaceBetween>
          )}
        </Container>
      </SpaceBetween>
    </Modal>
  );
};

export default SessionReplayViewer;