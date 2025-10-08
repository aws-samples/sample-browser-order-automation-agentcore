import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { wsService } from '../services/api';
import {
  Header,
  SpaceBetween,
  Container,
  ColumnLayout,
  Box,
  StatusIndicator,
  Button,
  Table,
  Tabs,
  Alert,
  Modal,
  KeyValuePairs,
  Popover
} from '@cloudscape-design/components';
import LiveScreenshotViewer from '../components/LiveScreenshotViewer';
import LiveBrowserViewer from '../components/LiveBrowserViewer';
import SessionReplayViewer from '../components/SessionReplayViewer';

// ResizeObserver errors are handled globally by errorSuppression utility

const OrderDetails = ({ addNotification }) => {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [showLiveViewer, setShowLiveViewer] = useState(false);
  // Removed showLiveBrowser - live view is now embedded
  const [showSessionReplay, setShowSessionReplay] = useState(false);
  const [autoShowLiveView, setAutoShowLiveView] = useState(false);
  const [manualControlEnabled, setManualControlEnabled] = useState(false);
  const [controlLoading, setControlLoading] = useState(false);
  const [novaActUpdates, setNovaActUpdates] = useState([]);
  const intervalRef = useRef(null);
  const logsContainerRef = useRef(null);

  const fetchOrder = useCallback(async () => {
    try {
      setError(null);
      const response = await fetch(`/api/orders/${orderId}`);

      if (!response.ok) {
        if (response.status === 404) {
          setOrder(null);
          setLoading(false);
          return;
        }
        throw new Error('Failed to fetch order');
      }

      const orderData = await response.json();
      const prevLogsCount = order?.execution_logs?.length || 0;
      const newLogsCount = orderData?.execution_logs?.length || 0;

      setOrder(orderData);
      setLoading(false);

      // Auto-scroll to bottom if new logs were added
      if (newLogsCount > prevLogsCount && logsContainerRef.current) {
        setTimeout(() => {
          logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
        }, 100);
      }
    } catch (error) {
      console.error('Failed to fetch order:', error);
      setError({
        type: 'network',
        message: error.message,
        status: error.response?.status
      });
      setLoading(false);
    }
  }, [orderId, order?.execution_logs?.length]);

  // Start polling function
  const startPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    intervalRef.current = setInterval(() => {
      fetchOrder();
    }, 30000); // 30초마다 (reduced since we have WebSocket updates)
  }, [fetchOrder]);

  // Stop polling function
  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    fetchOrder();

    // Set up WebSocket listeners for real-time updates
    const unsubscribeLog = wsService.subscribe('log_update', (data) => {
      if (data.order_id === orderId) {
        // Trigger a refresh to get the latest logs
        fetchOrder();
      }
    });

    const unsubscribeNovaAct = wsService.subscribe('nova_act_update', (data) => {
      if (data.order_id === orderId) {
        setNovaActUpdates(prev => [...prev, {
          ...data,
          id: Date.now() + Math.random()
        }]);

        // Also trigger a refresh for the main order data
        fetchOrder();
      }
    });

    const unsubscribeOrderUpdate = wsService.subscribe('order_updated', (data) => {
      if (data.order?.id === orderId) {
        fetchOrder();
      }
    });

    // Connect WebSocket if not already connected
    if (!wsService.ws || wsService.ws.readyState !== WebSocket.OPEN) {
      wsService.connect();
    }

    return () => {
      stopPolling();
      unsubscribeLog();
      unsubscribeNovaAct();
      unsubscribeOrderUpdate();
    };
  }, [fetchOrder, stopPolling, orderId]);

  // Handle polling based on order status
  useEffect(() => {
    if (order?.status) {
      if (['pending', 'processing'].includes(order.status)) {
        console.log(`Starting polling for order ${order?.id} with status: ${order.status}`);
        startPolling();

        // Auto-show live view for processing orders (embedded, no modals)
        if (order.status === 'processing' && !autoShowLiveView) {
          setAutoShowLiveView(true);
          // Live view is now embedded in page, no need to auto-show modals
          console.log('Order is processing, live view will be embedded in page');
        }
      } else {
        console.log(`Stopping polling for order ${order?.id} with final status: ${order.status}`);
        stopPolling();
        setAutoShowLiveView(false);
      }
    }
    return () => stopPolling();
  }, [order?.id, order?.status, startPolling, stopPolling, autoShowLiveView, order?.screenshots]);

  const handleCancelOrder = async () => {
    try {
      const response = await fetch(`/api/orders/${orderId}/cancel`, { method: 'POST' });

      if (!response.ok) {
        throw new Error('Failed to cancel order');
      }

      addNotification({
        type: 'success',
        header: 'Order Cancelled',
        content: 'Order has been cancelled successfully'
      });
      fetchOrder();
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Failed to cancel order',
        content: error.message
      });
    } finally {
      setShowCancelModal(false);
    }
  };

  const handleTakeControl = async () => {
    setControlLoading(true);
    try {
      const response = await fetch(`/api/orders/${orderId}/take-control`, { method: 'POST' });

      if (!response.ok) {
        throw new Error('Failed to take manual control');
      }

      const result = await response.json();
      if (result.success) {
        setManualControlEnabled(true);
        addNotification({
          type: 'success',
          header: 'Manual Control Enabled',
          content: 'You can now interact with the browser directly'
        });
      } else {
        throw new Error(result.error || 'Failed to enable manual control');
      }
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Failed to take control',
        content: error.message
      });
    } finally {
      setControlLoading(false);
    }
  };

  const handleReleaseControl = async () => {
    setControlLoading(true);
    try {
      const response = await fetch(`/api/orders/${orderId}/release-control`, { method: 'POST' });

      if (!response.ok) {
        throw new Error('Failed to release manual control');
      }

      const result = await response.json();
      if (result.success) {
        setManualControlEnabled(false);
        addNotification({
          type: 'success',
          header: 'Manual Control Released',
          content: 'Automation has been restored'
        });
      } else {
        throw new Error(result.error || 'Failed to release manual control');
      }
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Failed to release control',
        content: error.message
      });
    } finally {
      setControlLoading(false);
    }
  };

  const handleResumeNovaAct = async () => {
    setControlLoading(true);
    try {
      const response = await fetch(`/api/orders/${orderId}/resume-nova-act`, { method: 'POST' });

      if (!response.ok) {
        throw new Error('Failed to resume Nova Act');
      }

      const result = await response.json();
      if (result.success) {
        addNotification({
          type: 'success',
          header: 'Nova Act Resumed',
          content: 'Nova Act automation has been resumed successfully'
        });
        fetchOrder(); // Refresh order data
      } else {
        addNotification({
          type: 'warning',
          header: 'Nova Act Resume Result',
          content: result.message || 'Nova Act resumed but may require further attention'
        });
        fetchOrder(); // Refresh order data
      }
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Failed to resume Nova Act',
        content: error.message
      });
    } finally {
      setControlLoading(false);
    }
  };

  const formatTime = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    });
  };

  const calculateDuration = (createdAt, completedAt) => {
    if (!createdAt || !completedAt) return 'N/A';
    const startTime = new Date(createdAt);
    const endTime = new Date(completedAt);
    const durationMs = endTime - startTime;

    if (durationMs < 0) return 'N/A';

    if (durationMs < 1000) {
      return `${durationMs}ms`;
    }

    const seconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ${hours % 24}h ${minutes % 60}m`;
    if (hours > 0) return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    if (seconds > 0) return `${seconds}s`;
    return `${durationMs}ms`;
  };

  const getStatusIndicator = (status, tooltip = null) => {
    const statusComponent = (() => {
      switch (status) {
        case 'completed':
          return <StatusIndicator type="success">Completed</StatusIndicator>;
        case 'processing':
          return <StatusIndicator type="in-progress">Processing</StatusIndicator>;
        case 'failed':
          return <StatusIndicator type="error">Failed</StatusIndicator>;
        case 'requires_human':
          return <StatusIndicator type="warning">Requires Human</StatusIndicator>;
        case 'cancelled':
          return <StatusIndicator type="stopped">Cancelled</StatusIndicator>;
        default:
          return <StatusIndicator type="pending">Pending</StatusIndicator>;
      }
    })();

    // Add popover for failed status with error details
    if (status === 'failed' && tooltip) {
      return (
        <Popover
          header="Order Failed"
          content={tooltip}
          dismissButton={false}
          position="top"
          size="medium"
        >
          {statusComponent}
        </Popover>
      );
    }

    return statusComponent;
  };

  const renderOverviewTab = () => {
    if (!order) return null;

    return (
      <SpaceBetween size="m">
        <Container header={<Header variant="h3">Order Information</Header>}>
          <ColumnLayout columns={3}>
            <KeyValuePairs
              columns={1}
              items={[
                { label: 'Order ID', value: order?.id || 'N/A' },
                { label: 'Status', value: getStatusIndicator(order.status, order.status_tooltip) },
                { label: 'Retailer', value: order.retailer || 'N/A' },
                { label: 'Automation Method', value: order.automation_method_display || order.automation_method || 'N/A' },
                {
                  label: 'AI Model',
                  value: order?.ai_model ? (
                    <span title={order.ai_model}>
                      {order.ai_model.includes('claude-sonnet-4') ? 'Claude Sonnet 4' :
                        order.ai_model.includes('claude-3-5-sonnet') ? 'Claude 3.5 Sonnet' :
                          order.ai_model.includes('claude-sonnet') ? 'Claude 3.5 Sonnet' :
                            order.ai_model.includes('claude-haiku') ? 'Claude 3.5 Haiku' :
                              order.ai_model.includes('claude-opus') ? 'Claude 3 Opus' :
                                order.ai_model.includes('gpt-4') ? 'GPT-4' :
                                  order.ai_model.includes('gpt-3.5') ? 'GPT-3.5' :
                                    order.ai_model.length > 50 ? `${order.ai_model.substring(0, 30)}...` :
                                      order.ai_model}
                    </span>
                  ) : 'System Default'
                }
              ]}
            />
            <KeyValuePairs
              columns={1}
              items={[
                { label: 'Product Name', value: order.product?.name || 'N/A' },
                { label: 'Size', value: (order.product?.size && order.product.size !== '-') ? order.product.size : 'N/A' },
                { label: 'Color', value: (order.product?.color && order.product.color !== '-') ? order.product.color : 'N/A' },
                { label: 'Quantity', value: order.product?.quantity || 'N/A' }
              ]}
            />
            <KeyValuePairs
              columns={1}
              items={[
                { label: 'Created', value: formatTime(order.created_at) },
                { label: 'Updated', value: formatTime(order.updated_at) },
                { label: 'Completed', value: formatTime(order.completed_at) },
                { label: 'Duration', value: calculateDuration(order.created_at, order.completed_at) }
              ]}
            />
          </ColumnLayout>
        </Container>

        {/* Execution Logs - CloudWatch Style */}
        <Container
          header={
            <Header
              variant="h3"
              counter={`(${(order.execution_logs || []).length})`}
              description="Real-time automation agent logs"
            >
              Execution Logs
            </Header>
          }
          fitHeight
        >
          <div
            ref={logsContainerRef}
            style={{
              height: '400px',
              overflowY: 'auto',
              padding: '0',
              backgroundColor: '#232f3e',
              fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
              fontSize: '13px',
              lineHeight: '1.4'
            }}
            role="region"
            aria-label="Execution logs"
          >
            {(order.execution_logs || []).length === 0 ? (
              <div style={{
                padding: '20px',
                textAlign: 'center',
                color: '#879196'
              }}>
                <div>No execution logs yet</div>
                <div style={{ fontSize: '12px', marginTop: '8px' }}>
                  Logs will appear here as the automation agent processes your order
                </div>
              </div>
            ) : (
              <div>
                {order.execution_logs.map((log, index) => {
                  const timestamp = new Date(log.timestamp).toISOString();
                  const logLevel = log.level || 'INFO';
                  const logColor = logLevel === 'ERROR' ? '#ff6b6b' :
                    logLevel === 'WARNING' ? '#ffa726' : '#e8eaed';

                  return (
                    <div
                      key={index}
                      style={{
                        padding: '4px 12px',
                        borderBottom: '1px solid #3c4043',
                        color: logColor,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word'
                      }}
                    >
                      <span style={{ color: '#9aa0a6' }}>{timestamp}</span>
                      <span style={{ color: '#8ab4f8', marginLeft: '12px' }}>[{logLevel}]</span>
                      <span style={{ marginLeft: '12px' }}>{log.message}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Container>

        {/* Nova Act Real-time Updates */}
        {order.automation_method === 'nova_act' && novaActUpdates.length > 0 && (
          <Container
            header={
              <Header
                variant="h3"
                counter={`(${novaActUpdates.length})`}
                description="Real-time Nova Act automation updates"
              >
                Nova Act Live Updates
              </Header>
            }
          >
            <div style={{
              maxHeight: '300px',
              overflowY: 'auto',
              padding: '0',
              backgroundColor: '#f8f9fa',
              border: '1px solid #e9ecef',
              borderRadius: '4px'
            }}>
              {novaActUpdates.slice(-10).map((update) => {
                const timestamp = new Date(update.timestamp).toLocaleTimeString();
                const getUpdateColor = (type) => {
                  switch (type) {
                    case 'error_occurred': return '#dc3545';
                    case 'agent_thinking': return '#6f42c1';
                    case 'action_performed': return '#28a745';
                    case 'command_started': return '#007bff';
                    case 'report_available': return '#17a2b8';
                    default: return '#6c757d';
                  }
                };

                return (
                  <div
                    key={update.id}
                    style={{
                      padding: '8px 12px',
                      borderBottom: '1px solid #e9ecef',
                      fontSize: '13px'
                    }}
                  >
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      marginBottom: '4px'
                    }}>
                      <span style={{
                        color: '#6c757d',
                        fontSize: '12px'
                      }}>
                        {timestamp}
                      </span>
                      <span style={{
                        color: getUpdateColor(update.update_type),
                        fontWeight: 'bold',
                        fontSize: '12px'
                      }}>
                        {update.update_type.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>
                    <div style={{
                      color: '#495057',
                      marginLeft: '16px'
                    }}>
                      {update.data.thought && `Thought: ${update.data.thought}`}
                      {update.data.action && `Action: ${update.data.action}`}
                      {update.data.command && `Command: ${update.data.command}`}
                      {update.data.error && `Error: ${update.data.error}`}
                      {update.data.html_path && `Report available (${update.data.total_steps} steps)`}
                    </div>
                  </div>
                );
              })}
            </div>
          </Container>
        )}

        {(order.customer_name || order.shipping_address) && (
          <Container header={<Header variant="h3">Customer & Shipping</Header>}>
            <ColumnLayout columns={2}>
              {order.customer_name && (
                <KeyValuePairs
                  columns={1}
                  items={[
                    { label: 'Customer Name', value: order.customer_name },
                    { label: 'Email', value: order.customer_email || 'N/A' }
                  ]}
                />
              )}
              {order.shipping_address && (
                <Box>
                  <Box variant="awsui-key-label">Shipping Address</Box>
                  <Box>
                    {order.shipping_address.first_name} {order.shipping_address.last_name}<br />
                    {order.shipping_address.address_line_1}<br />
                    {order.shipping_address.address_line_2 && (
                      <>{order.shipping_address.address_line_2}<br /></>
                    )}
                    {order.shipping_address.city}, {order.shipping_address.state} {order.shipping_address.postal_code}<br />
                    {order.shipping_address.country}
                  </Box>
                </Box>
              )}
            </ColumnLayout>
          </Container>
        )}
      </SpaceBetween>
    );
  };

  const renderExecutionLogsTab = () => {
    const logs = order?.execution_logs || [];

    return (
      <Table
        columnDefinitions={[
          {
            id: 'timestamp',
            header: 'Timestamp',
            cell: item => formatTime(item.timestamp),
            sortingField: 'timestamp'
          },
          {
            id: 'level',
            header: 'Level',
            cell: item => (
              <StatusIndicator
                type={item.level === 'ERROR' ? 'error' :
                  item.level === 'WARNING' ? 'warning' :
                    item.level === 'INFO' ? 'info' : 'success'}
              >
                {item.level}
              </StatusIndicator>
            )
          },
          {
            id: 'message',
            header: 'Message',
            cell: item => item.message
          },
          {
            id: 'step',
            header: 'Step',
            cell: item => item.step || 'N/A'
          }
        ]}
        items={logs}
        sortingDisabled={false}
        empty={
          <Box textAlign="center" color="inherit">
            <b>No execution logs available</b>
          </Box>
        }
        header={
          <Header
            counter={`(${logs.length})`}
            description="Detailed execution logs from the automation agent"
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                {/* TEMPORARILY DISABLED - Screenshots Button - Will be re-enabled later */}
                {/* 
                {(order?.screenshots?.length > 0) && (
                  <Button
                    iconName="camera"
                    onClick={() => setShowLiveViewer(true)}
                  >
                    Screenshots
                  </Button>
                )}
                */}
                {/* END TEMPORARILY DISABLED - Screenshots Button */}

                <Button
                  iconName="play"
                  onClick={() => setShowSessionReplay(true)}
                >
                  Session Replay
                </Button>
              </SpaceBetween>
            }
          >
            Execution Logs
          </Header>
        }
      />
    );
  };



  if (loading) {
    return (
      <SpaceBetween size="l">
        <Header variant="h1">Order Details</Header>
        <Container>
          <Box textAlign="center" padding={{ vertical: "xxl" }}>
            <SpaceBetween size="m">
              <StatusIndicator type="loading">
                <Box fontSize="heading-m">Loading order details...</Box>
              </StatusIndicator>
              <Box variant="p" color="text-body-secondary">
                Please wait while we fetch the order information.
              </Box>
            </SpaceBetween>
          </Box>
        </Container>
      </SpaceBetween>
    );
  }

  if (error) {
    return (
      <SpaceBetween size="l">
        <Header variant="h1">Order Details</Header>
        <Container>
          <SpaceBetween size="l">
            <Box textAlign="center" padding={{ vertical: "xxl" }}>
              <SpaceBetween size="m">
                <Box>
                  <StatusIndicator type="error" iconAriaLabel="Error">
                    <Box fontSize="heading-l" fontWeight="bold">Failed to Load Order</Box>
                  </StatusIndicator>
                </Box>
                <Box variant="p" color="text-body-secondary">
                  {error.type === 'network' ?
                    'Unable to connect to the server. Please check your connection and try again.' :
                    error.message}
                  <br />
                  {error.status && <Box variant="small">Error code: {error.status}</Box>}
                </Box>
                <SpaceBetween direction="horizontal" size="s">
                  <Button
                    variant="primary"
                    iconName="refresh"
                    onClick={() => {
                      setLoading(true);
                      setError(null);
                      fetchOrder();
                    }}
                  >
                    Try Again
                  </Button>
                </SpaceBetween>
              </SpaceBetween>
            </Box>
          </SpaceBetween>
        </Container>
      </SpaceBetween>
    );
  }

  if (!order) {
    return (
      <SpaceBetween size="l">
        <Header variant="h1">Order Details</Header>
        <Container>
          <SpaceBetween size="l">
            <Box textAlign="center" padding={{ vertical: "xxl" }}>
              <SpaceBetween size="m">
                <Box>
                  <StatusIndicator type="error" iconAriaLabel="Error">
                    <Box fontSize="heading-l" fontWeight="bold">Order Not Found</Box>
                  </StatusIndicator>
                </Box>
                <Box variant="p" color="text-body-secondary">
                  The order you're looking for doesn't exist or may have been deleted.
                  This could happen if the order was cleaned up or the ID is incorrect.
                </Box>
                <Box variant="small" color="text-body-secondary">
                  Order ID: <Box variant="code" display="inline">{orderId}</Box>
                </Box>
                <SpaceBetween direction="horizontal" size="s">
                  <Button
                    iconName="arrow-left"
                    onClick={() => navigate('/dashboard')}
                  >
                    Back to Dashboard
                  </Button>
                </SpaceBetween>
              </SpaceBetween>
            </Box>
          </SpaceBetween>
        </Container>
      </SpaceBetween>
    );
  }

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        actions={
          <SpaceBetween direction="horizontal" size="xs">
            <Button
              iconName="refresh"
              onClick={fetchOrder}
              loading={loading}
            >
              Refresh
            </Button>
            {order?.status === 'processing' && order?.automation_method === 'strands' && (
              <>
                {!manualControlEnabled ? (
                  <Button
                    variant="normal"
                    iconName="settings"
                    onClick={handleTakeControl}
                    loading={controlLoading}
                  >
                    Take Control
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    iconName="play"
                    onClick={handleReleaseControl}
                    loading={controlLoading}
                  >
                    Release Control
                  </Button>
                )}
              </>
            )}
            {order?.status === 'requires_human' && order?.automation_method === 'nova_act' && (
              <Button
                variant="primary"
                iconName="play"
                onClick={handleResumeNovaAct}
                loading={controlLoading}
              >
                Resume Nova Act
              </Button>
            )}
            {order?.status === 'pending' && (
              <Button
                variant="normal"
                onClick={() => setShowCancelModal(true)}
              >
                Cancel Order
              </Button>
            )}
            <Button
              iconName="arrow-left"
              onClick={() => navigate('/dashboard')}
            >
              Back to Dashboard
            </Button>
          </SpaceBetween>
        }
      >
        Order Details: {order.product?.name || 'Unknown Product'}
      </Header>



      {/* Manual Control Status */}
      {manualControlEnabled && (
        <Alert type="info" header="Manual Control Active">
          You have manual control of the browser. You can interact with the page directly.
          Click "Release Control" to return to automation.
        </Alert>
      )}

      {/* Nova Act CAPTCHA Status */}
      {order?.status === 'requires_human' && order?.automation_method === 'nova_act' && (
        <Alert type="warning" header="CAPTCHA Detected - Human Intervention Required">
          Nova Act has encountered a CAPTCHA or security challenge that requires human intervention.
          Please use the Live Browser View to solve the CAPTCHA, then click "Resume Nova Act" to continue automation.
        </Alert>
      )}

      {/* Error Display */}
      {order.error && (
        <Alert type="error" header="Order Failed">
          {order.error}
        </Alert>
      )}

      {/* Results Tabs */}
      <Container>
        <Tabs
          activeTabId={activeTab}
          onChange={({ detail }) => setActiveTab(detail.activeTabId)}
          tabs={[
            {
              id: 'overview',
              label: 'Overview'
            },
            {
              id: 'execution-logs',
              label: `Execution Logs (${(order?.execution_logs || []).length})`
            },
            /* TEMPORARILY DISABLED - Screenshots Tab - Will be re-enabled later */
            /*
            {
              id: 'screenshots',
              label: `Screenshots (${(order?.screenshots || []).length})`
            },
            */
            /* END TEMPORARILY DISABLED - Screenshots Tab */
            ...(['processing', 'requires_human'].includes(order?.status) ? [{
              id: 'live-view',
              label: 'Live Browser View'
            }] : []),

            /* TEMPORARILY DISABLED - Raw Data Tab - Will be re-enabled later */
            /*
            {
              id: 'raw-data',
              label: 'Raw Data'
            }
            */
            /* END TEMPORARILY DISABLED - Raw Data Tab */
          ]}
        />

        {/* Tab Content */}
        {activeTab === 'overview' && renderOverviewTab()}
        {activeTab === 'execution-logs' && renderExecutionLogsTab()}

        {/* TEMPORARILY DISABLED - Screenshots Tab Content - Will be re-enabled later */}
        {/* {activeTab === 'screenshots' && renderScreenshotsTab()} */}
        {/* END TEMPORARILY DISABLED - Screenshots Tab Content */}

        {activeTab === 'live-view' && (
          <LiveBrowserViewer
            orderId={order?.id}
            isVisible={true}
          />
        )}

        {/* TEMPORARILY DISABLED - Raw Data Tab Content - Will be re-enabled later */}
        {/* 
        {activeTab === 'raw-data' && (
          <Container
            header={
              <Header
                variant="h3"
                actions={
                  <Button
                    iconName="copy"
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(order, null, 2));
                      addNotification({
                        type: 'success',
                        header: 'Copied to clipboard',
                        content: 'Raw data has been copied to clipboard'
                      });
                    }}
                  >
                    Copy
                  </Button>
                }
              >
                Raw JSON Data
              </Header>
            }
          >
            <Box fontFamily="monospace" padding="s">
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {JSON.stringify(order, null, 2)}
              </pre>
            </Box>
          </Container>
        )}
        */}
        {/* END TEMPORARILY DISABLED - Raw Data Tab Content */}
      </Container>

      {/* Cancel Order Modal */}
      <Modal
        visible={showCancelModal}
        onDismiss={() => setShowCancelModal(false)}
        header="Cancel Order"
        closeAriaLabel="Close modal"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setShowCancelModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleCancelOrder}>
                Confirm
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween size="m">
          <Box variant="span">Are you sure you want to cancel this order?</Box>
          <Alert type="warning">
            This action cannot be undone. The order will be marked as cancelled and removed from the processing queue.
          </Alert>
        </SpaceBetween>
      </Modal>

      {/* Live Screenshot Viewer */}
      <LiveScreenshotViewer
        order={order}
        isVisible={showLiveViewer}
        onClose={() => setShowLiveViewer(false)}
      />

      {/* Live Browser View is now embedded in page, no modal needed */}

      {/* Session Replay Viewer */}
      <SessionReplayViewer
        order={order}
        isVisible={showSessionReplay}
        onClose={() => setShowSessionReplay(false)}
      />


    </SpaceBetween>
  );
};

export default OrderDetails;