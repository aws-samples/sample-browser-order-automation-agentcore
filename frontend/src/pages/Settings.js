import { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Box,
  Button,
  FormField,
  Input,
  Select,
  Spinner,
  Table,
  Modal,
  Toggle,
} from '@cloudscape-design/components';

const Settings = ({ addNotification }) => {
  const [loading, setLoading] = useState(true);
  const [systemConfig, setSystemConfig] = useState({});
  const [originalConfig, setOriginalConfig] = useState({});
  const [hasChanges, setHasChanges] = useState(false);
  const [isEditingApiKey, setIsEditingApiKey] = useState(false);

  // AWS Resources state
  const [awsStatus, setAwsStatus] = useState(null);
  const [iamLoading, setIamLoading] = useState(false);
  const [iamLoaded, setIamLoaded] = useState(false);
  const [s3Loading, setS3Loading] = useState(false);
  const [s3Loaded, setS3Loaded] = useState(false);

  // Retailer URLs state
  const [retailerUrls, setRetailerUrls] = useState([]);
  const [urlsLoading, setUrlsLoading] = useState(false);
  const [showUrlModal, setShowUrlModal] = useState(false);
  const [editingUrl, setEditingUrl] = useState(null);
  const [urlFormData, setUrlFormData] = useState({
    retailer: '',
    website_name: '',
    starting_url: '',
    is_default: false
  });

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);

      // Only load system config (fast)
      const configResponse = await fetch('/api/settings/config');
      if (configResponse.ok) {
        const configData = await configResponse.json();
        const config = configData.config || {};
        setSystemConfig(config);
        setOriginalConfig(config);
        setHasChanges(false);
      }

    } catch (error) {
      console.error('Failed to load settings:', error);
      addNotification({
        type: 'error',
        header: 'Failed to load settings',
        content: error.message
      });
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  const loadIamRoles = useCallback(async () => {
    if (iamLoaded || iamLoading) return;

    try {
      setIamLoading(true);
      const response = await fetch('/api/settings/aws/search-iam-roles');

      if (response.ok) {
        const data = await response.json();

        setAwsStatus(prev => ({
          ...prev,
          execution_roles: data.execution_roles || []
        }));
      } else {
        await response.text();
        throw new Error('Failed to load IAM roles');
      }

      setIamLoaded(true);
    } catch (error) {
      console.warn('IAM roles loading failed:', error);
      setAwsStatus(prev => ({
        ...prev,
        execution_roles: []
      }));
      setIamLoaded(true);
    } finally {
      setIamLoading(false);
    }
  }, [iamLoaded, iamLoading]);

  const loadS3Buckets = useCallback(async () => {
    if (s3Loaded || s3Loading) return;

    try {
      setS3Loading(true);
      const response = await fetch('/api/settings/aws/search-s3-buckets');

      if (response.ok) {
        const data = await response.json();

        setAwsStatus(prev => ({
          ...prev,
          s3_buckets: data.s3_buckets || []
        }));
      } else {
        await response.text();
        throw new Error('Failed to load S3 buckets');
      }

      setS3Loaded(true);
    } catch (error) {
      console.warn('S3 buckets loading failed:', error);
      setAwsStatus(prev => ({
        ...prev,
        s3_buckets: []
      }));
      setS3Loaded(true);
    } finally {
      setS3Loading(false);
    }
  }, [s3Loaded, s3Loading]);

  const loadRetailerUrls = useCallback(async () => {
    try {
      setUrlsLoading(true);
      const response = await fetch('/api/config/retailer-urls');
      if (response.ok) {
        const data = await response.json();
        setRetailerUrls(data.retailer_urls || []);
      }
    } catch (error) {
      console.error('Failed to load retailer URLs:', error);
      addNotification({
        type: 'error',
        header: 'Failed to load retailer URLs',
        content: error.message
      });
    } finally {
      setUrlsLoading(false);
    }
  }, [addNotification]);

  const handleSaveUrl = async () => {
    try {
      const method = editingUrl ? 'PUT' : 'POST';
      const url = editingUrl ? `/api/config/retailer-urls/${editingUrl.id}` : '/api/config/retailer-urls';
      
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(urlFormData)
      });

      if (response.ok) {
        addNotification({
          type: 'success',
          header: editingUrl ? 'URL Updated' : 'URL Added',
          content: `Retailer URL has been ${editingUrl ? 'updated' : 'added'} successfully`
        });
        setShowUrlModal(false);
        setEditingUrl(null);
        setUrlFormData({ retailer: '', website_name: '', starting_url: '', is_default: false });
        loadRetailerUrls();
      } else {
        throw new Error('Failed to save URL');
      }
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Save Failed',
        content: error.message
      });
    }
  };

  const handleDeleteUrl = async (urlId) => {
    try {
      const response = await fetch(`/api/config/retailer-urls/${urlId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        addNotification({
          type: 'success',
          header: 'URL Deleted',
          content: 'Retailer URL has been deleted successfully'
        });
        loadRetailerUrls();
      } else {
        throw new Error('Failed to delete URL');
      }
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Delete Failed',
        content: error.message
      });
    }
  };

  const handleEditUrl = (url) => {
    setEditingUrl(url);
    setUrlFormData({
      retailer: url.retailer,
      website_name: url.website_name,
      starting_url: url.starting_url,
      is_default: url.is_default
    });
    setShowUrlModal(true);
  };

  const handleAddUrl = () => {
    setEditingUrl(null);
    setUrlFormData({ retailer: '', website_name: '', starting_url: '', is_default: false });
    setShowUrlModal(true);
  };

  useEffect(() => {
    loadSettings();
    loadRetailerUrls();
  }, [loadSettings, loadRetailerUrls]);

  const validateNovaActApiKey = (key) => {
    // UUID v4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(key);
  };



  const handleConfigChange = (key, value) => {
    // Nova Act API Key 편집 상태 관리
    if (key === 'nova_act_api_key') {
      setIsEditingApiKey(true);
    }

    // 로컬 상태만 업데이트 (저장하지 않음)
    setSystemConfig(prev => {
      const newConfig = { ...prev, [key]: value };
      // 변경사항이 있는지 확인
      const hasChanges = JSON.stringify(newConfig) !== JSON.stringify(originalConfig);
      setHasChanges(hasChanges);
      return newConfig;
    });
  };

  const handleSaveSettings = async () => {
    try {
      // Nova Act API Key 검증
      if (systemConfig.nova_act_api_key && !validateNovaActApiKey(systemConfig.nova_act_api_key)) {
        addNotification({
          type: 'error',
          header: 'Invalid API Key',
          content: 'Nova Act API Key must be in UUID format (e.g., 12345678-1234-1234-1234-123456789abc)'
        });
        return;
      }

      const response = await fetch('/api/settings/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: systemConfig })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result = await response.json();

      // Check for success - handle both status field and HTTP success
      if (response.ok && (result.status === 'success' || !result.status)) {
        // 저장 성공 후 DB에서 최신 설정을 다시 로드하여 동기화
        const configResponse = await fetch('/api/settings/config');
        if (configResponse.ok) {
          const configData = await configResponse.json();
          const updatedConfig = configData.config || {};
          setSystemConfig(updatedConfig);
          setOriginalConfig(updatedConfig);
        }

        setHasChanges(false);
        setIsEditingApiKey(false); // 저장 후 API 키 편집 상태 해제
        addNotification({
          type: 'success',
          header: 'Settings Saved',
          content: 'All configuration settings have been saved successfully'
        });
      } else {
        throw new Error(result.message || result.detail || 'Failed to save configuration');
      }

    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Save Error',
        content: error.message
      });
    }
  };

  const handleResetToDefaults = () => {
    // 기본값으로 리셋 (저장하지 않음)
    const defaultConfig = {
      agentcore_region: 'us-west-2',
      session_replay_s3_bucket: '',
      session_replay_s3_prefix: 'session-replays/',
      browser_session_timeout: 3600,
      max_concurrent_orders: 5,
      default_model: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
      nova_act_api_key: '',
      execution_role_arn: '',
      processing_timeout: 1800
    };

    setSystemConfig(defaultConfig);
    const hasChanges = JSON.stringify(defaultConfig) !== JSON.stringify(originalConfig);
    setHasChanges(hasChanges);
    setIsEditingApiKey(true); // Reset 시 API 키 편집 가능하도록

    addNotification({
      type: 'info',
      header: 'Reset to Defaults',
      content: 'Settings have been reset to default values. Click Save to apply changes.'
    });
  };

  if (loading) {
    return (
      <Container>
        <Box textAlign="center" padding="xxl">
          <Spinner size="large" />
          <Box variant="p" padding={{ top: 's' }}>Loading settings...</Box>
        </Box>
      </Container>
    );
  }

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Configure AWS services and automation settings for intelligent browser automation"
        actions={
          <Button
            variant="primary"
            iconName="refresh"
            onClick={loadSettings}
            loading={loading}
          >
            Refresh
          </Button>
        }
      >
        Automation Settings
      </Header>

      {/* AWS Infrastructure */}
      <Container header={<Header variant="h2">AWS Infrastructure</Header>}>
        <SpaceBetween size="m">
          <FormField label="AWS Region" description="Primary AWS region for all services and resources">
            <Select
              selectedOption={{
                label: systemConfig.agentcore_region === 'us-west-2' ? 'US West 2 (Oregon)' :
                  systemConfig.agentcore_region === 'us-east-1' ? 'US East 1 (N. Virginia)' :
                    'US West 2 (Oregon)',
                value: systemConfig.agentcore_region || 'us-west-2'
              }}
              onChange={({ detail }) =>
                handleConfigChange('agentcore_region', detail.selectedOption.value)
              }
              options={[
                { label: 'US West 2 (Oregon)', value: 'us-west-2' },
                { label: 'US East 1 (N. Virginia)', value: 'us-east-1' }
              ]}
            />
          </FormField>

          <FormField label="IAM Execution Role" description="IAM role with permissions for AgentCore browser automation">
            <Select
              selectedOption={
                systemConfig.execution_role_arn ? {
                  label: awsStatus?.execution_roles?.find(role => role.value === systemConfig.execution_role_arn)?.label ||
                    systemConfig.execution_role_arn.split('/').pop() ||
                    systemConfig.execution_role_arn,
                  value: systemConfig.execution_role_arn
                } : null
              }
              onChange={({ detail }) =>
                handleConfigChange('execution_role_arn', detail.selectedOption.value)
              }
              onFocus={loadIamRoles}
              options={
                (() => {

                  
                  // 백엔드에서 {value: arn, label: name} 구조로 반환됨
                  const roleOptions = awsStatus?.execution_roles || [];



                  // Add current value if it's not in the AWS list (for saved values)
                  if (systemConfig.execution_role_arn &&
                    !roleOptions.find(opt => opt.value === systemConfig.execution_role_arn)) {
                    const roleName = systemConfig.execution_role_arn.split('/').pop() || systemConfig.execution_role_arn;
                    roleOptions.unshift({
                      label: `${roleName} (current)`,
                      value: systemConfig.execution_role_arn
                    });
                  }

                  return roleOptions;
                })()
              }
              placeholder={iamLoaded ? (awsStatus?.execution_roles?.length > 0 ? "Select execution role" : "No roles available") : "Click to load roles"}
              empty={iamLoading ? "Loading execution roles..." : iamLoaded ? "No execution roles found. Check AWS credentials and permissions." : "Click dropdown to load roles"}
              filteringType="auto"
            />
          </FormField>
        </SpaceBetween>
      </Container>

      {/* Amazon Bedrock Configuration */}
      <Container header={<Header variant="h2">Amazon Bedrock Configuration</Header>}>
        <SpaceBetween size="m">
          <FormField label="Foundation Model" description="Amazon Bedrock foundation model for Strands automation agents">
            <Select
              selectedOption={{
                label: systemConfig.default_model?.includes('claude-sonnet-4') ? 'Claude Sonnet 4' :
                  systemConfig.default_model?.includes('claude-3-7-sonnet') ? 'Claude 3.7 Sonnet' :
                    systemConfig.default_model?.includes('nova-pro') ? 'Amazon Nova Pro' :
                      systemConfig.default_model?.includes('gpt-oss-120b') ? 'GPT-OSS 120B' :
                        systemConfig.default_model?.includes('gpt-oss-20b') ? 'GPT-OSS 20B' :
                          systemConfig.default_model?.includes('deepseek.v3') ? 'DeepSeek V3' :
                            'Claude Sonnet 4',
                value: systemConfig.default_model || 'us.anthropic.claude-sonnet-4-20250514-v1:0'
              }}
              onChange={({ detail }) =>
                handleConfigChange('default_model', detail.selectedOption.value)
              }
              options={[
                {
                  label: 'Claude Sonnet 4',
                  value: 'us.anthropic.claude-sonnet-4-20250514-v1:0'
                },
                {
                  label: 'Claude 3.7 Sonnet',
                  value: 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
                },
                {
                  label: 'Amazon Nova Pro',
                  value: 'us.amazon.nova-pro-v1:0'
                },
                {
                  label: 'GPT-OSS 120B',
                  value: 'openai.gpt-oss-120b-1:0'
                },
                {
                  label: 'GPT-OSS 20B',
                  value: 'openai.gpt-oss-20b-1:0'
                },
                {
                  label: 'DeepSeek V3',
                  value: 'deepseek.v3-v1:0'
                }
              ]}
            />
          </FormField>

          <FormField
            label="Nova Act API Key"
            description="API key for Nova Act automation service integration"
            constraintText="UUID format required (e.g., 12345678-1234-1234-1234-123456789abc)"
          >
            <Input
              type={isEditingApiKey || !originalConfig.nova_act_api_key ? "text" : "password"}
              value={
                isEditingApiKey
                  ? systemConfig.nova_act_api_key || ''
                  : originalConfig.nova_act_api_key && !isEditingApiKey
                    ? '••••••••••••••••'
                    : systemConfig.nova_act_api_key || ''
              }
              onChange={({ detail }) =>
                handleConfigChange('nova_act_api_key', detail.value)
              }
              onFocus={() => {
                if (originalConfig.nova_act_api_key && !isEditingApiKey) {
                  setIsEditingApiKey(true);
                  // 포커스 시 실제 값으로 변경
                  setSystemConfig(prev => ({ ...prev, nova_act_api_key: originalConfig.nova_act_api_key }));
                }
              }}
              placeholder={isEditingApiKey || !originalConfig.nova_act_api_key ? "Enter Nova Act API key" : ""}
              invalid={systemConfig.nova_act_api_key && !validateNovaActApiKey(systemConfig.nova_act_api_key)}
            />
          </FormField>
        </SpaceBetween>
      </Container>

      {/* Processing & Performance */}
      <Container header={<Header variant="h2">Processing & Performance</Header>}>
        <SpaceBetween size="m">
          <FormField label="Maximum Concurrent Orders" description="Maximum number of orders processed simultaneously">
            <Select
              selectedOption={{
                label: `${systemConfig.max_concurrent_orders || 5} orders`,
                value: systemConfig.max_concurrent_orders || 5
              }}
              onChange={({ detail }) =>
                handleConfigChange('max_concurrent_orders', parseInt(detail.selectedOption.value))
              }
              options={[
                { label: '1 order', value: 1 },
                { label: '3 orders', value: 3 },
                { label: '5 orders', value: 5 },
                { label: '10 orders', value: 10 },
                { label: '20 orders', value: 20 }
              ]}
            />
          </FormField>

          <FormField label="Processing Timeout" description="Maximum time allowed for order processing before timeout">
            <Select
              selectedOption={{
                label: `${Math.floor((systemConfig.processing_timeout || 1800) / 60)} minutes`,
                value: systemConfig.processing_timeout || 1800
              }}
              onChange={({ detail }) =>
                handleConfigChange('processing_timeout', parseInt(detail.selectedOption.value))
              }
              options={[
                { label: '5 minutes', value: 300 },
                { label: '10 minutes', value: 600 },
                { label: '15 minutes', value: 900 },
                { label: '30 minutes', value: 1800 },
                { label: '60 minutes', value: 3600 }
              ]}
            />
          </FormField>

          <FormField label="Browser Session Timeout" description="Maximum duration for browser sessions before automatic cleanup">
            <Select
              selectedOption={{
                label: `${Math.floor((systemConfig.browser_session_timeout || 3600) / 60)} minutes`,
                value: systemConfig.browser_session_timeout || 3600
              }}
              onChange={({ detail }) =>
                handleConfigChange('browser_session_timeout', parseInt(detail.selectedOption.value))
              }
              options={[
                { label: '30 minutes', value: 1800 },
                { label: '60 minutes', value: 3600 },
                { label: '120 minutes', value: 7200 },
                { label: '240 minutes', value: 14400 }
              ]}
            />
          </FormField>
        </SpaceBetween>
      </Container>

      {/* Amazon S3 Storage */}
      <Container header={<Header variant="h2">Amazon S3 Storage</Header>}>
        <SpaceBetween size="m">
          <FormField label="Session Recordings Bucket" description="S3 bucket for storing browser session recordings and screenshots">
            <Select
              selectedOption={
                systemConfig.session_replay_s3_bucket ? {
                  label: systemConfig.session_replay_s3_bucket,
                  value: systemConfig.session_replay_s3_bucket
                } : null
              }
              onChange={({ detail }) =>
                handleConfigChange('session_replay_s3_bucket', detail.selectedOption.value)
              }
              onFocus={loadS3Buckets}
              options={
                (() => {

                  
                  // 백엔드에서 {value: name, label: name} 구조로 반환됨
                  const bucketOptions = awsStatus?.s3_buckets || [];



                  // Add current value if it's not in the AWS list (for saved values)
                  if (systemConfig.session_replay_s3_bucket &&
                    !bucketOptions.find(opt => opt.value === systemConfig.session_replay_s3_bucket)) {
                    bucketOptions.unshift({
                      label: `${systemConfig.session_replay_s3_bucket} (current)`,
                      value: systemConfig.session_replay_s3_bucket
                    });
                  }

                  return bucketOptions;
                })()
              }
              placeholder={s3Loaded ? "Select S3 bucket" : "Click to load buckets"}
              empty={s3Loading ? "Loading S3 buckets..." : s3Loaded ? "No S3 buckets available" : "Click dropdown to load buckets"}
              filteringType="auto"
            />
          </FormField>

          <FormField label="S3 Object Prefix" description="S3 prefix for organizing session recordings and maintaining clean bucket structure">
            <Input
              value={systemConfig.session_replay_s3_prefix || 'session-replays/'}
              onChange={({ detail }) =>
                handleConfigChange('session_replay_s3_prefix', detail.value)
              }
              placeholder="session-replays/"
            />
          </FormField>
        </SpaceBetween>
      </Container>

      {/* Retailer URL Management */}
      <Table
          columnDefinitions={[
            {
              id: 'retailer',
              header: 'Retailer',
              cell: item => item.retailer,
              sortingField: 'retailer'
            },
            {
              id: 'website_name',
              header: 'Website Name',
              cell: item => item.website_name,
              sortingField: 'website_name'
            },
            {
              id: 'starting_url',
              header: 'Starting URL',
              cell: item => (
                <a href={item.starting_url} target="_blank" rel="noopener noreferrer">
                  {item.starting_url}
                </a>
              )
            },
            {
              id: 'is_default',
              header: 'Default',
              cell: item => item.is_default ? '✓ Default' : '',
              sortingField: 'is_default'
            },
            {
              id: 'actions',
              header: 'Actions',
              cell: item => (
                <SpaceBetween direction="horizontal" size="xs">
                  <Button size="small" onClick={() => handleEditUrl(item)}>
                    Edit
                  </Button>
                  <Button size="small" onClick={() => handleDeleteUrl(item.id)}>
                    Delete
                  </Button>
                </SpaceBetween>
              )
            }
          ]}
          items={retailerUrls}
          loading={urlsLoading}
          loadingText="Loading retailer URLs..."
          sortingDisabled={false}
          empty={
            <Box textAlign="center" color="inherit">
              <b>No retailer URLs configured</b>
              <Box variant="p" color="inherit">
                Add retailer URLs to configure starting pages for automation.
              </Box>
            </Box>
          }
          header={
            <Header
              variant="h2"
              counter={`(${retailerUrls.length})`}
              description="Configure starting URLs for each retailer used by automation agents"
              actions={
                <Button variant="primary" iconName="add-plus" onClick={handleAddUrl}>
                  Add URL
                </Button>
              }
            >
              Retailer URL Management
            </Header>
          }
        />

      {/* URL Add/Edit Modal */}
      <Modal
        onDismiss={() => setShowUrlModal(false)}
        visible={showUrlModal}
        closeAriaLabel="Close modal"
        size="medium"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setShowUrlModal(false)}>
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={handleSaveUrl}
                disabled={!urlFormData.retailer || !urlFormData.website_name || !urlFormData.starting_url}
              >
                {editingUrl ? 'Update' : 'Add'} URL
              </Button>
            </SpaceBetween>
          </Box>
        }
        header={editingUrl ? 'Edit Retailer URL' : 'Add Retailer URL'}
      >
        <SpaceBetween size="m">
          <FormField label="Retailer" description="Enter the retailer name (e.g., example-store, my-retailer)">
            <Input
              value={urlFormData.retailer}
              onChange={({ detail }) => 
                setUrlFormData(prev => ({ ...prev, retailer: detail.value }))
              }
              placeholder="Enter retailer name"
            />
          </FormField>

          <FormField label="Website Name" description="Descriptive name for this URL (e.g., 'Official Store', 'Women's Section')">
            <Input
              value={urlFormData.website_name}
              onChange={({ detail }) => 
                setUrlFormData(prev => ({ ...prev, website_name: detail.value }))
              }
              placeholder="e.g., Official Store, Women's Section"
            />
          </FormField>

          <FormField label="Starting URL" description="The URL where automation will begin">
            <Input
              value={urlFormData.starting_url}
              onChange={({ detail }) => 
                setUrlFormData(prev => ({ ...prev, starting_url: detail.value }))
              }
              placeholder="https://www.example.com"
            />
          </FormField>

          <FormField label="Default URL" description="Set this as the default starting URL for this retailer">
            <Toggle
              onChange={({ detail }) => 
                setUrlFormData(prev => ({ ...prev, is_default: detail.checked }))
              }
              checked={urlFormData.is_default}
            >
              Use as default URL for this retailer
            </Toggle>
          </FormField>
        </SpaceBetween>
      </Modal>

      {/* Save Settings - Outside container with right alignment */}
      <Box float="right">
        <SpaceBetween direction="horizontal" size="xs">
          <Button onClick={handleResetToDefaults}>
            Reset to Defaults
          </Button>
          <Button
            variant="primary"
            onClick={handleSaveSettings}
            disabled={!hasChanges}
          >
            Save
          </Button>
        </SpaceBetween>
      </Box>
    </SpaceBetween>
  );
};

export default Settings;