import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Container,
  Header,
  Box,
  Button,
  SpaceBetween,
  StatusIndicator,
  Modal,
  ColumnLayout,
  KeyValuePairs
} from '@cloudscape-design/components';

// ResizeObserver errors are handled globally by errorSuppression utility

const LiveScreenshotViewer = ({ order, isVisible, onClose }) => {
  const [currentScreenshot, setCurrentScreenshot] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const intervalRef = useRef(null);

  const screenshots = useMemo(() => order?.screenshots || [], [order?.screenshots]);

  const screenshotsLength = screenshots.length;
  
  useEffect(() => {
    if (screenshotsLength > 0) {
      setCurrentScreenshot(screenshots[screenshotsLength - 1]);
      setSelectedIndex(screenshotsLength - 1);
    }
  }, [screenshots, screenshotsLength]);

  useEffect(() => {
    if (isVisible && order?.status === 'processing') {
      // Auto-refresh screenshots during processing
      intervalRef.current = setInterval(() => {
        // This would trigger a refresh of the order data
        // The parent component should handle this
      }, 3000);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isVisible, order?.status]);

  const handleScreenshotSelect = (index) => {
    setSelectedIndex(index);
    setCurrentScreenshot(screenshots[index]);
  };

  const handlePrevious = () => {
    if (selectedIndex > 0) {
      handleScreenshotSelect(selectedIndex - 1);
    }
  };

  const handleNext = () => {
    if (selectedIndex < screenshots.length - 1) {
      handleScreenshotSelect(selectedIndex + 1);
    }
  };

  const formatTime = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    });
  };

  if (!isVisible) return null;

  return (
    <Modal
      visible={isVisible}
      onDismiss={onClose}
      header="Live Screenshot Viewer"
      size="max"
      closeAriaLabel="Close screenshot viewer"
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
              variant="primary" 
              onClick={() => setIsFullscreen(true)}
              disabled={!currentScreenshot}
            >
              Fullscreen
            </Button>
          </SpaceBetween>
        </Box>
      }
    >
      <SpaceBetween size="l">
        {screenshots.length === 0 ? (
          <Box textAlign="center" padding="xxl">
            <SpaceBetween size="m">
              <StatusIndicator type="pending">
                <Box fontSize="heading-s">No screenshots available</Box>
              </StatusIndicator>
              <Box variant="p" color="text-body-secondary">
                Screenshots will appear here as the automation agent processes your order
              </Box>
            </SpaceBetween>
          </Box>
        ) : (
          <>
            {/* Screenshot Navigation */}
            <Container>
              <ColumnLayout columns={3}>
                <KeyValuePairs
                  columns={1}
                  items={[
                    { label: 'Current', value: `${selectedIndex + 1} of ${screenshots.length}` },
                    { label: 'Step', value: currentScreenshot?.step || 'N/A' }
                  ]}
                />
                <KeyValuePairs
                  columns={1}
                  items={[
                    { label: 'Timestamp', value: formatTime(currentScreenshot?.timestamp) },
                    { label: 'Description', value: currentScreenshot?.description || 'N/A' }
                  ]}
                />
                <Box textAlign="right">
                  <SpaceBetween direction="horizontal" size="xs">
                    <Button 
                      iconName="angle-left"
                      onClick={handlePrevious}
                      disabled={selectedIndex === 0}
                    >
                      Previous
                    </Button>
                    <Button 
                      iconName="angle-right"
                      onClick={handleNext}
                      disabled={selectedIndex === screenshots.length - 1}
                    >
                      Next
                    </Button>
                  </SpaceBetween>
                </Box>
              </ColumnLayout>
            </Container>

            {/* Main Screenshot Display */}
            <Container>
              <div style={{ 
                textAlign: 'center',
                backgroundColor: '#f8f9fa',
                padding: '20px',
                borderRadius: '8px',
                border: '2px dashed #dee2e6'
              }}>
                {currentScreenshot ? (
                  <img 
                    src={currentScreenshot.url} 
                    alt={currentScreenshot.description || `Screenshot ${selectedIndex + 1}`}
                    style={{ 
                      maxWidth: '100%', 
                      maxHeight: '600px',
                      height: 'auto',
                      borderRadius: '4px',
                      boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
                      cursor: 'pointer'
                    }}
                    onClick={() => setIsFullscreen(true)}
                  />
                ) : (
                  <Box color="text-body-secondary">
                    No screenshot selected
                  </Box>
                )}
              </div>
            </Container>

            {/* Screenshot Thumbnails */}
            <Container header={<Header variant="h3">All Screenshots</Header>}>
              <div style={{ 
                display: 'flex', 
                gap: '12px', 
                overflowX: 'auto',
                padding: '8px 0'
              }}>
                {screenshots.map((screenshot, index) => (
                  <div
                    key={index}
                    style={{
                      minWidth: '120px',
                      cursor: 'pointer',
                      border: selectedIndex === index ? '3px solid #0972d3' : '2px solid #e9ebed',
                      borderRadius: '8px',
                      padding: '4px',
                      backgroundColor: selectedIndex === index ? '#e6f3ff' : 'white'
                    }}
                    onClick={() => handleScreenshotSelect(index)}
                  >
                    <img 
                      src={screenshot.url} 
                      alt={`Thumbnail ${index + 1}`}
                      style={{ 
                        width: '100%', 
                        height: '80px',
                        objectFit: 'cover',
                        borderRadius: '4px'
                      }}
                    />
                    <Box 
                      variant="small" 
                      textAlign="center" 
                      margin={{ top: 'xs' }}
                      color={selectedIndex === index ? 'text-status-info' : 'text-body-secondary'}
                    >
                      {screenshot.step || `Step ${index + 1}`}
                    </Box>
                  </div>
                ))}
              </div>
            </Container>
          </>
        )}
      </SpaceBetween>

      {/* Fullscreen Modal */}
      <Modal
        visible={isFullscreen}
        onDismiss={() => setIsFullscreen(false)}
        header={`Screenshot ${selectedIndex + 1} - ${currentScreenshot?.step || 'N/A'}`}
        size="max"
        closeAriaLabel="Close fullscreen view"
      >
        <div style={{ textAlign: 'center' }}>
          {currentScreenshot && (
            <img 
              src={currentScreenshot.url} 
              alt={currentScreenshot.description || `Screenshot ${selectedIndex + 1}`}
              style={{ 
                maxWidth: '100%', 
                height: 'auto',
                borderRadius: '4px'
              }}
            />
          )}
        </div>
      </Modal>
    </Modal>
  );
};

export default LiveScreenshotViewer;