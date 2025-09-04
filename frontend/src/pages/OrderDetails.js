import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
    }, 10000); // 10초마다
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
    return () => stopPolling();
  }, [fetchOrder, stopPolling]);

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
                { label: 'Automation Method', value: order.automation_method_display || order.automation_method || 'N/A' }
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
                {(order?.screenshots?.length > 0) && (
                  <Button
                    iconName="camera"
                    onClick={() => setShowLiveViewer(true)}
                  >
                    Screenshots
                  </Button>
                )}
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

  const renderScreenshotsTab = () => {
    const screenshots = order?.screenshots || [];
    
    return (
      <Container
        header={
          <Header
            variant="h3"
            actions={
              screenshots.length > 0 && (
                <Button
                  variant="primary"
                  iconName="camera"
                  onClick={() => setShowLiveViewer(true)}
                >
                  View Screenshots
                </Button>
              )
            }
          >
            Screenshots ({screenshots.length})
          </Header>
        }
      >
        <SpaceBetween size="m">
          {screenshots.length === 0 ? (
            <Box textAlign="center" color="inherit">
              <b>No screenshots available</b>
            </Box>
          ) : (
            screenshots.map((screenshot, index) => (
              <Container 
                key={index}
                header={<Header variant="h3">{screenshot.step || `Screenshot ${index + 1}`}</Header>}
              >
                <Box>
                  <img 
                    src={screenshot.url} 
                    alt={screenshot.description || `Screenshot ${index + 1}`}
                    style={{ maxWidth: '100%', height: 'auto' }}
                  />
                  {screenshot.description && (
                    <Box variant="small" color="text-body-secondary" margin={{ top: 'xs' }}>
                      {screenshot.description}
                    </Box>
                  )}
                </Box>
              </Container>
            ))
          )}
        </SpaceBetween>
      </Container>
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
            {
              id: 'screenshots',
              label: `Screenshots (${(order?.screenshots || []).length})`
            },
            ...(order?.status === 'processing' ? [{
              id: 'live-view',
              label: 'Live Browser View'
            }] : []),
            {
              id: 'raw-data',
              label: 'Raw Data'
            }
          ]}
        />

        {/* Tab Content */}
        {activeTab === 'overview' && renderOverviewTab()}
        {activeTab === 'execution-logs' && renderExecutionLogsTab()}
        {activeTab === 'screenshots' && renderScreenshotsTab()}
        {activeTab === 'live-view' && (
          <LiveBrowserViewer
            orderId={order?.id}
            isVisible={true}
          />
        )}
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