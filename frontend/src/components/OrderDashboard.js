/**
 * Order Dashboard - Production Order Automation System
 * Following Cloudscape Design System patterns and best practices
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Header,
  SpaceBetween,
  Button,
  ButtonDropdown,
  Table,
  Box,
  StatusIndicator,
  Alert,
  Modal,
  Pagination,
  CollectionPreferences,
  PropertyFilter,
  Link,
  Popover
} from '@cloudscape-design/components';

import CreateOrderWizard from './CreateOrderWizard';
import { apiService } from '../services/api';
// import useResizeObserverFix from '../hooks/useResizeObserverFix';

// ResizeObserver errors are handled globally by errorSuppression utility

const OrderDashboard = ({ addNotification }) => {
  const [orders, setOrders] = useState([]);
  const [retailers, setRetailers] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedItems, setSelectedItems] = useState([]);
  const [preferences, setPreferences] = useState({
    pageSize: 20,
    visibleContent: ['id', 'retailer', 'product', 'status', 'method', 'created', 'actions']
  });
  const [filtering, setFiltering] = useState({
    tokens: [],
    operation: 'and'
  });
  const [currentPageIndex, setCurrentPageIndex] = useState(1);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [showCreateOrderWizard, setShowCreateOrderWizard] = useState(false);

  const [errorCount, setErrorCount] = useState(0);
  const [hasError, setHasError] = useState(false);
  
  const fetchDashboardData = useCallback(async () => {
    // Skip if we've had too many errors
    if (errorCount >= 5) {
      setHasError(true);
      return;
    }

    try {
      const [ordersData, retailersData] = await Promise.all([
        apiService.getOrders(500),
        apiService.getRetailerConfig()
      ]);

      setOrders(Array.isArray(ordersData.orders) ? ordersData.orders : []);
      setRetailers(retailersData);
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





  const handleDeleteCompleted = async () => {
    try {
      const result = await apiService.request('/api/orders/cleanup/completed', { method: 'DELETE' });

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

  const handleForceDeleteOrder = async (orderId) => {
    const order = orders.find(o => o.id === orderId);
    const productName = order?.product?.name || 'Unknown Product';
    const shortId = orderId.substring(0, 8);
    
    if (!window.confirm(`Are you sure you want to delete this order?\n\nOrder: ${shortId}\nProduct: ${productName}\n\nThis action cannot be undone.`)) {
      return;
    }

    try {
      await apiService.request(`/api/orders/${orderId}/force`, { method: 'DELETE' });

      addNotification({
        type: 'success',
        header: 'Order Deleted',
        content: `Order ${shortId} (${productName}) has been deleted successfully`
      });

      fetchDashboardData();

    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Delete Failed',
        content: `Failed to delete order: ${error.message}`
      });
    }
  };

  const handleUploadCSV = () => {
    window.location.href = '/orders/batch-upload';
  };



  const handleRetryOrder = async (orderId) => {
    try {
      await apiService.request(`/api/orders/${orderId}/retry`, { method: 'POST' });
      addNotification({
        type: 'success',
        header: 'Order Retry',
        content: `Order ${orderId.substring(0, 8)} has been queued for retry`
      });
      fetchDashboardData();
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
          apiService.cancelOrder(order.id)
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

  const handleBulkDelete = async () => {
    if (selectedItems.length === 0) return;

    const orderList = selectedItems.map(order => 
      `• ${order.id.substring(0, 8)} - ${order.product?.name || 'Unknown Product'}`
    ).join('\n');

    if (!window.confirm(`Are you sure you want to delete ${selectedItems.length} selected order(s)?\n\n${orderList}\n\nThis action cannot be undone.`)) {
      return;
    }

    try {
      const deletePromises = selectedItems.map(order =>
        apiService.request(`/api/orders/${order.id}/force`, { method: 'DELETE' })
      );

      await Promise.all(deletePromises);

      addNotification({
        type: 'success',
        header: 'Orders Deleted',
        content: `${selectedItems.length} order(s) deleted successfully`
      });
      setSelectedItems([]);
      fetchDashboardData();
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Delete Failed',
        content: `Failed to delete orders: ${error.message}`
      });
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
    {
      id: 'actions',
      header: 'Actions',
      cell: item => {
        const actions = [
          {
            id: 'delete',
            text: 'Delete',
            iconName: 'remove'
          }
        ];

        if (item.status === 'failed') {
          actions.unshift({
            id: 'retry',
            text: 'Retry',
            iconName: 'refresh'
          });
        }

        return (
          <ButtonDropdown
            variant="icon"
            ariaLabel={`Actions for order ${item.id?.substring(0, 8) || 'N/A'}`}
            items={actions}
            onItemClick={(e) => {
              switch (e.detail.id) {
                case 'retry':
                  handleRetryOrder(item.id);
                  break;
                case 'delete':
                  handleForceDeleteOrder(item.id);
                  break;
                default:
                  break;
              }
            }}
            expandToViewport={true}
          />
        );
      },
      minWidth: 60
    }

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
        description="Sample e-commerce order automation demo with Amazon Bedrock AgentCore Browser"
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
      >
        Order Automation Dashboard
      </Header>



      {/* Orders Table */}
      <Table
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
                      id: 'delete',
                      text: selectedItems.length > 0 ? `Delete Selected (${selectedItems.length})` : 'Delete Completed',
                      disabled: false
                    },

                  ]}
                  onItemClick={(e) => {
                    switch (e.detail.id) {
                      case 'create-wizard':
                        window.location.href = '/orders/create';
                        break;
                      case 'upload-csv':
                        handleUploadCSV();
                        break;
                      case 'delete':
                        if (selectedItems.length > 0) {
                          handleBulkDelete();
                        } else {
                          handleDeleteCompleted();
                        }
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