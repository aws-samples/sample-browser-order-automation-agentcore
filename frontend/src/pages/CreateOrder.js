import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Header,
  SpaceBetween,
  Button,
  FormField,
  Input,
  Select,
  Textarea,
  ColumnLayout,
  Box,
  ExpandableSection
} from '@cloudscape-design/components';
import ModelSelector from '../components/ModelSelector';

const CreateOrder = ({ addNotification }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [retailerUrls, setRetailerUrls] = useState([]);
  const [loadingRetailers, setLoadingRetailers] = useState(true);
  const [secrets, setSecrets] = useState([]);
  const [formData, setFormData] = useState({
    // Required fields - minimal for demo
    retailer: '', // User will type retailer name
    product_url: '', // No default URL
    product_name: '',

    // Optional fields - demo mode
    customer_name: 'Demo Customer',
    customer_email: 'demo@example.com',
    shipping_first_name: 'Demo',
    shipping_last_name: 'User',
    shipping_address_1: '123 Demo Street',
    shipping_city: 'Demo City',
    shipping_state: 'CA',
    shipping_postal_code: '12345',
    shipping_country: 'US',

    // Agent will figure these out
    product_size: '',
    product_color: '',
    product_quantity: 1,
    product_price: '',
    shipping_address_2: '',
    automation_method: 'nova_act', // Default to Nova Act + AgentCore Browser
    ai_model: 'nova_act',

    // Instructions for agent (optional)
    instructions: ''
  });
  
  const [userSelectedModel, setUserSelectedModel] = useState(false);

  const fetchRetailerUrls = useCallback(async () => {
    try {
      setLoadingRetailers(true);
      const response = await fetch('/api/config/retailer-urls');
      if (response.ok) {
        const data = await response.json();
        setRetailerUrls(data.retailer_urls || []);
      }
    } catch (error) {
      console.error('Failed to fetch retailer URLs:', error);
      addNotification({
        type: 'error',
        header: 'Failed to load retailers',
        content: error.message
      });
    } finally {
      setLoadingRetailers(false);
    }
  }, [addNotification]);

  const fetchSecrets = useCallback(async () => {
    try {
      const response = await fetch('/api/secrets');
      if (response.ok) {
        const data = await response.json();
        setSecrets(data.secrets || []);
      } else {
        console.warn('Failed to fetch secrets, using empty array');
        setSecrets([]);
      }
    } catch (error) {
      console.error('Failed to fetch secrets:', error);
      setSecrets([]); // Set empty array on error
    }
  }, []);

  useEffect(() => {
    fetchRetailerUrls();
    fetchSecrets();
  }, [fetchRetailerUrls, fetchSecrets]);

  const handleInputChange = (field, value) => {
    setFormData(prev => {
      const newData = {
        ...prev,
        [field]: value
      };

      // When automation method changes to nova_act, set AI model to Nova Act
      if (field === 'automation_method' && value === 'nova_act') {
        newData.ai_model = 'nova_act';
        setUserSelectedModel(false); // Reset user selection tracking
      }
      // When automation method changes from nova_act to strands, set default only if user hasn't selected
      else if (field === 'automation_method' && value === 'strands' && prev.automation_method === 'nova_act' && !userSelectedModel) {
        newData.ai_model = 'us.anthropic.claude-sonnet-4-20250514-v1:0';
      }

      return newData;
    });
  };

  const validateForm = () => {
    return formData.retailer && formData.product_name;
  };

  const hasCredentialsForRetailer = (retailerName) => {
    if (!retailerName || !secrets.length) return false;
    
    // Check for exact name match
    const exactMatch = secrets.find(secret => 
      secret.site_name.toLowerCase() === retailerName.toLowerCase()
    );
    if (exactMatch) return true;
    
    // Check for partial name match
    const partialMatch = secrets.find(secret => 
      secret.site_name.toLowerCase().includes(retailerName.toLowerCase()) ||
      retailerName.toLowerCase().includes(secret.site_name.toLowerCase())
    );
    return !!partialMatch;
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const orderData = {
        customer_name: formData.customer_name,
        customer_email: formData.customer_email,
        retailer: formData.retailer,
        automation_method: formData.automation_method,
        ai_model: formData.ai_model,
        product: {
          url: formData.product_url,
          name: formData.product_name,
          size: formData.product_size || undefined,
          color: formData.product_color || undefined,
          quantity: formData.product_quantity,
          price: formData.product_price ? parseFloat(formData.product_price) : undefined
        },
        shipping_address: {
          first_name: formData.shipping_first_name,
          last_name: formData.shipping_last_name,
          address_line_1: formData.shipping_address_1,
          address_line_2: formData.shipping_address_2 || undefined,
          city: formData.shipping_city,
          state: formData.shipping_state,
          postal_code: formData.shipping_postal_code,
          country: formData.shipping_country
        },

        instructions: formData.instructions || undefined
      };

      const response = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
      });

      if (!response.ok) {
        throw new Error('Failed to create order');
      }

      const result = await response.json();

      addNotification({
        type: 'success',
        header: 'Order Created',
        content: `Order ${result.order_id} has been created successfully`
      });

      navigate('/dashboard');

    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Order Creation Failed',
        content: `Failed to create order: ${error.message}`
      });
    } finally {
      setLoading(false);
    }
  };

  // Get unique retailers for dropdown
  const getRetailerOptions = () => {
    const uniqueRetailers = {};
    retailerUrls.forEach(url => {
      if (!uniqueRetailers[url.retailer]) {
        uniqueRetailers[url.retailer] = {
          label: url.retailer.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          value: url.retailer
        };
      }
    });
    return Object.values(uniqueRetailers);
  };

  // Get default URL for selected retailer
  const getDefaultUrlForRetailer = (retailer) => {
    const defaultUrl = retailerUrls.find(url => url.retailer === retailer && url.is_default);
    return defaultUrl ? defaultUrl.starting_url : '';
  };

  // Handle retailer change
  const handleRetailerChange = (retailer) => {
    handleInputChange('retailer', retailer);
    // Always update product URL with default URL for selected retailer
    const defaultUrl = getDefaultUrlForRetailer(retailer);
    if (defaultUrl) {
      handleInputChange('product_url', defaultUrl);
    }
  };



  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="An order automation request groups together product information, customer details, and automation settings for AI-powered e-commerce purchasing."
        actions={
          <Button
            iconName="arrow-left"
            onClick={() => navigate('/dashboard')}
          >
            Back to Dashboard
          </Button>
        }
      >
        Create order
      </Header>

      <Container header={<Header variant="h2">Order configuration</Header>}>
        <SpaceBetween size="l">
          <ColumnLayout columns={3}>
            <div style={{ gridColumn: 'span 2' }}>
              <FormField
                label="Product name"
                constraintText="Product name must be 1 to 255 characters. Valid characters are a-z, A-Z, 0-9, hyphens (-), and underscores (_)."
              >
                <Input
                  value={formData.product_name}
                  onChange={({ detail }) => handleInputChange('product_name', detail.value)}
                  placeholder="Enter product name"
                />
              </FormField>
            </div>
            <FormField label="Retailer">
              <SpaceBetween size="xs">
                <Select
                  selectedOption={getRetailerOptions().find(opt => opt.value === formData.retailer) || null}
                  onChange={({ detail }) => handleRetailerChange(detail.selectedOption.value)}
                  options={getRetailerOptions()}
                  placeholder={loadingRetailers ? "Loading retailers..." : "Select retailer"}
                  disabled={loadingRetailers}
                  empty={loadingRetailers ? "Loading..." : "No retailers configured. Add retailers in Settings."}
                />
                {formData.retailer && hasCredentialsForRetailer(formData.retailer) && (
                  <Box color="text-status-success" fontSize="body-s">
                    ✓ Login credentials available in Secret Vault
                  </Box>
                )}
                {formData.retailer && !hasCredentialsForRetailer(formData.retailer) && (
                  <Box color="text-status-warning" fontSize="body-s">
                    ⚠ No login credentials found. Add credentials in Secret Vault if login is required.
                  </Box>
                )}
              </SpaceBetween>
            </FormField>
          </ColumnLayout>

          <FormField label="Automation method" description="All methods use AgentCore Browser for secure, scalable automation">
            <Select
              selectedOption={
                formData.automation_method === 'nova_act'
                  ? { label: 'Nova Act + AgentCore Browser', value: 'nova_act' }
                  : { label: 'Strands + AgentCore Browser + Browser Tools', value: 'strands' }
              }
              onChange={({ detail }) => handleInputChange('automation_method', detail.selectedOption.value)}
              options={[
                { label: 'Nova Act + AgentCore Browser', value: 'nova_act' },
                { label: 'Strands + AgentCore Browser + Browser Tools', value: 'strands' }
              ]}
            />
          </FormField>

          {formData.automation_method === 'nova_act' && (
            <ModelSelector
              selectedModel={formData.ai_model}
              onChange={(model) => handleInputChange('ai_model', model)}
              label="AI Model"
              description="Model used for generating Nova Act instructions. Nova Act uses its internal model with AgentCore Browser for execution."
              disabled={true}
            />
          )}

          {formData.automation_method === 'strands' && (
            <ModelSelector
              selectedModel={formData.ai_model}
              onChange={(model) => {
                handleInputChange('ai_model', model);
                setUserSelectedModel(true); // Mark that user manually selected a model
              }}
              label="AI Model"
              description="Bedrock model used with Strands and AgentCore Browser for web automation"
            />
          )}
        </SpaceBetween>
      </Container>

      <ExpandableSection headerText="Product details - optional" variant="container" defaultExpanded={true}>
        <SpaceBetween size="l">

          <FormField label="Product URL (starting URL)" constraintText="Optional - helps agent locate the product">
            <Input
              value={formData.product_url}
              onChange={({ detail }) => handleInputChange('product_url', detail.value)}
              placeholder="https://www.example.com/product"
            />
          </FormField>

          <ColumnLayout columns={3}>
            <FormField label="Size" constraintText="Leave empty for auto-detection">
              <Input
                value={formData.product_size}
                onChange={({ detail }) => handleInputChange('product_size', detail.value)}
                placeholder="Auto-detect"
              />
            </FormField>
            <FormField label="Color" constraintText="Leave empty for auto-detection">
              <Input
                value={formData.product_color}
                onChange={({ detail }) => handleInputChange('product_color', detail.value)}
                placeholder="Auto-detect"
              />
            </FormField>
            <FormField label="Quantity">
              <Input
                value={formData.product_quantity.toString()}
                onChange={({ detail }) => handleInputChange('product_quantity', parseInt(detail.value) || 1)}
                type="number"
                placeholder="1"
              />
            </FormField>
          </ColumnLayout>
        </SpaceBetween>
      </ExpandableSection>



      <ExpandableSection headerText="Instructions - optional" variant="container">
        <SpaceBetween size="l">

          <FormField
            label="Special instructions"
            description="Tell the agent any specific requirements or preferences"
          >
            <Textarea
              value={formData.instructions}
              onChange={({ detail }) => handleInputChange('instructions', detail.value)}
              placeholder="e.g., 'Choose the blue color if available', 'Select size Large', 'Use fastest shipping option'"
              rows={4}
            />
          </FormField>
        </SpaceBetween>
      </ExpandableSection>

      <Box float="right">
        <SpaceBetween size="m" direction="horizontal">
          <Button onClick={() => navigate('/dashboard')}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            loading={loading}
            disabled={!validateForm()}
          >
            Create
          </Button>
        </SpaceBetween>
      </Box>
    </SpaceBetween>
  );
};

export default CreateOrder;