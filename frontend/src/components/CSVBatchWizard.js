import React, { useState } from 'react';
import {
  Modal,
  Box,
  SpaceBetween,
  Button,
  Alert,
  FormField,
  FileUpload,
  Select,
  Header,
  Container,
  ColumnLayout,
  StatusIndicator,
  ProgressBar
} from '@cloudscape-design/components';
import ModelSelector from './ModelSelector';

const CSVBatchWizard = ({ visible, onDismiss, onOrdersCreated, addNotification }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [uploadFile, setUploadFile] = useState([]);
  const [automationMethod, setAutomationMethod] = useState({ value: 'strands', label: 'Strands + AgentCore Browser + Browser Tools' });
  const [aiModel, setAiModel] = useState('us.anthropic.claude-sonnet-4-20250514-v1:0');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [csvPreview, setCsvPreview] = useState(null);
  const [validationResults, setValidationResults] = useState(null);

  const automationMethods = [
    { value: 'strands', label: 'Strands + AgentCore Browser + Browser Tools' },
    { value: 'nova_act', label: 'Nova Act + Browser Automation' }
  ];

  const handleFileChange = async ({ detail }) => {
    setUploadFile(detail.value);
    
    if (detail.value && detail.value.length > 0) {
      // Preview CSV file
      try {
        const file = detail.value[0];
        const text = await file.text();
        const lines = text.split('\n').slice(0, 6); // First 5 rows + header
        const preview = lines.map(line => line.split(',').slice(0, 4)); // First 4 columns
        setCsvPreview(preview);
        
        // Basic validation
        const totalLines = text.split('\n').length - 1; // Exclude header
        setValidationResults({
          totalRows: totalLines,
          hasHeader: lines[0].includes('name') && lines[0].includes('curateditem_url'),
          fileSize: (file.size / 1024 / 1024).toFixed(2) + ' MB'
        });
      } catch (error) {
        console.error('Error previewing CSV:', error);
      }
    } else {
      setCsvPreview(null);
      setValidationResults(null);
    }
  };

  const handleNext = () => {
    if (currentStep < 3) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleUpload = async () => {
    if (!uploadFile || uploadFile.length === 0) return;

    setUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('file', uploadFile[0]);
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
        header: 'CSV Batch Upload Completed',
        content: `${result.created_count || 0} orders created successfully${result.error_count > 0 ? ` (${result.error_count} errors)` : ''}`
      });

      if (onOrdersCreated) {
        onOrdersCreated(result.created_orders);
      }

      onDismiss();
      resetWizard();

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

  const resetWizard = () => {
    setCurrentStep(1);
    setUploadFile([]);
    setAutomationMethod({ value: 'strands', label: 'Strands + AgentCore Browser + Browser Tools' });
    setAiModel('us.anthropic.claude-sonnet-4-20250514-v1:0');
    setCsvPreview(null);
    setValidationResults(null);
    setUploadProgress(0);
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
    <SpaceBetween size="l">
      <Header variant="h3">Upload CSV File</Header>
      
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

      {validationResults && (
        <Container>
          <SpaceBetween size="s">
            <Header variant="h4">File Validation</Header>
            <ColumnLayout columns={3}>
              <div>
                <Box variant="awsui-key-label">Total Rows</Box>
                <Box>{validationResults.totalRows}</Box>
              </div>
              <div>
                <Box variant="awsui-key-label">File Size</Box>
                <Box>{validationResults.fileSize}</Box>
              </div>
              <div>
                <Box variant="awsui-key-label">Header Valid</Box>
                <StatusIndicator type={validationResults.hasHeader ? "success" : "error"}>
                  {validationResults.hasHeader ? "Valid" : "Invalid"}
                </StatusIndicator>
              </div>
            </ColumnLayout>
          </SpaceBetween>
        </Container>
      )}

      {csvPreview && (
        <Container>
          <SpaceBetween size="s">
            <Header variant="h4">CSV Preview (First 5 rows)</Header>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <tbody>
                  {csvPreview.map((row, index) => (
                    <tr key={index} style={{ borderBottom: '1px solid #e9ebed' }}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} style={{ 
                          padding: '8px', 
                          fontSize: '12px',
                          maxWidth: '150px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          fontWeight: index === 0 ? 'bold' : 'normal'
                        }}>
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SpaceBetween>
        </Container>
      )}
    </SpaceBetween>
  );

  const renderStep2 = () => (
    <SpaceBetween size="l">
      <Header variant="h3">Configure Automation Settings</Header>
      
      <Alert type="info">
        These settings will be applied to all orders created from the CSV file.
      </Alert>

      <FormField
        label="Automation Method"
        description="Choose the automation method for processing orders"
      >
        <Select
          selectedOption={automationMethod}
          onChange={({ detail }) => setAutomationMethod(detail.selectedOption)}
          options={automationMethods}
        />
      </FormField>

      <FormField
        label="AI Model"
        description="Select the AI model to use for automation"
      >
        <ModelSelector
          value={aiModel}
          onChange={setAiModel}
          automationMethod={automationMethod.value}
        />
      </FormField>

      {validationResults && (
        <Container>
          <SpaceBetween size="s">
            <Header variant="h4">Batch Summary</Header>
            <ColumnLayout columns={2}>
              <div>
                <Box variant="awsui-key-label">Orders to Create</Box>
                <Box>{validationResults.totalRows}</Box>
              </div>
              <div>
                <Box variant="awsui-key-label">Automation Method</Box>
                <Box>{automationMethod.label}</Box>
              </div>
            </ColumnLayout>
          </SpaceBetween>
        </Container>
      )}
    </SpaceBetween>
  );

  const renderStep3 = () => (
    <SpaceBetween size="l">
      <Header variant="h3">Review and Upload</Header>
      
      <Container>
        <SpaceBetween size="m">
          <Header variant="h4">Upload Summary</Header>
          <ColumnLayout columns={2}>
            <div>
              <Box variant="awsui-key-label">File</Box>
              <Box>{uploadFile[0]?.name}</Box>
            </div>
            <div>
              <Box variant="awsui-key-label">Orders to Create</Box>
              <Box>{validationResults?.totalRows}</Box>
            </div>
            <div>
              <Box variant="awsui-key-label">Automation Method</Box>
              <Box>{automationMethod.label}</Box>
            </div>
            <div>
              <Box variant="awsui-key-label">AI Model</Box>
              <Box>{aiModel.includes('claude-sonnet-4') ? 'Claude Sonnet 4' : aiModel}</Box>
            </div>
          </ColumnLayout>
        </SpaceBetween>
      </Container>

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
        <strong>Important:</strong> This will create {validationResults?.totalRows} orders in your system. 
        Make sure your automation settings are correct before proceeding.
      </Alert>
    </SpaceBetween>
  );

  const getStepContent = () => {
    switch (currentStep) {
      case 1: return renderStep1();
      case 2: return renderStep2();
      case 3: return renderStep3();
      default: return renderStep1();
    }
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1: return uploadFile.length > 0 && validationResults?.hasHeader;
      case 2: return automationMethod && aiModel;
      case 3: return true;
      default: return false;
    }
  };

  return (
    <Modal
      visible={visible}
      onDismiss={onDismiss}
      header="CSV Batch Upload Wizard"
      closeAriaLabel="Close modal"
      size="large"
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={onDismiss} disabled={uploading}>
              Cancel
            </Button>
            <Button onClick={downloadSampleCSV} disabled={uploading}>
              Download Sample
            </Button>
            {currentStep > 1 && (
              <Button onClick={handleBack} disabled={uploading}>
                Back
              </Button>
            )}
            {currentStep < 3 ? (
              <Button 
                variant="primary" 
                onClick={handleNext}
                disabled={!canProceed() || uploading}
              >
                Next
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={handleUpload}
                disabled={!canProceed()}
                loading={uploading}
              >
                Upload & Create Orders
              </Button>
            )}
          </SpaceBetween>
        </Box>
      }
    >
      <SpaceBetween size="l">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            {[1, 2, 3].map((step) => (
              <div key={step} style={{ display: 'flex', alignItems: 'center' }}>
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    backgroundColor: currentStep >= step ? '#0972d3' : '#e9ebed',
                    color: currentStep >= step ? 'white' : '#5f6b7a',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 'bold',
                    fontSize: '14px'
                  }}
                >
                  {step}
                </div>
                {step < 3 && (
                  <div
                    style={{
                      width: '40px',
                      height: '2px',
                      backgroundColor: currentStep > step ? '#0972d3' : '#e9ebed',
                      marginLeft: '10px'
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {getStepContent()}
      </SpaceBetween>
    </Modal>
  );
};

export default CSVBatchWizard;