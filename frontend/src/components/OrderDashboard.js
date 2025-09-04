/**
 * Order Dashboard - Production Order Automation System
 * Following Cloudscape Design System patterns and best practices
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Button,
  ButtonDropdown,
  Table,
  Box,
  StatusIndicator,
  Alert,
  ColumnLayout,
  KeyValuePairs,
  Modal,
  Pagination,
  CollectionPreferences,
  PropertyFilter,
  Link,
  FileUpload,
  FormField,
  Popover
} from '@cloudscape-design/components';

import CreateOrderWizard from './CreateOrderWizard';
import useResizeObserverFix from '../hooks/useResizeObserverFix';

// ResizeObserver errors are handled globally by errorSuppression utility

const OrderDashboard = ({ addNotification }) => {
  const [orders, setOrders] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [retailers, setRetailers] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedItems, setSelectedItems] = useState([]);
  const [preferences, setPreferences] = useState({
    pageSize: 20,
    visibleContent: ['id', 'retailer', 'product', 'status', 'method', 'created']
  });
  const [filtering, setFiltering] = useState({
    tokens: [],
    operation: 'and'
  });
  const [statusFilter, setStatusFilter] = useState(null);
  const [currentPageIndex, setCurrentPageIndex] = useState(1);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [showCreateOrderWizard, setShowCreateOrderWizard] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [errorCount, setErrorCount] = useState(0);
  const [hasError, setHasError] = useState(false);
  const [queueStatus, setQueueStatus] = useState('active'); // active, paused
  const [uploadFile, setUploadFile] = useState([]);
  const [uploading, setUploading] = useState(false);

  // Use the ResizeObserver fix hook
  const { observe } = useResizeObserverFix();

  const fetchDashboardData = useCallback(async () => {
    // Skip if we've had too many errors
    if (errorCount >= 5) {
      setHasError(true);
      return;
    }

    try {
      const [ordersRes, metricsRes, retailersRes, queueRes] = await Promise.all([
        fetch('/api/orders'),
        fetch('/api/metrics/performance'),
        fetch('/api/config/retailers'),
        fetch('/api/queue/status')
      ]);

      if (!ordersRes.ok || !metricsRes.ok || !retailersRes.ok || !queueRes.ok) {
        throw new Error('Failed to fetch dashboard data');
      }

      const ordersData = await ordersRes.json();
      const metricsData = await metricsRes.json();
      const retailersData = await retailersRes.json();
      const queueData = await queueRes.json();

      setOrders(Array.isArray(ordersData.orders) ? ordersData.orders : []);
      setMetrics(metricsData.metrics);
      setRetailers(retailersData);
      setQueueStatus(queueData.status || 'active');
      setLoading(false);
      setErrorCount(0);
      setHasError(false);

    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      setErrorCount(prev => {
        const newCount = prev + 1;
        
        // Only show notification for first error
        if (prev === 0) {
          addNotification({
            type: 'error',
            header: 'Dashboard Error',
            content: 'Dashboard temporarily unavailable. Please try again later.'
          });
        }

        // Stop polling after 5 errors
        if (newCount >= 5) {
          setHasError(true);
        }
        
        return newCount;
      });
      
      setLoading(false);
    }
  }, [addNotification, errorCount]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Handle ResizeObserver issues on component mount
  useEffect(() => {
    const handleResize = () => {
      // Force a small delay to prevent ResizeObserver loops
      setTimeout(() => {
        // Trigger a gentle re-render if needed
        if (document.body) {
          document.body.style.transform = 'translateZ(0)';
          requestAnimationFrame(() => {
            document.body.style.transform = '';
          });
        }
      }, 100);
    };

    window.addEventListener('resize', handleResize, { passive: true });
    
    // Initial call to stabilize layout
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // 별도 useEffect로 폴링 관리 - 조건부로만 실행
  useEffect(() => {
    // 활성 주문이 있을 때만 폴링 시작
    const hasActiveOrders = orders.some(order => 
      ['pending', 'processing'].includes(order.status)
    );
    
    if (hasActiveOrders && !hasError && errorCount < 5) {
      console.log('Starting polling - active orders detected');
      const interval = setInterval(fetchDashboardData, 30000); // 30초마다
      
      return () => {
        console.log('Stopping polling');
        clearInterval(interval);
      };
    }
  }, [orders, hasError, errorCount, fetchDashboardData]);

  const createOrder = async (method = 'strands_agent') => {
    try {
      const response = await fetch(`/api/test/sample-order?automation_method=${method}`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error('Failed to create order');
      }
      
      const result = await response.json();
      
      addNotification({
        type: 'success',
        header: 'Order Created',
        content: `Order created with ${method}: ${result.order_id}`
      });
      fetchDashboardData();
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Order Creation Failed',
        content: `Failed to create order: ${error.message}`
      });
    }
  };

  const handleQueuePause = async () => {
    try {
      const response = await fetch('/api/queue/pause', { method: 'POST' });
      
      if (!response.ok) {
        throw new Error('Failed to pause queue');
      }
      
      addNotification({
        type: 'success',
        header: 'Queue Paused',
        content: 'Order processing queue has been paused successfully'
      });
      
      setQueueStatus('paused');
      fetchDashboardData();
      
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Queue Pause Failed',
        content: `Failed to pause queue: ${error.message}`
      });
    }
  };

  const handleQueueResume = async () => {
    try {
      const response = await fetch('/api/queue/resume', { method: 'POST' });
      
      if (!response.ok) {
        throw new Error('Failed to resume queue');
      }
      
      addNotification({
        type: 'success',
        header: 'Queue Resumed',
        content: 'Order processing queue has been resumed successfully'
      });
      
      setQueueStatus('active');
      fetchDashboardData();
      
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Queue Resume Failed',
        content: `Failed to resume queue: ${error.message}`
      });
    }
  };

  const handleDeleteCompleted = async () => {
    try {
      const response = await fetch('/api/orders/cleanup/completed', { method: 'DELETE' });
      
      if (!response.ok) {
        throw new Error('Failed to delete completed orders');
      }
      
      const result = await response.json();
      
      addNotification({
        type: 'success',
        header: 'Orders Deleted',
        content: `${result.deleted_count || 0} completed orders have been deleted`
      });
      
      fetchDashboardData();
      
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Delete Failed',
        content: `Failed to delete completed orders: ${error.message}`
      });
    }
  };

  const handleUploadCSV = () => {
    setShowUploadModal(true);
  };

  const handleFileUpload = async () => {
    if (!uploadFile || uploadFile.length === 0) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile[0]);

      const response = await fetch('/api/orders/upload-csv', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error('Failed to upload CSV file');
      }

      const result = await response.json();

      addNotification({
        type: 'success',
        header: 'CSV Uploaded',
        content: `${result.created_count || 0} orders created from CSV file`
      });

      setShowUploadModal(false);
      setUploadFile([]);
      fetchDashboardData();

    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Upload Failed',
        content: `Failed to upload CSV: ${error.message}`
      });
    } finally {
      setUploading(false);
    }
  };

  const downloadSampleCSV = () => {
    // Use the public sample file instead of inline content
    const link = document.createElement('a');
    link.href = '/sample-orders.csv';
    link.download = 'sample-orders.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleRetryOrder = async (orderId) => {
    try {
      const response = await fetch(`/api/orders/${orderId}/retry`, { method: 'POST' });
      if (response.ok) {
        addNotification({
          type: 'success',
          header: 'Order Retry',
          content: `Order ${orderId.substring(0, 8)} has been queued for retry`
        });
        fetchDashboardData();
      } else {
        throw new Error('Failed to retry order');
      }
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Retry Failed',
        content: `Failed to retry order: ${error.message}`
      });
    }
  };

  const handleBulkCancel = async () => {
    if (selectedItems.length === 0) return;

    try {
      const cancelPromises = selectedItems
        .filter(order => order.status === 'pending')
        .map(order => 
          fetch(`/api/orders/${order.id}/cancel`, { method: 'POST' })
        );

      await Promise.all(cancelPromises);
      
      addNotification({
        type: 'success',
        header: 'Orders Cancelled',
        content: `${cancelPromises.length} order(s) cancelled successfully`
      });
      setSelectedItems([]);
      fetchDashboardData();
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Cancellation Failed',
        content: `Failed to cancel orders: ${error.message}`
      });
    } finally {
      setShowCancelModal(false);
    }
  };

  const canCancelSelected = () => {
    return selectedItems.every(order => order.status === 'pending');
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

  const formatTime = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    });
  };

  const getFilteredOrders = useMemo(() => {
    if (!Array.isArray(orders)) {
      return [];
    }
    let filtered = [...orders];
    
    filtering.tokens.forEach(token => {
      const { propertyKey, value, operator } = token;
      filtered = filtered.filter(order => {
        const orderValue = order[propertyKey];
        switch (operator) {
          case '=':
            return orderValue === value;
          case '!=':
            return orderValue !== value;
          case ':':
            return String(orderValue).toLowerCase().includes(value.toLowerCase());
          case '!:':
            return !String(orderValue).toLowerCase().includes(value.toLowerCase());
          default:
            return true;
        }
      });
    });
    
    return filtered;
  }, [orders, filtering]);

  const getPaginatedOrders = useMemo(() => {
    const startIndex = (currentPageIndex - 1) * preferences.pageSize;
    const endIndex = startIndex + preferences.pageSize;
    return getFilteredOrders.slice(startIndex, endIndex);
  }, [getFilteredOrders, currentPageIndex, preferences.pageSize]);

  const orderColumns = [
    {
      id: 'id',
      header: 'Order ID',
      cell: item => (
        <Link href={`/orders/${item.id}`}>
          {item.id?.substring(0, 8) || 'N/A'}
        </Link>
      ),
      sortingField: 'id',
      isRowHeader: true
    },
    {
      id: 'retailer',
      header: 'Retailer',
      cell: item => retailers[item.retailer]?.name || item.retailer,
      sortingField: 'retailer'
    },
    {
      id: 'product',
      header: 'Product',
      cell: item => {
        const product = item.product;
        if (!product || !product.name) return 'N/A';
        
        const details = [];
        if (product.size && product.size !== '-' && product.size !== 'N/A') details.push(product.size);
        if (product.color && product.color !== '-' && product.color !== 'N/A') details.push(product.color);
        
        return (
          <Box>
            <div>{product.name}</div>
            {details.length > 0 && (
              <Box variant="small" color="text-body-secondary">
                {details.join(' • ')}
              </Box>
            )}
          </Box>
        );
      }
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => getStatusIndicator(item.status, item.status_tooltip),
      sortingField: 'status'
    },
    {
      id: 'method',
      header: 'Method',
      cell: item => item.automation_method_display || item.automation_method || 'N/A',
      sortingField: 'automation_method'
    },
    {
      id: 'created',
      header: 'Created',
      cell: item => formatTime(item.created_at),
      sortingField: 'created_at'
    },

  ];

  const propertyFilteringProperties = [
    {
      key: 'status',
      operators: ['=', '!='],
      propertyLabel: 'Status',
      groupValuesLabel: 'Status values'
    },
    {
      key: 'retailer',
      operators: ['=', '!=', ':', '!:'],
      propertyLabel: 'Retailer',
      groupValuesLabel: 'Retailer values'
    }
  ];

  const handleStatusFilter = (status) => {
    setStatusFilter(status);
    setFiltering({
      tokens: [{ propertyKey: 'status', operator: '=', value: status }],
      operation: 'and'
    });
    setCurrentPageIndex(1);
  };

  const metricsItems = useMemo(() => {
    if (!metrics) return [];
    
    return [
      { label: 'Total Orders', value: metrics.overall_metrics?.total_orders || 0 },
      { label: 'Success Rate', value: `${Math.round(metrics.overall_metrics?.success_rate || 0)}%` },
      { label: 'Avg Processing Time', value: `${Math.round(metrics.overall_metrics?.avg_processing_time || 0)}s` },
      { label: 'Orders Today', value: metrics.overall_metrics?.orders_today || 0 },
      { 
        label: 'Review Queue', 
        value: (
          <Link 
            onFollow={() => handleStatusFilter('requires_human')}
            variant={statusFilter === 'requires_human' ? 'primary' : 'secondary'}
          >
            {metrics.review_queue || 0}
          </Link>
        )
      },
      { 
        label: 'Failed Orders', 
        value: (
          <Link 
            onFollow={() => handleStatusFilter('failed')}
            variant={statusFilter === 'failed' ? 'primary' : 'secondary'}
          >
            {metrics.failed || 0}
          </Link>
        )
      }
    ];
  }, [metrics, statusFilter]);

  const filteredOrders = getFilteredOrders;
  const paginatedOrders = getPaginatedOrders;

  if (hasError) {
    return (
      <SpaceBetween size="l">
        <Header variant="h1">Order Automation Dashboard</Header>
        <Alert
          type="error"
          header="Dashboard Service Unavailable"
          action={
            <Button
              onClick={() => {
                setErrorCount(0);
                setHasError(false);
                fetchDashboardData();
              }}
            >
              Retry
            </Button>
          }
        >
          The dashboard service is temporarily unavailable. This may be due to connectivity issues.
        </Alert>
      </SpaceBetween>
    );
  }

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="AI-powered e-commerce order automation system"
        actions={
          <SpaceBetween direction="horizontal" size="xs">
            {selectedItems.length > 0 && canCancelSelected() && (
              <Button 
                iconName="close"
                onClick={() => setShowCancelModal(true)}
              >
                Cancel Selected ({selectedItems.length})
              </Button>
            )}
          </SpaceBetween>
        }
        counter={`(${filteredOrders.length})`}
      >
        Order Automation Dashboard
      </Header>

      {/* Metrics Overview */}
      <Container
        header={<Header variant="h2">System Metrics Overview</Header>}
      >
        <ColumnLayout columns={3}>
          <Container header={<Header variant="h3">Success Metrics</Header>}>
            <KeyValuePairs items={metricsItems.slice(0, 2)} />
          </Container>
          
          <Container header={<Header variant="h3">Performance Metrics</Header>}>
            <KeyValuePairs items={metricsItems.slice(2, 4)} />
          </Container>

          <Container header={<Header variant="h3">Capacity Metrics</Header>}>
            <KeyValuePairs items={metricsItems.slice(4, 6)} />
          </Container>
        </ColumnLayout>
      </Container>

      {/* Orders Table */}
      <Container
        header={
          <Header
            variant="h2"
            counter={`(${filteredOrders.length})`}
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                <Button iconName="refresh" onClick={fetchDashboardData} loading={loading}>
                  Refresh
                </Button>
                <ButtonDropdown
                  variant="primary"
                  items={[
                    { 
                      id: 'create-wizard', 
                      text: 'Create New'
                    },
                    { 
                      id: 'upload-csv', 
                      text: 'Upload CSV'
                    },
                    { 
                      id: 'pause-queue', 
                      text: 'Pause',
                      disabled: queueStatus === 'paused'
                    },
                    { 
                      id: 'resume-queue', 
                      text: 'Resume',
                      disabled: queueStatus === 'active'
                    },
                    { 
                      id: 'delete-completed', 
                      text: 'Delete',
                      disabled: orders.some(order => order.status === 'processing')
                    }
                  ]}
                  onItemClick={(e) => {
                    switch(e.detail.id) {
                      case 'create-wizard':
                        window.location.href = '/orders/create';
                        break;
                      case 'upload-csv':
                        handleUploadCSV();
                        break;
                      case 'pause-queue':
                        handleQueuePause();
                        break;
                      case 'resume-queue':
                        handleQueueResume();
                        break;
                      case 'delete-completed':
                        handleDeleteCompleted();
                        break;
                      default:
                        break;
                    }
                  }}
                >
                  Actions
                </ButtonDropdown>
              </SpaceBetween>
            }
          >
            Orders
          </Header>
        }
      >
        <Table
          columnDefinitions={orderColumns}
          items={paginatedOrders}
          loading={loading}
          loadingText="Loading orders..."
          selectedItems={selectedItems}
          onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
          selectionType="multi"
          ariaLabels={{
            selectionGroupLabel: "Items selection",
            allItemsSelectionLabel: ({ selectedItems }) =>
              `${selectedItems.length} ${selectedItems.length === 1 ? "item" : "items"} selected`,
            itemSelectionLabel: ({ selectedItems }, item) => {
              const isItemSelected = selectedItems.filter(i => i.id === item.id).length;
              return `${item.product?.name || 'Order'} is ${isItemSelected ? "" : "not "}selected`;
            }
          }}
          filter={
            <PropertyFilter
              query={filtering}
              onChange={({ detail }) => {
                setFiltering(detail);
                setCurrentPageIndex(1);
              }}
              countText={`${filteredOrders.length} matches`}
              expandToViewport={true}
              filteringProperties={propertyFilteringProperties}
              filteringPlaceholder="Find orders"
            />
          }
          pagination={
            <Pagination
              currentPageIndex={currentPageIndex}
              onChange={({ detail }) => setCurrentPageIndex(detail.currentPageIndex)}
              pagesCount={Math.ceil(filteredOrders.length / preferences.pageSize)}
              ariaLabels={{
                nextPageLabel: "Next page",
                previousPageLabel: "Previous page",
                pageLabel: pageNumber => `Page ${pageNumber} of all pages`
              }}
            />
          }
          preferences={
            <CollectionPreferences
              title="Preferences"
              confirmLabel="Confirm"
              cancelLabel="Cancel"
              preferences={preferences}
              onConfirm={({ detail }) => setPreferences(detail)}
              pageSizePreference={{
                title: "Page size",
                options: [
                  { value: 10, label: "10 orders" },
                  { value: 20, label: "20 orders" },
                  { value: 50, label: "50 orders" }
                ]
              }}
              visibleContentPreference={{
                title: "Select visible columns",
                options: [{
                  label: "Order properties",
                  options: orderColumns.map(({ id, header }) => ({
                    id,
                    label: header
                  }))
                }]
              }}
            />
          }
          trackBy="id"
          empty={
            <Box margin={{ vertical: 'xs' }} textAlign="center" color="inherit">
              <SpaceBetween size="m">
                <b>No orders</b>
                <Box variant="p" color="inherit">
                  Create a test order to see automation in action.
                </Box>
                <Button 
                  variant="primary"
                  iconName="gen-ai"
                  onClick={() => window.location.href = '/orders/create'}
                >
                  Create Order
                </Button>
              </SpaceBetween>
            </Box>
          }
        />
      </Container>

      {/* Create Order Wizard */}
      {showCreateOrderWizard && (
        <CreateOrderWizard
          visible={showCreateOrderWizard}
          onDismiss={() => setShowCreateOrderWizard(false)}
          onOrderCreated={(orderId) => {
            addNotification({
              type: 'success',
              header: 'Order Created',
              content: `Order ${orderId} has been created successfully`
            });
            fetchDashboardData();
            setShowCreateOrderWizard(false);
          }}
          addNotification={addNotification}
        />
      )}

      {/* CSV Upload Modal */}
      <Modal
        visible={showUploadModal}
        onDismiss={() => setShowUploadModal(false)}
        header="Upload Orders CSV"
        closeAriaLabel="Close modal"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setShowUploadModal(false)}>
                Cancel
              </Button>
              <Button onClick={downloadSampleCSV}>
                Download Sample
              </Button>
              <Button 
                variant="primary" 
                onClick={handleFileUpload}
                disabled={!uploadFile || uploadFile.length === 0}
                loading={uploading}
              >
                Upload
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween size="m">
          <Box variant="span">
            Upload a CSV file to create multiple orders at once.
          </Box>
          
          <Alert type="info">
            <Box>
              <strong>Required fields:</strong> customer_name, customer_email, retailer, product_url, product_name, 
              shipping_first_name, shipping_last_name, shipping_address_1, shipping_city, shipping_state, 
              shipping_postal_code, shipping_country
            </Box>
            <Box margin={{ top: 'xs' }}>
              <strong>Optional fields:</strong> product_size, product_color, product_quantity, product_price, 
              automation_method, ai_model, priority, instructions
            </Box>
            <Box margin={{ top: 'xs' }} variant="small" color="text-body-secondary">
              <strong>Demo tip:</strong> Leave size/color empty for agent auto-detection. Use instructions field for specific guidance.
            </Box>
          </Alert>

          <FormField
            label="Select CSV file"
            description="Upload a CSV file with order data"
          >
            <FileUpload
              onChange={({ detail }) => setUploadFile(detail.value)}
              value={uploadFile}
              i18nStrings={{
                uploadButtonText: e => e ? "Choose files" : "Choose file",
                dropzoneText: e => e ? "Drop files to upload" : "Drop file to upload",
                removeFileAriaLabel: e => `Remove file ${e + 1}`,
                limitShowFewer: "Show fewer files",
                limitShowMore: "Show more files",
                errorIconAriaLabel: "Error",
                warningIconAriaLabel: "Warning"
              }}
              showFileLastModified
              showFileSize
              accept=".csv"
              constraintText="CSV files only, max 10MB"
            />
          </FormField>
        </SpaceBetween>
      </Modal>

      {/* Bulk Cancel Modal */}
      <Modal
        visible={showCancelModal}
        onDismiss={() => setShowCancelModal(false)}
        header="Cancel Selected Orders"
        closeAriaLabel="Close modal"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setShowCancelModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleBulkCancel}>
                Cancel {selectedItems.length} Order{selectedItems.length > 1 ? 's' : ''}
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween size="m">
          <Box variant="span">
            Are you sure you want to cancel {selectedItems.length} selected order{selectedItems.length > 1 ? 's' : ''}?
          </Box>
          <Alert type="warning">
            This action cannot be undone. The orders will be removed from the processing queue.
          </Alert>
          <Box variant="small">
            Selected orders:
            <ul style={{ marginLeft: '20px', paddingLeft: '0' }}>
              {selectedItems.slice(0, 5).map(order => (
                <li key={order.id}>{order.product?.name || 'Unknown Product'}</li>
              ))}
              {selectedItems.length > 5 && (
                <li>... and {selectedItems.length - 5} more</li>
              )}
            </ul>
          </Box>
        </SpaceBetween>
      </Modal>
    </SpaceBetween>
  );
};

export default OrderDashboard;