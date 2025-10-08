import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Header,
  SpaceBetween,
  Button,
  Alert,
  FormField,
  FileUpload,
  Select,
  Box,
  ColumnLayout,
  StatusIndicator,
  ProgressBar,
  Table,
  Pagination,
  TextFilter,
  CollectionPreferences,
  Modal,
  Input,
  Textarea,
  Wizard,
  Link
} from '@cloudscape-design/components';
import ModelSelector from '../components/ModelSelector';

const BatchUpload = ({ addNotification }) => {
  const navigate = useNavigate();
  
  // Main state
  const [currentStep, setCurrentStep] = useState(1);
  const [uploadFile, setUploadFile] = useState([]);
  const [automationMethod, setAutomationMethod] = useState({ value: 'nova_act', label: 'Nova Act + AgentCore Browser' });
  const [aiModel, setAiModel] = useState('nova_act');
  const [userSelectedModel, setUserSelectedModel] = useState(false); // Track if user manually selected a model
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  // CSV data state
  const [csvData, setCsvData] = useState([]);
  const [validationResults, setValidationResults] = useState(null);
  const [filteredData, setFilteredData] = useState([]);
  const [selectedItems, setSelectedItems] = useState([]);
  
  // Table state
  const [currentPageIndex, setCurrentPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [filterText, setFilterText] = useState('');
  const [sortingColumn, setSortingColumn] = useState({ sortingField: 'name' });
  
  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [editFormData, setEditFormData] = useState({});

  const automationMethods = [
    { value: 'nova_act', label: 'Nova Act + AgentCore Browser' },
    { value: 'strands', label: 'Strands + AgentCore Browser + Browser Tools' }
  ];

  const columnDefinitions = [
    {
      id: 'name',
      header: 'Product Name',
      cell: item => item.name || '-',
      sortingField: 'name',
      width: 200
    },
    {
      id: 'brand',
      header: 'Brand',
      cell: item => item.brand || '-',
      sortingField: 'brand',
      width: 120
    },
    {
      id: 'price',
      header: 'Price',
      cell: item => {
        const price = parseFloat(item.price);
        return !isNaN(price) ? `$${price.toFixed(2)}` : '-';
      },
      sortingField: 'price',
      width: 100
    },
    {
      id: 'color',
      header: 'Color',
      cell: item => item.color || '-',
      sortingField: 'color',
      width: 100
    },
    {
      id: 'size',
      header: 'Size',
      cell: item => item.size || '-',
      sortingField: 'size',
      width: 100
    },
    {
      id: 'retailer',
      header: 'Retailer',
      cell: item => {
        const retailer = item.detected_retailer || 'unknown';
        const displayName = retailer.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        return displayName;
      },
      sortingField: 'detected_retailer',
      width: 120
    },
    {
      id: 'url',
      header: 'URL',
      cell: item => {
        if (!item.curateditem_url) return '-';
        
        const truncatedUrl = item.curateditem_url.length > 50 
          ? `${item.curateditem_url.substring(0, 50)}...` 
          : item.curateditem_url;
          
        return (
          <Link
            href={item.curateditem_url}
            external
            fontSize="body-s"
          >
            {truncatedUrl}
          </Link>
        );
      },
      width: 200
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => (
        <StatusIndicator type={getValidationStatus(item).type}>
          {getValidationStatus(item).text}
        </StatusIndicator>
      ),
      width: 100
    }
  ];



  const getValidationStatus = (item) => {
    if (!item.name || !item.curateditem_url) {
      return { type: 'error', text: 'Invalid' };
    }
    if (!item.detected_retailer || item.detected_retailer === 'unknown') {
      return { type: 'warning', text: 'Warning' };
    }
    return { type: 'success', text: 'Valid' };
  };

  const detectRetailer = (url) => {
    if (!url) return 'unknown';
    
    const urlLower = url.toLowerCase();
    
    // Extract domain from URL for retailer identification
    try {
      const urlObj = new URL(url);
      const domain = urlObj.hostname.replace('www.', '');
      // Use domain as retailer identifier (e.g., "example.com" -> "example")
      const retailer = domain.split('.')[0];
      if (retailer) return retailer;
    } catch (e) {
      // If URL parsing fails, continue to fallback logic
    }
    
    // Handle affiliate links with murl parameter
    if (urlLower.includes('murl=')) {
      try {
        // Find murl parameter and decode it
        const murlMatch = url.match(/murl=([^&]+)/i);
        if (murlMatch) {
          const decodedUrl = decodeURIComponent(murlMatch[1]).toLowerCase();
          console.log('Decoded URL:', decodedUrl); // Debug log
          
          if (decodedUrl.includes('neimanmarcus.com')) return 'neiman_marcus';
          if (decodedUrl.includes('net-a-porter.com')) return 'net_a_porter';
          if (decodedUrl.includes('mytheresa.com')) return 'mytheresa';
          if (decodedUrl.includes('amazon.com')) return 'amazon';
        }
      } catch (e) {
        console.warn('Error parsing murl:', e);
      }
    }
    
    // Handle other affiliate patterns
    if ((urlLower.includes('jdoqocy.com') || urlLower.includes('dpbolvw.net'))) {
      if (urlLower.includes('mytheresa.com')) return 'mytheresa';
      if (urlLower.includes('neimanmarcus.com')) return 'neiman_marcus';
    }
    
    // Handle linksynergy links
    if (urlLower.includes('linksynergy.com')) {
      if (urlLower.includes('neimanmarcus.com')) return 'neiman_marcus';
      if (urlLower.includes('net-a-porter.com')) return 'net_a_porter';
      if (urlLower.includes('mytheresa.com')) return 'mytheresa';
    }
    
    return 'unknown';
  };

  const handleFileChange = async ({ detail }) => {
    setUploadFile(detail.value);
    
    if (detail.value && detail.value.length > 0) {
      try {
        const file = detail.value[0];
        const text = await file.text();
        const lines = text.split('\n').filter(line => line.trim());
        
        if (lines.length < 2) {
          throw new Error('CSV file must have at least a header and one data row');
        }
        
        // Proper CSV parsing function
        const parseCSVLine = (line) => {
          const result = [];
          let current = '';
          let inQuotes = false;
          
          for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (char === '"') {
              if (inQuotes && line[i + 1] === '"') {
                // Escaped quote
                current += '"';
                i++; // Skip next quote
              } else {
                // Toggle quote state
                inQuotes = !inQuotes;
              }
            } else if (char === ',' && !inQuotes) {
              // End of field
              result.push(current.trim());
              current = '';
            } else {
              current += char;
            }
          }
          
          // Add the last field
          result.push(current.trim());
          return result;
        };
        
        const headers = parseCSVLine(lines[0]);
        const data = [];
        
        for (let i = 1; i < lines.length; i++) {
          const values = parseCSVLine(lines[i]);
          const row = {};
          
          headers.forEach((header, index) => {
            row[header] = values[index] || '';
          });
          
          // Add detected retailer
          row.detected_retailer = detectRetailer(row.curateditem_url);
          row.id = i; // Add unique ID for table
          
          data.push(row);
        }
        
        setCsvData(data);
        setFilteredData(data);
        
        // Validation results
        const validRows = data.filter(row => row.name && row.curateditem_url);
        const invalidRows = data.length - validRows.length;
        const unknownRetailers = data.filter(row => row.detected_retailer === 'unknown').length;
        
        setValidationResults({
          totalRows: data.length,
          validRows: validRows.length,
          invalidRows: invalidRows,
          unknownRetailers: unknownRetailers,
          hasHeader: headers.includes('name') && headers.includes('curateditem_url'),
          fileSize: (file.size / 1024 / 1024).toFixed(2) + ' MB',
          headers: headers
        });
        
        setCurrentStep(2);
        
      } catch (error) {
        addNotification({
          type: 'error',
          header: 'CSV Parse Error',
          content: `Failed to parse CSV file: ${error.message}`
        });
      }
    } else {
      setCsvData([]);
      setFilteredData([]);
      setValidationResults(null);
    }
  };

  // Filter and sort data
  useEffect(() => {
    let filtered = csvData;
    
    if (filterText) {
      filtered = csvData.filter(item =>
        Object.values(item).some(value =>
          String(value).toLowerCase().includes(filterText.toLowerCase())
        )
      );
    }
    
    if (sortingColumn.sortingField) {
      filtered.sort((a, b) => {
        const aVal = a[sortingColumn.sortingField] || '';
        const bVal = b[sortingColumn.sortingField] || '';
        
        if (sortingColumn.sortingDescending) {
          return String(bVal).localeCompare(String(aVal));
        }
        return String(aVal).localeCompare(String(bVal));
      });
    }
    
    setFilteredData(filtered);
  }, [csvData, filterText, sortingColumn]);

  const handleEditItem = (item) => {
    setEditingItem(item);
    setEditFormData({ ...item });
    setShowEditModal(true);
  };

  const handleSaveEdit = () => {
    const updatedData = csvData.map(item =>
      item.id === editingItem.id ? { ...editFormData, detected_retailer: detectRetailer(editFormData.curateditem_url) } : item
    );
    setCsvData(updatedData);
    setShowEditModal(false);
    setEditingItem(null);
    setEditFormData({});
  };

  const handleDeleteItems = () => {
    const updatedData = csvData.filter(item => !selectedItems.find(selected => selected.id === item.id));
    setCsvData(updatedData);
    setSelectedItems([]);
  };

  const handleUpload = async () => {
    if (csvData.length === 0) return;

    setUploading(true);
    setUploadProgress(0);

    try {
      // Create CSV content from current data
      const headers = validationResults.headers;
      const csvContent = [
        headers.join(','),
        ...csvData.map(row => headers.map(header => `"${row[header] || ''}"`).join(','))
      ].join('\n');

      const blob = new Blob([csvContent], { type: 'text/csv' });
      const formData = new FormData();
      formData.append('file', blob, 'batch_upload.csv');
      formData.append('automation_method', automationMethod.value);
      formData.append('ai_model', aiModel);

      // Simulate progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 200);

      const response = await fetch('/api/orders/upload-csv', {
        method: 'POST',
        body: formData
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      if (!response.ok) {
        throw new Error('Failed to upload CSV file');
      }

      const result = await response.json();

      addNotification({
        type: 'success',
        header: 'Batch Upload Completed',
        content: `${result.created_count || 0} orders created successfully${result.error_count > 0 ? ` (${result.error_count} errors)` : ''}`
      });

      // Show errors if any
      if (result.errors && result.errors.length > 0) {
        addNotification({
          type: 'warning',
          header: 'Some Orders Failed',
          content: `${result.error_count} orders failed to create. Check the logs for details.`
        });
      }

      // Navigate back to dashboard
      navigate('/dashboard');

    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Batch Upload Failed',
        content: `Failed to upload CSV: ${error.message}`
      });
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const downloadSampleCSV = () => {
    const link = document.createElement('a');
    link.href = '/sample-orders.csv';
    link.download = 'sample-orders.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const renderStep1 = () => (
    <Container header={<Header variant="h2">Upload CSV File</Header>}>
      <SpaceBetween size="l">
        <Alert type="info">
          <Box>
            <strong>Required fields:</strong> name, curateditem_url
          </Box>
          <Box margin={{ top: 'xs' }}>
            <strong>Optional fields:</strong> brand, description, color, size, price
          </Box>
          <Box margin={{ top: 'xs' }} variant="small" color="text-body-secondary">
            <strong>CSV Format:</strong> name,brand,description,color,size,price,curateditem_url
          </Box>
        </Alert>

        <FormField
          label="Select CSV file"
          description="Upload a CSV file with order data"
        >
          <FileUpload
            onChange={handleFileChange}
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
    </Container>
  );

  const renderStep2 = () => (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">Review and Edit Data</Header>}>
        <SpaceBetween size="m">
          {validationResults && (
            <ColumnLayout columns={4}>
              <div>
                <Box variant="awsui-key-label">Total Rows</Box>
                <Box>{validationResults.totalRows}</Box>
              </div>
              <div>
                <Box variant="awsui-key-label">Valid Rows</Box>
                <StatusIndicator type="success">{validationResults.validRows}</StatusIndicator>
              </div>
              <div>
                <Box variant="awsui-key-label">Invalid Rows</Box>
                <StatusIndicator type={validationResults.invalidRows > 0 ? "error" : "success"}>
                  {validationResults.invalidRows}
                </StatusIndicator>
              </div>
              <div>
                <Box variant="awsui-key-label">Unknown Retailers</Box>
                <StatusIndicator type={validationResults.unknownRetailers > 0 ? "warning" : "success"}>
                  {validationResults.unknownRetailers}
                </StatusIndicator>
              </div>
            </ColumnLayout>
          )}

          <Table
            columnDefinitions={columnDefinitions}
            items={filteredData.slice((currentPageIndex - 1) * pageSize, currentPageIndex * pageSize)}
            selectionType="multi"
            selectedItems={selectedItems}
            onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
            sortingColumn={sortingColumn}
            onSortingChange={({ detail }) => setSortingColumn(detail)}
            header={
              <Header
                counter={`(${filteredData.length})`}
                actions={
                  <SpaceBetween direction="horizontal" size="xs">
                    <Button
                      disabled={selectedItems.length === 0}
                      onClick={handleDeleteItems}
                    >
                      Delete selected
                    </Button>
                    <Button
                      disabled={selectedItems.length !== 1}
                      onClick={() => handleEditItem(selectedItems[0])}
                    >
                      Edit
                    </Button>
                  </SpaceBetween>
                }
              >
                CSV Data
              </Header>
            }
            filter={
              <TextFilter
                filteringText={filterText}
                onChange={({ detail }) => setFilterText(detail.filteringText)}
                filteringPlaceholder="Search products..."
              />
            }
            pagination={
              <Pagination
                currentPageIndex={currentPageIndex}
                pagesCount={Math.ceil(filteredData.length / pageSize)}
                onChange={({ detail }) => setCurrentPageIndex(detail.currentPageIndex)}
              />
            }
            preferences={
              <CollectionPreferences
                title="Preferences"
                confirmLabel="Confirm"
                cancelLabel="Cancel"
                preferences={{
                  pageSize: pageSize,
                  visibleContent: ['name', 'brand', 'price', 'color', 'size', 'retailer', 'status']
                }}
                pageSizePreference={{
                  title: "Page size",
                  options: [
                    { value: 10, label: "10 items" },
                    { value: 25, label: "25 items" },
                    { value: 50, label: "50 items" }
                  ]
                }}
                onConfirm={({ detail }) => {
                  setPageSize(detail.pageSize);
                }}
              />
            }
            empty={
              <Box textAlign="center" color="inherit">
                <b>No data</b>
                <Box variant="p" color="inherit">
                  No CSV data to display.
                </Box>
              </Box>
            }
          />
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );

  const renderStep3 = () => (
    <Container header={<Header variant="h2">Configure Automation Settings</Header>}>
      <SpaceBetween size="l">
        <Alert type="info">
          These settings will be applied to all {csvData.length} orders created from the CSV file.
        </Alert>

        <FormField 
          label="Automation method" 
          description="All methods use AgentCore Browser for secure, scalable automation"
        >
          <Select
            selectedOption={automationMethod}
            onChange={({ detail }) => {
              setAutomationMethod(detail.selectedOption);
              // Auto-set AI model based on automation method only if user hasn't manually selected one
              if (detail.selectedOption.value === 'nova_act') {
                setAiModel('nova_act');
                setUserSelectedModel(false); // Reset user selection tracking
              } else if (detail.selectedOption.value === 'strands' && !userSelectedModel) {
                // Only set default if user hasn't manually selected a model
                setAiModel('us.anthropic.claude-sonnet-4-20250514-v1:0');
              }
            }}
            options={automationMethods}
          />
        </FormField>

        {automationMethod.value === 'nova_act' && (
          <ModelSelector
            selectedModel={aiModel}
            onChange={setAiModel}
            label="AI Model"
            description="Model used for generating Nova Act instructions. Nova Act uses its internal model with AgentCore Browser for execution."
            disabled={true}
          />
        )}

        {automationMethod.value === 'strands' && (
          <ModelSelector
            selectedModel={aiModel}
            onChange={(model) => {
              setAiModel(model);
              setUserSelectedModel(true); // Mark that user manually selected a model
            }}
            label="AI Model"
            description="Bedrock model used with Strands and AgentCore Browser for web automation"
          />
        )}

        {uploading && (
          <Container>
            <SpaceBetween size="s">
              <Header variant="h4">Upload Progress</Header>
              <ProgressBar
                value={uploadProgress}
                label="Uploading and processing CSV file..."
                description={`${uploadProgress}% complete`}
              />
            </SpaceBetween>
          </Container>
        )}

        <Alert type="warning">
          <strong>Important:</strong> This will create {csvData.length} orders in your system. 
          Make sure your automation settings are correct before proceeding.
        </Alert>
      </SpaceBetween>
    </Container>
  );



  const canProceed = () => {
    switch (currentStep) {
      case 1: 
        return uploadFile.length > 0 && validationResults?.hasHeader;
      case 2: 
        return csvData.length > 0 && validationResults?.validRows > 0;
      case 3: 
        return automationMethod && aiModel && !uploading;
      default: 
        return false;
    }
  };

  const getWizardSteps = () => [
    {
      title: "Upload CSV File",
      info: <Link variant="info" onFollow={downloadSampleCSV}>Download Sample</Link>,
      description: "Upload a CSV file containing product information for batch order creation.",
      content: renderStep1(),
      isOptional: false
    },
    {
      title: "Review and Edit Data",
      description: "Review the uploaded data, edit individual items, and validate product information.",
      content: renderStep2(),
      isOptional: false
    },
    {
      title: "Configure and Create Orders",
      description: "Set automation method and AI model, then create all orders in this batch.",
      content: renderStep3(),
      isOptional: false
    }
  ];

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Upload a CSV file to create multiple orders at once with advanced editing and validation capabilities."
        actions={
          <Button
            iconName="arrow-left"
            onClick={() => navigate('/dashboard')}
          >
            Back to Dashboard
          </Button>
        }
      >
        Batch Upload Orders
      </Header>

      <Wizard
        i18nStrings={{
          stepNumberLabel: stepNumber => `Step ${stepNumber}`,
          collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
          skipToButtonLabel: (step, stepNumber) => `Skip to ${step.title}`,
          navigationAriaLabel: "Batch upload steps",
          cancelButton: "Cancel",
          previousButton: "Previous", 
          nextButton: "Next",
          submitButtonText: "Create Orders",
          optional: "optional",
          loadingText: "Creating orders..."
        }}
        onNavigate={({ detail }) => {
          const requestedStep = detail.requestedStepIndex + 1;
          if (requestedStep < currentStep || (requestedStep === currentStep + 1 && canProceed())) {
            setCurrentStep(requestedStep);
          }
        }}
        onCancel={() => navigate('/dashboard')}
        onSubmit={handleUpload}
        activeStepIndex={currentStep - 1}
        allowSkipTo={false}
        steps={getWizardSteps()}
        isLoadingNextStep={uploading}
        submitButtonText="Create Orders"
      />

      {/* Edit Modal */}
      <Modal
        visible={showEditModal}
        onDismiss={() => setShowEditModal(false)}
        header="Edit Product"
        closeAriaLabel="Close modal"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setShowEditModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSaveEdit}>
                Save
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        {editingItem && (
          <SpaceBetween size="m">
            <FormField label="Product Name">
              <Input
                value={editFormData.name || ''}
                onChange={({ detail }) => setEditFormData(prev => ({ ...prev, name: detail.value }))}
              />
            </FormField>
            <FormField label="Brand">
              <Input
                value={editFormData.brand || ''}
                onChange={({ detail }) => setEditFormData(prev => ({ ...prev, brand: detail.value }))}
              />
            </FormField>
            <ColumnLayout columns={3}>
              <FormField label="Price">
                <Input
                  value={editFormData.price || ''}
                  onChange={({ detail }) => setEditFormData(prev => ({ ...prev, price: detail.value }))}
                  type="number"
                />
              </FormField>
              <FormField label="Color">
                <Input
                  value={editFormData.color || ''}
                  onChange={({ detail }) => setEditFormData(prev => ({ ...prev, color: detail.value }))}
                />
              </FormField>
              <FormField label="Size">
                <Input
                  value={editFormData.size || ''}
                  onChange={({ detail }) => setEditFormData(prev => ({ ...prev, size: detail.value }))}
                />
              </FormField>
            </ColumnLayout>
            <FormField label="Product URL">
              <Input
                value={editFormData.curateditem_url || ''}
                onChange={({ detail }) => setEditFormData(prev => ({ ...prev, curateditem_url: detail.value }))}
              />
            </FormField>
            <FormField label="Description">
              <Textarea
                value={editFormData.description || ''}
                onChange={({ detail }) => setEditFormData(prev => ({ ...prev, description: detail.value }))}
                rows={3}
              />
            </FormField>
          </SpaceBetween>
        )}
      </Modal>
    </SpaceBetween>
  );
};

export default BatchUpload;