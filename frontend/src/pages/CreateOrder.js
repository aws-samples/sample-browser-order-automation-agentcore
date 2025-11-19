import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
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
  const { orderId } = useParams(); // If orderId exists, we're in edit mode
  const isEditMode = !!orderId;
  const [loading, setLoading] = useState(false);
  const [loadingOrder, setLoadingOrder] = useState(isEditMode);
  const [retailerUrls, setRetailerUrls] = useState([]);
  const [loadingRetailers, setLoadingRetailers] = useState(true);
  const [secrets, setSecrets] = useState([]);
  const [formData, setFormData] = useState({
    // Required fields - minimal for demo
    retailer: '', // User will type retailer name
    product_url: '', // No default URL
    product_name: '',

    // Optional fields - demo mode
    customer_name: 'Jane Doe',
    customer_email: 'jane.doe@example.com',
    customer_phone: '4154351234',
    shipping_first_name: 'Jane',
    shipping_last_name: 'Doe',
    shipping_address_1: '123 Main Street',
    shipping_city: 'San Francisco',
    shipping_state: 'CA',
    shipping_postal_code: '94102',
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

  // Load order data in edit mode
  useEffect(() => {
    const loadOrder = async () => {
      if (!isEditMode) return;
      
      try {
        setLoadingOrder(true);
        const response = await fetch(`/api/orders/${orderId}`);
        if (!response.ok) throw new Error('Failed to load order');
        
        const order = await response.json();
        
        // Helper function to filter out dash values
        const filterDash = (value) => (value === '-' ? '' : value || '');
        
        // Populate form with order data
        setFormData({
          retailer: order.retailer || '',
          product_url: order.product_url || '',
          product_name: order.product_name || '',
          customer_name: order.customer_name || '',
          customer_email: order.customer_email || '',
          customer_phone: order.shipping_address?.phone || '',
          shipping_first_name: order.shipping_address?.first_name || '',
          shipping_last_name: order.shipping_address?.last_name || '',
          shipping_address_1: order.shipping_address?.address_line_1 || '',
          shipping_address_2: order.shipping_address?.address_line_2 || '',
          shipping_city: order.shipping_address?.city || '',
          shipping_state: order.shipping_address?.state || '',
          shipping_postal_code: order.shipping_address?.postal_code || '',
          shipping_country: order.shipping_address?.country || 'US',
          product_size: filterDash(order.product_size),
          product_color: filterDash(order.product_color),
          product_quantity: order.product_quantity || 1,
          product_price: order.product_price || '',
          automation_method: order.automation_method || 'nova_act',
          ai_model: order.ai_model || 'nova_act',
          instructions: filterDash(order.instructions)
        });
      } catch (error) {
        addNotification({
          type: 'error',
          header: 'Failed to load order',
          content: error.message
        });
        navigate('/dashboard');
      } finally {
        setLoadingOrder(false);
      }
    };
    
    loadOrder();
  }, [isEditMode, orderId, addNotification, navigate]);

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
        newData.ai_model = 'global.anthropic.claude-sonnet-4-5-20250929-v1:0';
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
      if (isEditMode) {
        // Edit mode - update existing order
        const updateData = {
          product_name: formData.product_name,
          product_url: formData.product_url,
          product_size: formData.product_size,  // Allow empty string to clear value
          product_color: formData.product_color,  // Allow empty string to clear value
          instructions: formData.instructions,  // Allow empty string to clear value
          customer_name: formData.customer_name,
          customer_email: formData.customer_email,
          shipping_address: {
            first_name: formData.shipping_first_name,
            last_name: formData.shipping_last_name,
            address_line_1: formData.shipping_address_1,
            address_line_2: formData.shipping_address_2 || undefined,
            city: formData.shipping_city,
            state: formData.shipping_state,
            postal_code: formData.shipping_postal_code,
            country: formData.shipping_country,
            phone: formData.customer_phone || '4154351234'
          }
        };

        const response = await fetch(`/api/orders/${orderId}/edit`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updateData)
        });

        if (!response.ok) {
          throw new Error('Failed to update order');
        }

        addNotification({
          type: 'success',
          header: 'Order Updated',
          content: 'Order has been updated successfully'
        });

        navigate(`/orders/${orderId}`);
      } else {
        // Create mode - create new order
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
            country: formData.shipping_country,
            phone: formData.customer_phone || '4154351234'
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
      }

    } catch (error) {
      addNotification({
        type: 'error',
        header: isEditMode ? 'Order Update Failed' : 'Order Creation Failed',
        content: `Failed to ${isEditMode ? 'update' : 'create'} order: ${error.message}`
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
        description={isEditMode ? "Edit order details and retry with updated information." : "An order automation request groups together product information, customer details, and automation settings for AI-powered e-commerce purchasing."}
        actions={
          <Button
            iconName="arrow-left"
            onClick={() => navigate(isEditMode ? `/orders/${orderId}` : '/dashboard')}
          >
            {isEditMode ? 'Back to Order' : 'Back to Dashboard'}
          </Button>
        }
      >
        {isEditMode ? 'Edit order' : 'Create order'}
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

      <ExpandableSection headerText="Customer & Shipping - optional" variant="container" defaultExpanded={false}>
        <SpaceBetween size="l">
          <ColumnLayout columns={2}>
            <FormField label="Customer Name">
              <Input
                value={formData.customer_name}
                onChange={({ detail }) => handleInputChange('customer_name', detail.value)}
                placeholder="Demo Customer"
              />
            </FormField>
            <FormField label="Customer Email">
              <Input
                value={formData.customer_email}
                onChange={({ detail }) => handleInputChange('customer_email', detail.value)}
                placeholder="demo@example.com"
                type="email"
              />
            </FormField>
          </ColumnLayout>

          <FormField label="Phone Number">
            <Input
              value={formData.customer_phone}
              onChange={({ detail }) => handleInputChange('customer_phone', detail.value)}
              placeholder="4154351234"
              type="tel"
            />
          </FormField>

          <ColumnLayout columns={2}>
            <FormField label="First Name">
              <Input
                value={formData.shipping_first_name}
                onChange={({ detail }) => handleInputChange('shipping_first_name', detail.value)}
                placeholder="Demo"
              />
            </FormField>
            <FormField label="Last Name">
              <Input
                value={formData.shipping_last_name}
                onChange={({ detail }) => handleInputChange('shipping_last_name', detail.value)}
                placeholder="User"
              />
            </FormField>
          </ColumnLayout>

          <FormField label="Address Line 1">
            <Input
              value={formData.shipping_address_1}
              onChange={({ detail }) => handleInputChange('shipping_address_1', detail.value)}
              placeholder="123 Demo Street"
            />
          </FormField>

          <FormField label="Address Line 2 (Optional)">
            <Input
              value={formData.shipping_address_2}
              onChange={({ detail }) => handleInputChange('shipping_address_2', detail.value)}
              placeholder="Apt, Suite, etc."
            />
          </FormField>

          <ColumnLayout columns={3}>
            <FormField label="City">
              <Input
                value={formData.shipping_city}
                onChange={({ detail }) => handleInputChange('shipping_city', detail.value)}
                placeholder="Demo City"
              />
            </FormField>
            <FormField label="State">
              <Input
                value={formData.shipping_state}
                onChange={({ detail }) => handleInputChange('shipping_state', detail.value)}
                placeholder="CA"
              />
            </FormField>
            <FormField label="Postal Code">
              <Input
                value={formData.shipping_postal_code}
                onChange={({ detail }) => handleInputChange('shipping_postal_code', detail.value)}
                placeholder="12345"
              />
            </FormField>
          </ColumnLayout>

          <FormField label="Country">
            <Input
              value={formData.shipping_country}
              onChange={({ detail }) => handleInputChange('shipping_country', detail.value)}
              placeholder="US"
            />
          </FormField>
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
            loading={loading || loadingOrder}
            disabled={!validateForm() || loadingOrder}
          >
            {isEditMode ? 'Save Changes' : 'Create'}
          </Button>
        </SpaceBetween>
      </Box>
    </SpaceBetween>
  );
};

export default CreateOrder;