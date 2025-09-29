import React, { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Header,
  SpaceBetween,
  Button,
  StatusIndicator,
  Box,
  Pagination,
  CollectionPreferences,
  PropertyFilter,
  Link
} from '@cloudscape-design/components';

const FailedOrders = ({ addNotification }) => {
  const [failedOrders, setFailedOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedItems, setSelectedItems] = useState([]);
  const [preferences, setPreferences] = useState({
    pageSize: 20,
    visibleContent: ['retailer', 'product_name', 'customer_name', 'error_message', 'created_at', 'automation_method']
  });
  const [filtering, setFiltering] = useState({
    tokens: [],
    operation: 'and'
  });
  const [currentPageIndex, setCurrentPageIndex] = useState(1);

  const fetchFailedOrders = useCallback(async () => {
    try {
      const response = await fetch('/api/orders?status=failed&limit=100');
      if (!response.ok) {
        throw new Error('Failed to fetch failed orders');
      }
      const data = await response.json();
      setFailedOrders(data.orders || []);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch failed orders:', error);
      addNotification({
        type: 'error',
        header: 'Failed to load failed orders',
        content: error.message
      });
      setLoading(false);
    }
  }, [addNotification]);

  useEffect(() => {
    fetchFailedOrders();
    
    // Refresh every 60 seconds
    const interval = setInterval(fetchFailedOrders, 60000);
    return () => clearInterval(interval);
  }, [fetchFailedOrders]);

  const formatTime = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short'
    });
  };

  const getFilteredItems = () => {
    let filtered = [...failedOrders];

    filtering.tokens.forEach(token => {
      const { propertyKey, value, operator } = token;

      filtered = filtered.filter(item => {
        const itemValue = item[propertyKey];

        switch (operator) {
          case '=':
            return itemValue === value;
          case '!=':
            return itemValue !== value;
          case ':':
            return String(itemValue).toLowerCase().includes(value.toLowerCase());
          case '!:':
            return !String(itemValue).toLowerCase().includes(value.toLowerCase());
          default:
            return true;
        }
      });
    });

    return filtered;
  };

  const getPaginatedItems = () => {
    const filtered = getFilteredItems();
    const startIndex = (currentPageIndex - 1) * preferences.pageSize;
    const endIndex = startIndex + preferences.pageSize;
    return filtered.slice(startIndex, endIndex);
  };



  const columnDefinitions = [
    {
      id: 'retailer',
      header: 'Retailer',
      cell: item => item.retailer || 'Unknown',
      sortingField: 'retailer'
    },
    {
      id: 'product_name',
      header: 'Product',
      cell: item => (
        <Link href={`/orders/${item.id}`}>
          {item.product_name || 'Unknown Product'}
        </Link>
      ),
      sortingField: 'product_name'
    },
    {
      id: 'customer_name',
      header: 'Customer',
      cell: item => item.customer_name || 'Unknown',
      sortingField: 'customer_name'
    },
    {
      id: 'automation_method',
      header: 'Method',
      cell: item => item.automation_method || 'Unknown',
      sortingField: 'automation_method'
    },
    {
      id: 'error_message',
      header: 'Error',
      cell: item => (
        <Box variant="small" color="text-status-error">
          {item.error_message || 'Unknown error'}
        </Box>
      )
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => (
        <StatusIndicator type="error">
          Failed
        </StatusIndicator>
      )
    },
    {
      id: 'created_at',
      header: 'Created',
      cell: item => formatTime(item.created_at),
      sortingField: 'created_at'
    },

  ];

  const propertyFilteringProperties = [
    {
      key: 'retailer',
      operators: [':', '!:', '=', '!='],
      propertyLabel: 'Retailer',
      groupValuesLabel: 'Retailer values'
    },
    {
      key: 'product_name',
      operators: [':', '!:', '=', '!='],
      propertyLabel: 'Product',
      groupValuesLabel: 'Product values'
    },
    {
      key: 'customer_name',
      operators: [':', '!:', '=', '!='],
      propertyLabel: 'Customer',
      groupValuesLabel: 'Customer values'
    },
    {
      key: 'automation_method',
      operators: [':', '!:', '=', '!='],
      propertyLabel: 'Method',
      groupValuesLabel: 'Method values'
    }
  ];

  const filteredItems = getFilteredItems();
  const paginatedItems = getPaginatedItems();

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Orders that failed during automation processing"
      >
        Failed Orders
      </Header>



      <Table
        header={
          <Header
            variant="h2"
            counter={`(${filteredItems.length})`}
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                <Button iconName="refresh" onClick={fetchFailedOrders} loading={loading}>
                  Refresh
                </Button>
              </SpaceBetween>
            }
          >
            Failed Orders
          </Header>
        }
        columnDefinitions={columnDefinitions}
        items={paginatedItems}
        loading={loading}
        loadingText="Loading failed orders..."
        selectedItems={selectedItems}
        onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
        selectionType="multi"
        ariaLabels={{
          selectionGroupLabel: "Items selection",
          allItemsSelectionLabel: ({ selectedItems }) =>
            `${selectedItems.length} ${selectedItems.length === 1 ? "item" : "items"} selected`,
          itemSelectionLabel: ({ selectedItems }, item) => {
            const isItemSelected = selectedItems.filter(i => i.id === item.id).length;
            return `${item.product_name} is ${isItemSelected ? "" : "not "}selected`;
          }
        }}
        filter={
          <PropertyFilter
            query={filtering}
            onChange={({ detail }) => {
              setFiltering(detail);
              setCurrentPageIndex(1);
            }}
            countText={`${filteredItems.length} matches`}
            expandToViewport={true}
            filteringProperties={propertyFilteringProperties}
            filteringPlaceholder="Find failed orders"
          />
        }
        pagination={
          <Pagination
            currentPageIndex={currentPageIndex}
            onChange={({ detail }) => setCurrentPageIndex(detail.currentPageIndex)}
            pagesCount={Math.ceil(filteredItems.length / preferences.pageSize)}
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
                { value: 10, label: "10 items" },
                { value: 20, label: "20 items" },
                { value: 50, label: "50 items" },
                { value: 100, label: "100 items" }
              ]
            }}
            visibleContentPreference={{
              title: "Select visible columns",
              options: [
                {
                  label: "Order properties",
                  options: columnDefinitions.map(({ id, header }) => ({
                    id,
                    label: header
                  }))
                }
              ]
            }}
          />
        }
        empty={
          <Box margin={{ vertical: 'xs' }} textAlign="center" color="inherit">
            <SpaceBetween size="m">
              <b>No failed orders</b>
              <Box variant="p" color="inherit">
                All orders are processing successfully.
              </Box>
            </SpaceBetween>
          </Box>
        }
      />
    </SpaceBetween>
  );
};

export default FailedOrders;