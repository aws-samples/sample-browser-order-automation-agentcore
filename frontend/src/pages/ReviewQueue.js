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
  Link,
  Alert
} from '@cloudscape-design/components';

const ReviewQueue = ({ addNotification }) => {
  const [reviewItems, setReviewItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedItems, setSelectedItems] = useState([]);
  const [preferences, setPreferences] = useState({
    pageSize: 20,
    visibleContent: ['retailer', 'product_name', 'customer_name', 'automation_method', 'product_price', 'error_message', 'created_at']
  });
  const [filtering, setFiltering] = useState({
    tokens: [],
    operation: 'and'
  });
  const [currentPageIndex, setCurrentPageIndex] = useState(1);
  const [errorCount, setErrorCount] = useState(0);
  const [hasError, setHasError] = useState(false);
  const [completingReviews, setCompletingReviews] = useState(false);

  const fetchReviewQueue = useCallback(async () => {
    if (errorCount >= 5) {
      setHasError(true);
      return;
    }

    try {
      const response = await fetch('/api/review/queue');
      if (!response.ok) {
        throw new Error('Failed to fetch review queue');
      }
      const data = await response.json();
      const newReviewItems = data.orders || [];
      setReviewItems(newReviewItems);

      // Update selected items if they still exist
      if (selectedItems.length > 0) {
        const selectedIds = selectedItems.map(item => item.id);
        const updatedSelection = newReviewItems.filter(item => selectedIds.includes(item.id));
        setSelectedItems(updatedSelection);
      }

      setLoading(false);
      setErrorCount(0);
      setHasError(false);
    } catch (error) {
      console.error('Failed to fetch review queue:', error);
      const newErrorCount = errorCount + 1;
      setErrorCount(newErrorCount);

      if (errorCount === 0) {
        addNotification({
          type: 'error',
          header: 'Failed to load review queue',
          content: error.message
        });
      }

      if (newErrorCount >= 5) {
        setHasError(true);
      }

      setLoading(false);
    }
  }, [errorCount, selectedItems, addNotification]);

  useEffect(() => {
    fetchReviewQueue();

    const interval = setInterval(() => {
      if (errorCount < 5) {
        fetchReviewQueue();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchReviewQueue, errorCount]);

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

  const getFilteredItems = () => {
    let filtered = [...reviewItems];
    filtering.tokens.forEach(token => {
      const { propertyKey, value, operator } = token;
      filtered = filtered.filter(item => {
        const itemValue = item[propertyKey];
        switch (operator) {
          case ':': return String(itemValue).toLowerCase().includes(value.toLowerCase());
          case '!:': return !String(itemValue).toLowerCase().includes(value.toLowerCase());
          case '=': return String(itemValue) === value;
          case '!=': return String(itemValue) !== value;
          default: return true;
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

  const handleBulkComplete = async () => {
    if (selectedItems.length === 0) {
      addNotification({
        type: 'warning',
        header: 'No items selected',
        content: 'Please select items to complete review for'
      });
      return;
    }

    setCompletingReviews(true);
    try {
      const promises = selectedItems.map(item =>
        fetch(`/api/review/${item.id}/resolve`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            status: 'completed',
            human_review_notes: 'Bulk completed via review queue'
          })
        })
      );

      await Promise.all(promises);

      addNotification({
        type: 'success',
        header: 'Reviews completed',
        content: `Successfully completed ${selectedItems.length} reviews`
      });

      setSelectedItems([]);
      fetchReviewQueue();
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Failed to complete reviews',
        content: error.message
      });
    } finally {
      setCompletingReviews(false);
    }
  };

  const columnDefinitions = [
    {
      id: 'retailer',
      header: 'Retailer',
      cell: item => item.retailer,
      sortingField: 'retailer'
    },
    {
      id: 'product_name',
      header: 'Product',
      cell: item => (
        <Link href={`/orders/${item.id}`}>
          {item.product_name}
        </Link>
      ),
      sortingField: 'product_name'
    },
    {
      id: 'customer_name',
      header: 'Customer',
      cell: item => item.customer_name,
      sortingField: 'customer_name'
    },
    {
      id: 'automation_method',
      header: 'Method',
      cell: item => item.automation_method,
      sortingField: 'automation_method'
    },
    {
      id: 'product_price',
      header: 'Price',
      cell: item => item.product_price ? `$${item.product_price.toFixed(2)}` : 'N/A',
      sortingField: 'product_price'
    },
    {
      id: 'error_message',
      header: 'Review Reason',
      cell: item => (
        <Box variant="small" color="text-status-warning">
          {item.error_message || item.human_review_notes || 'Requires human review'}
        </Box>
      )
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => (
        <StatusIndicator type="warning">
          Requires Review
        </StatusIndicator>
      )
    },
    {
      id: 'created_at',
      header: 'Created',
      cell: item => formatTime(item.created_at),
      sortingField: 'created_at'
    }
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

  if (hasError) {
    return (
      <SpaceBetween size="l">
        <Header variant="h1">Review Queue</Header>
        <Alert
          type="error"
          header="Service Unavailable"
          action={
            <Button
              onClick={() => {
                setErrorCount(0);
                setHasError(false);
                fetchReviewQueue();
              }}
            >
              Retry
            </Button>
          }
        >
          The review queue service is temporarily unavailable. This may be due to database connectivity issues.
        </Alert>
      </SpaceBetween>
    );
  }

  return (
    <SpaceBetween direction="vertical" size="l">
    <Header
      variant="h1"
      description="Orders requiring human review due to automation issues"
    >
      Review Queue
    </Header>



    <Table
      header={
        <Header
          variant="h2"
          counter={`(${filteredItems.length})`}
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              <Button iconName="refresh" onClick={fetchReviewQueue} loading={loading}>
                Refresh
              </Button>
              {selectedItems.length > 0 && (
                <Button
                  variant="primary"
                  onClick={handleBulkComplete}
                  loading={completingReviews}
                >
                  Complete {selectedItems.length} Reviews
                </Button>
              )}
            </SpaceBetween>
          }
        >
          Review Items
        </Header>
      }
      columnDefinitions={columnDefinitions}
      items={paginatedItems}
      loading={loading}
      loadingText="Loading review items..."
      selectedItems={selectedItems}
      onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
      selectionType="multi"
      filter={
        <PropertyFilter
          query={filtering}
          onChange={({ detail }) => {
            setFiltering(detail);
            setCurrentPageIndex(1);
          }}
          countText={`${filteredItems.length} matches`}
          expandToViewport
          filteringProperties={propertyFilteringProperties}
          filteringPlaceholder="Find review items"
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
              { value: 50, label: "50 items" }
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
            <b>No items in review queue</b>
            <Box variant="p" color="inherit">
              All orders are processing successfully and don't require human review.
            </Box>
          </SpaceBetween>
        </Box>
      }
      trackBy="id"
    />
    </SpaceBetween>
  );
};

export default ReviewQueue;