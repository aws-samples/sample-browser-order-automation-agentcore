import React, { useState, useEffect, useCallback } from 'react';
import {
  Header,
  SpaceBetween,
  Container,
  FormField,
  Input,
  Button,
  Alert,
  Box,
  ColumnLayout,
  Select,
  Tabs,
  Table,
  Modal,
  Form,
  TextContent,
  Badge
} from '@cloudscape-design/components';

const Settings = ({ addNotification }) => {
  // System Configuration State
  const [systemConfig, setSystemConfig] = useState({
    nova_act_api_key: '',
    agentcore_region: 'us-west-2',
    default_model: 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
    selected_browser_id: ''
  });

  // AgentCore State
  const [browsers, setBrowsers] = useState([]);
  const [browserSessions, setBrowserSessions] = useState([]);
  const [selectedBrowser, setSelectedBrowser] = useState(null);

  // Retailer State
  const [retailers, setRetailers] = useState([]);
  const [retailerConfigs, setRetailerConfigs] = useState({});
  const [newRetailer, setNewRetailer] = useState({
    id: '',
    name: '',
    base_url: '',
    description: ''
  });

  // Loading States
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadingBrowsers, setLoadingBrowsers] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [creatingBrowser, setCreatingBrowser] = useState(false);
  const [loadingRetailers, setLoadingRetailers] = useState(false);

  // Modal States
  const [showCreateBrowserModal, setShowCreateBrowserModal] = useState(false);
  const [showRetailerModal, setShowRetailerModal] = useState(false);

  // Fetch system configuration
  const fetchSystemConfig = useCallback(async () => {
    try {
      const response = await fetch('/api/config/system');
      const data = await response.json();

      setSystemConfig(prev => ({
        ...prev,
        ...data.system
      }));

      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch system config:', error);
      addNotification({
        type: 'error',
        header: 'Failed to load system configuration',
        content: error.message
      });
      setLoading(false);
    }
  }, [addNotification]);

  // Fetch retailers
  const fetchRetailers = useCallback(async () => {
    setLoadingRetailers(true);
    try {
      const response = await fetch('/api/config/retailers');
      const data = await response.json();

      setRetailers(data.supported_retailers || []);
      setRetailerConfigs(data.retailer_configs || {});

    } catch (error) {
      console.error('Failed to fetch retailers:', error);
      addNotification({
        type: 'error',
        header: 'Failed to load retailers',
        content: error.message
      });
    } finally {
      setLoadingRetailers(false);
    }
  }, [addNotification]);

  // Fetch browser sessions
  const fetchBrowserSessions = useCallback(async (browserId) => {
    if (!browserId) return;

    setLoadingSessions(true);
    try {
      const response = await fetch(`/api/agentcore/browsers/${browserId}/sessions`);
      const data = await response.json();

      setBrowserSessions(data.sessions || []);

    } catch (error) {
      console.error('Failed to fetch browser sessions:', error);
      addNotification({
        type: 'error',
        header: 'Failed to load browser sessions',
        content: error.message
      });
    } finally {
      setLoadingSessions(false);
    }
  }, [addNotification]);

  // Fetch AgentCore browsers
  const fetchBrowsers = useCallback(async () => {
    setLoadingBrowsers(true);
    try {
      const response = await fetch(`/api/agentcore/browsers?region=${systemConfig.agentcore_region}`);
      const data = await response.json();

      setBrowsers(data.browsers || []);

      // If a browser is selected, fetch its sessions
      if (systemConfig.selected_browser_id) {
        const browser = data.browsers?.find(b => b.browser_id === systemConfig.selected_browser_id);
        if (browser) {
          setSelectedBrowser(browser);
          await fetchBrowserSessions(browser.browser_id);
        }
      }

    } catch (error) {
      console.error('Failed to fetch browsers:', error);
      addNotification({
        type: 'error',
        header: 'Failed to load browsers',
        content: error.message
      });
    } finally {
      setLoadingBrowsers(false);
    }
  }, [systemConfig.agentcore_region, systemConfig.selected_browser_id, fetchBrowserSessions, addNotification]);

  // Create browser
  const createBrowser = async (browserConfig) => {
    setCreatingBrowser(true);
    try {
      const response = await fetch('/api/agentcore/browsers', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          region: systemConfig.agentcore_region,
          ...browserConfig
        })
      });

      const browser = await response.json();

      addNotification({
        type: 'success',
        header: 'Browser created successfully',
        content: `Browser ${browser.name} has been created`
      });

      setShowCreateBrowserModal(false);
      await fetchBrowsers();

    } catch (error) {
      console.error('Failed to create browser:', error);
      addNotification({
        type: 'error',
        header: 'Failed to create browser',
        content: error.message
      });
    } finally {
      setCreatingBrowser(false);
    }
  };

  // Delete browser
  const deleteBrowser = async (browserId) => {
    try {
      await fetch(`/api/agentcore/browsers/${browserId}`, {
        method: 'DELETE'
      });

      addNotification({
        type: 'success',
        header: 'Browser deleted',
        content: 'Browser has been deleted successfully'
      });

      await fetchBrowsers();

    } catch (error) {
      console.error('Failed to delete browser:', error);
      addNotification({
        type: 'error',
        header: 'Failed to delete browser',
        content: error.message
      });
    }
  };

  // Create session
  const createSession = async (browserId) => {
    try {
      const response = await fetch(`/api/agentcore/browsers/${browserId}/sessions`, {
        method: 'POST'
      });

      const session = await response.json();

      addNotification({
        type: 'success',
        header: 'Session created',
        content: `Session ${session.session_id} has been created`
      });

      await fetchBrowserSessions(browserId);

    } catch (error) {
      console.error('Failed to create session:', error);
      addNotification({
        type: 'error',
        header: 'Failed to create session',
        content: error.message
      });
    }
  };

  // Delete session
  const deleteSession = async (sessionId) => {
    try {
      await fetch(`/api/agentcore/sessions/${sessionId}`, {
        method: 'DELETE'
      });

      addNotification({
        type: 'success',
        header: 'Session deleted',
        content: 'Session has been deleted successfully'
      });

      if (selectedBrowser) {
        await fetchBrowserSessions(selectedBrowser.browser_id);
      }

    } catch (error) {
      console.error('Failed to delete session:', error);
      addNotification({
        type: 'error',
        header: 'Failed to delete session',
        content: error.message
      });
    }
  };

  // Save system settings
  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await fetch('/api/config/system', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          config_key: 'system_settings',
          config_value: systemConfig
        })
      });

      addNotification({
        type: 'success',
        header: 'Settings saved',
        content: 'System settings have been updated successfully'
      });

    } catch (error) {
      console.error('Failed to save settings:', error);
      addNotification({
        type: 'error',
        header: 'Failed to save settings',
        content: error.message
      });
    } finally {
      setSaving(false);
    }
  };

  // Add new retailer
  const addRetailer = async () => {
    try {
      const response = await fetch('/api/config/retailers', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newRetailer)
      });

      if (response.ok) {
        addNotification({
          type: 'success',
          header: 'Retailer added',
          content: `${newRetailer.name} has been added successfully`
        });

        setNewRetailer({ id: '', name: '', base_url: '', description: '' });
        setShowRetailerModal(false);
        await fetchRetailers();
      }
    } catch (error) {
      console.error('Failed to add retailer:', error);
      addNotification({
        type: 'error',
        header: 'Failed to add retailer',
        content: error.message
      });
    }
  };

  // Delete retailer
  const deleteRetailer = async (retailerId) => {
    try {
      await fetch(`/api/config/retailers/${retailerId}`, {
        method: 'DELETE'
      });

      addNotification({
        type: 'success',
        header: 'Retailer deleted',
        content: 'Retailer has been removed successfully'
      });

      await fetchRetailers();
    } catch (error) {
      console.error('Failed to delete retailer:', error);
      addNotification({
        type: 'error',
        header: 'Failed to delete retailer',
        content: error.message
      });
    }
  };

  // Initialize data
  useEffect(() => {
    fetchSystemConfig();
    fetchRetailers();
  }, [fetchSystemConfig, fetchRetailers]);

  useEffect(() => {
    if (!loading && systemConfig.agentcore_region) {
      fetchBrowsers();
    }
  }, [loading, systemConfig.agentcore_region, fetchBrowsers]);

  // Set default browser if none selected
  useEffect(() => {
    if (browsers.length > 0 && !systemConfig.selected_browser_id) {
      const defaultBrowser = browsers[0];
      setSelectedBrowser(defaultBrowser);
      setSystemConfig(prev => ({
        ...prev,
        selected_browser_id: defaultBrowser.browser_id
      }));
    }
  }, [browsers, systemConfig.selected_browser_id]);

  // Browser table columns
  const browserColumns = [
    {
      id: 'browser_id',
      header: 'Browser ID',
      cell: item => item.browser_id,
      sortingField: 'browser_id'
    },
    {
      id: 'name',
      header: 'Name',
      cell: item => (
        <SpaceBetween direction="horizontal" size="xs">
          <span>{item.name}</span>
          {item.managed_by && (
            <Badge color="blue">{item.managed_by} Managed</Badge>
          )}
        </SpaceBetween>
      ),
      sortingField: 'name'
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => (
        <Badge color={item.status === 'READY' ? 'green' : 'grey'}>
          {item.status}
        </Badge>
      ),
      sortingField: 'status'
    },
    {
      id: 'description',
      header: 'Description',
      cell: item => item.description || 'No description'
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: item => (
        <SpaceBetween direction="horizontal" size="xs">
          <Button
            size="small"
            onClick={async () => {
              setSelectedBrowser(item);
              setSystemConfig(prev => ({
                ...prev,
                selected_browser_id: item.browser_id
              }));
              await fetchBrowserSessions(item.browser_id);
            }}
          >
            Select as Default
          </Button>
          {!item.managed_by && (
            <Button
              size="small"
              variant="normal"
              onClick={() => deleteBrowser(item.browser_id)}
            >
              Delete
            </Button>
          )}
        </SpaceBetween>
      )
    }
  ];

  // Session table columns
  const sessionColumns = [
    {
      id: 'session_id',
      header: 'Session ID',
      cell: item => item.session_id,
      sortingField: 'session_id'
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => (
        <Badge color={item.status === 'ACTIVE' ? 'green' : 'grey'}>
          {item.status}
        </Badge>
      ),
      sortingField: 'status'
    },
    {
      id: 'created_at',
      header: 'Created',
      cell: item => new Date(item.created_at).toLocaleString(),
      sortingField: 'created_at'
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: item => (
        <SpaceBetween direction="horizontal" size="xs">
          <Button
            size="small"
            onClick={() => {
              // Sessions are now read-only for viewing purposes
              addNotification({
                type: 'info',
                header: 'Session Information',
                content: `Session ${item.session_id} is active. Sessions are automatically managed by agents.`
              });
            }}
          >
            View
          </Button>
          <Button
            size="small"
            variant="normal"
            onClick={() => deleteSession(item.session_id)}
          >
            Delete
          </Button>
        </SpaceBetween>
      )
    }
  ];

  // Retailer table columns
  const retailerColumns = [
    {
      id: 'id',
      header: 'ID',
      cell: item => item,
      sortingField: 'id'
    },
    {
      id: 'name',
      header: 'Name',
      cell: item => retailerConfigs[item]?.name || item,
      sortingField: 'name'
    },
    {
      id: 'base_url',
      header: 'Base URL',
      cell: item => (
        <a href={retailerConfigs[item]?.base_url} target="_blank" rel="noopener noreferrer">
          {retailerConfigs[item]?.base_url}
        </a>
      )
    },
    {
      id: 'description',
      header: 'Description',
      cell: item => retailerConfigs[item]?.description || 'No description'
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => (
        <Badge color={retailerConfigs[item]?.status === 'active' ? 'green' : 'grey'}>
          {retailerConfigs[item]?.status || 'active'}
        </Badge>
      )
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: item => (
        <SpaceBetween direction="horizontal" size="xs">
          <Button
            size="small"
            variant="normal"
            onClick={() => deleteRetailer(item)}
          >
            Delete
          </Button>
        </SpaceBetween>
      )
    }
  ];

  if (loading) {
    return <Box>Loading settings...</Box>;
  }

  const tabs = [
    {
      label: 'System Settings',
      id: 'system',
      content: (
        <Container>
          <Form
            actions={
              <Box float="right">
                <SpaceBetween direction="horizontal" size="xs">
                  <Button
                    variant="primary"
                    loading={saving}
                    onClick={handleSaveSettings}
                  >
                    Save Settings
                  </Button>
                </SpaceBetween>
              </Box>
            }
          >
            <SpaceBetween size="l">
              <FormField
                label="Nova Act API Key"
                description="API key for Nova Act automation service"
              >
                <Input
                  value={systemConfig.nova_act_api_key || ''}
                  onChange={({ detail }) =>
                    setSystemConfig(prev => ({ ...prev, nova_act_api_key: detail.value }))
                  }
                  placeholder="Enter your Nova Act API key"
                  type="password"
                />
              </FormField>

              <ColumnLayout columns={2}>
                <FormField
                  label="AgentCore Region"
                  description="AWS region for AgentCore Browser service"
                >
                  <Select
                    selectedOption={{
                      label: systemConfig.agentcore_region || 'us-west-2',
                      value: systemConfig.agentcore_region || 'us-west-2'
                    }}
                    onChange={({ detail }) => {
                      setSystemConfig(prev => ({ ...prev, agentcore_region: detail.selectedOption.value }));
                      // Refresh browsers when region changes
                      fetchBrowsers();
                    }}
                    options={[
                      { label: 'us-west-2', value: 'us-west-2' },
                      { label: 'us-east-1', value: 'us-east-1' },
                      { label: 'eu-west-1', value: 'eu-west-1' },
                      { label: 'ap-southeast-1', value: 'ap-southeast-1' }
                    ]}
                  />
                </FormField>

                <FormField
                  label="Default Model"
                  description="Default AI model for automation"
                >
                  <Select
                    selectedOption={{
                      label: systemConfig.default_model === 'us.anthropic.claude-sonnet-4-20250514-v1:0' ? 'Claude Sonnet 4' :
                             systemConfig.default_model === 'us.anthropic.claude-3-7-sonnet-20250219-v1:0' ? 'Claude 3.7 Sonnet' :
                             systemConfig.default_model === 'us.amazon.nova-pro-v1:0' ? 'Amazon Nova Pro' :
                             systemConfig.default_model === 'openai.gpt-oss-20b-1:0' ? 'GPT-OSS 20B' :
                             systemConfig.default_model === 'openai.gpt-oss-120b-1:0' ? 'GPT-OSS 120B' : 'Claude 3.7 Sonnet',
                      value: systemConfig.default_model || 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
                    }}
                    onChange={({ detail }) =>
                      setSystemConfig(prev => ({ ...prev, default_model: detail.selectedOption.value }))
                    }
                    options={[
                      { label: 'Claude Sonnet 4', value: 'us.anthropic.claude-sonnet-4-20250514-v1:0' },
                      { label: 'Claude 3.7 Sonnet', value: 'us.anthropic.claude-3-7-sonnet-20250219-v1:0' },
                      { label: 'Amazon Nova Pro', value: 'us.amazon.nova-pro-v1:0' },
                      { label: 'GPT-OSS 20B', value: 'openai.gpt-oss-20b-1:0' },
                      { label: 'GPT-OSS 120B', value: 'openai.gpt-oss-120b-1:0' }
                    ]}
                  />
                </FormField>
              </ColumnLayout>

              <FormField
                label="Default Browser"
                description="Default AgentCore Browser for agent spawning (AWS managed)"
              >
                <Select
                  selectedOption={
                    systemConfig.selected_browser_id
                      ? browsers.find(b => b.browser_id === systemConfig.selected_browser_id) 
                        ? { 
                            label: `${browsers.find(b => b.browser_id === systemConfig.selected_browser_id).name} (AWS Managed)`, 
                            value: systemConfig.selected_browser_id 
                          }
                        : { label: systemConfig.selected_browser_id, value: systemConfig.selected_browser_id }
                      : browsers.length > 0 
                        ? { 
                            label: `${browsers[0].name} (AWS Managed)`, 
                            value: browsers[0].browser_id 
                          }
                        : null
                  }
                  onChange={async ({ detail }) => {
                    const browser = browsers.find(b => b.browser_id === detail.selectedOption.value);
                    setSelectedBrowser(browser);
                    setSystemConfig(prev => ({ ...prev, selected_browser_id: detail.selectedOption.value }));
                    await fetchBrowserSessions(detail.selectedOption.value);
                  }}
                  options={browsers.map(browser => ({
                    label: `${browser.name} (${browser.managed_by || 'AWS'} Managed)`,
                    value: browser.browser_id
                  }))}
                  placeholder="AWS AgentCore Browser Tool"
                  empty="AWS AgentCore Browser Tool will be used"
                />
              </FormField>

              <Alert type="info">
                <TextContent>
                  <p><strong>AWS AgentCore Browser Tool:</strong> Using AWS managed browser sandbox (aws.browser.v1) for secure web browsing.</p>
                  <p><strong>Session Management:</strong> Sessions are automatically created when agents are spawned. Each agent gets its own dedicated session.</p>
                  <p><strong>ARN:</strong> arn:aws:bedrock-agentcore:us-west-2:aws:browser/aws.browser.v1</p>
                </TextContent>
              </Alert>
            </SpaceBetween>
          </Form>
        </Container>
      )
    },
    {
      label: 'AgentCore Browsers',
      id: 'browsers',
      content: (
        <SpaceBetween size="l">
          <Container
            header={
              <Header
                variant="h2"
                actions={
                  <SpaceBetween direction="horizontal" size="xs">
                    <Button
                      onClick={fetchBrowsers}
                      loading={loadingBrowsers}
                    >
                      Refresh
                    </Button>
                    <Button
                      variant="primary"
                      onClick={() => setShowCreateBrowserModal(true)}
                    >
                      View Details
                    </Button>
                  </SpaceBetween>
                }
              >
                AgentCore Browsers
              </Header>
            }
          >
            <Table
              columnDefinitions={browserColumns}
              items={browsers}
              loading={loadingBrowsers}
              loadingText="Loading browsers..."
              empty={
                <Box textAlign="center" color="inherit">
                  <b>No browsers found</b>
                  <Box padding={{ bottom: 's' }} variant="p" color="inherit">
                    Create your first browser to get started.
                  </Box>
                  <Button onClick={() => setShowCreateBrowserModal(true)}>
                    View AWS Browser Tool
                  </Button>
                </Box>
              }
            />
          </Container>

          {selectedBrowser && (
            <Container
              header={
                <Header
                  variant="h3"
                  actions={
                    <Button
                      variant="primary"
                      onClick={() => createSession(selectedBrowser.browser_id)}
                    >
                      Create Session
                    </Button>
                  }
                >
                  Sessions for {selectedBrowser.name}
                </Header>
              }
            >
              <Table
                columnDefinitions={sessionColumns}
                items={browserSessions}
                loading={loadingSessions}
                loadingText="Loading sessions..."
                empty={
                  <Box textAlign="center" color="inherit">
                    <b>No sessions found</b>
                    <Box padding={{ bottom: 's' }} variant="p" color="inherit">
                      Create a session for this browser.
                    </Box>
                    <Button onClick={() => createSession(selectedBrowser.browser_id)}>
                      Create Session
                    </Button>
                  </Box>
                }
              />
            </Container>
          )}
        </SpaceBetween>
      )
    },
    {
      label: 'Retailer Configuration',
      id: 'retailers',
      content: (
        <Container
          header={
            <Header
              variant="h2"
              actions={
                <SpaceBetween direction="horizontal" size="xs">
                  <Button
                    onClick={fetchRetailers}
                    loading={loadingRetailers}
                  >
                    Refresh
                  </Button>
                  <Button
                    variant="primary"
                    onClick={() => setShowRetailerModal(true)}
                  >
                    Add Retailer
                  </Button>
                </SpaceBetween>
              }
            >
              Retailer Management
            </Header>
          }
        >
          <SpaceBetween size="l">
            <Alert type="info">
              <TextContent>
                <p>Configure supported retailers for order automation. Each retailer requires a name, base URL, and description.</p>
                <p>Currently supported retailers: <strong>{retailers.length}</strong></p>
              </TextContent>
            </Alert>

            <Table
              columnDefinitions={retailerColumns}
              items={retailers}
              loading={loadingRetailers}
              loadingText="Loading retailers..."
              empty={
                <Box textAlign="center" color="inherit">
                  <b>No retailers configured</b>
                  <Box padding={{ bottom: 's' }} variant="p" color="inherit">
                    Add your first retailer to get started with order automation.
                  </Box>
                  <Button onClick={() => setShowRetailerModal(true)}>
                    Add Retailer
                  </Button>
                </Box>
              }
              header={
                <Header
                  counter={`(${retailers.length})`}
                  description="Manage supported retailers for order automation"
                >
                  Configured Retailers
                </Header>
              }
            />
          </SpaceBetween>
        </Container>
      )
    }
  ];

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Configure system settings, AgentCore browsers, and retailer configurations"
      >
        Settings
      </Header>

      <Tabs tabs={tabs} />

      {/* Create Browser Modal */}
      <Modal
        onDismiss={() => setShowCreateBrowserModal(false)}
        visible={showCreateBrowserModal}
        closeAriaLabel="Close modal"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button
                variant="link"
                onClick={() => setShowCreateBrowserModal(false)}
              >
                Close
              </Button>
            </SpaceBetween>
          </Box>
        }
        header="AWS AgentCore Browser Tool"
      >
        <SpaceBetween size="l">
          <Alert type="info">
            <TextContent>
              <p><strong>AWS Managed Resource</strong></p>
              <p>The AgentCore Browser Tool is created and managed by Amazon. It cannot be edited or deleted.</p>
            </TextContent>
          </Alert>
          
          <Box>
            <p><strong>Tool Details:</strong></p>
            <ul>
              <li><strong>Name:</strong> AgentCore Browser Tool</li>
              <li><strong>Description:</strong> AWS built-in browser sandbox for secure web browsing</li>
              <li><strong>Tool ID:</strong> aws.browser.v1</li>
              <li><strong>ARN:</strong> arn:aws:bedrock-agentcore:{systemConfig.agentcore_region}:aws:browser/aws.browser.v1</li>
              <li><strong>Status:</strong> Ready</li>
              <li><strong>Region:</strong> {systemConfig.agentcore_region}</li>
            </ul>
          </Box>
          
          <Box>
            <p><strong>Features:</strong></p>
            <ul>
              <li>Secure browser sandbox environment</li>
              <li>Automatic session management</li>
              <li>WebSocket-based CDP connection</li>
              <li>Built-in security and isolation</li>
            </ul>
          </Box>
        </SpaceBetween>
      </Modal>

      {/* Add Retailer Modal */}
      <Modal
        onDismiss={() => setShowRetailerModal(false)}
        visible={showRetailerModal}
        closeAriaLabel="Close modal"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button
                variant="link"
                onClick={() => setShowRetailerModal(false)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={addRetailer}
                disabled={!newRetailer.id || !newRetailer.name || !newRetailer.base_url}
              >
                Add Retailer
              </Button>
            </SpaceBetween>
          </Box>
        }
        header="Add New Retailer"
      >
        <Form>
          <SpaceBetween size="l">
            <FormField
              label="Retailer ID"
              description="Unique identifier for the retailer (lowercase, no spaces)"
            >
              <Input
                value={newRetailer.id}
                onChange={({ detail }) =>
                  setNewRetailer(prev => ({ ...prev, id: detail.value.toLowerCase().replace(/\s+/g, '_') }))
                }
                placeholder="e.g., amazon, nike, gucci"
              />
            </FormField>

            <FormField
              label="Retailer Name"
              description="Display name for the retailer"
            >
              <Input
                value={newRetailer.name}
                onChange={({ detail }) =>
                  setNewRetailer(prev => ({ ...prev, name: detail.value }))
                }
                placeholder="e.g., Amazon, Nike, Gucci"
              />
            </FormField>

            <FormField
              label="Base URL"
              description="Main website URL for the retailer"
            >
              <Input
                value={newRetailer.base_url}
                onChange={({ detail }) =>
                  setNewRetailer(prev => ({ ...prev, base_url: detail.value }))
                }
                placeholder="https://www.example.com"
                type="url"
              />
            </FormField>

            <FormField
              label="Description"
              description="Brief description of the retailer"
            >
              <Input
                value={newRetailer.description}
                onChange={({ detail }) =>
                  setNewRetailer(prev => ({ ...prev, description: detail.value }))
                }
                placeholder="Brief description of the retailer and products"
              />
            </FormField>
          </SpaceBetween>
        </Form>
      </Modal>
    </SpaceBetween>
  );
};

export default Settings;