## ADDED Requirements

### Requirement: MCP runtime is hosted by backend deployment
The system SHALL host MCP protocol endpoints from the backend deployment runtime and SHALL NOT require a dedicated MCP application container for standard Docker deployment.

#### Scenario: Compose application startup
- **GIVEN** the standard application deployment is started with Docker Compose
- **WHEN** the application services become healthy
- **THEN** the deployment starts the backend container without starting a separate `stock-mcp` application container
- **AND** MCP protocol requests are served by an MCP server process running inside the backend container

#### Scenario: Backend container hosts two service processes
- **GIVEN** the backend deployment is running
- **WHEN** an operator inspects the backend container
- **THEN** the container hosts both the main backend API process and the MCP server process
- **AND** the two processes listen on their respective service ports

### Requirement: Embedded MCP endpoints remain protocol-compatible
The system SHALL preserve MCP protocol compatibility after embedding MCP into the backend runtime.

#### Scenario: Streamable HTTP MCP client connects
- **GIVEN** an MCP client sends `initialize` and subsequent tool requests to the configured `/messages` endpoint
- **WHEN** the backend runtime handles the MCP request
- **THEN** the system returns valid MCP streamable HTTP protocol responses
- **AND** tool listing and tool execution continue to work without a dedicated MCP container

#### Scenario: Legacy endpoint configuration is normalized
- **GIVEN** an internal or external MCP client is still configured with a legacy endpoint path such as `/mcp`
- **WHEN** the client is initialized
- **THEN** the system resolves the configuration to the embedded MCP streamable HTTP endpoint without requiring a separate MCP service hostname

### Requirement: Backend MCP fallback uses embedded endpoint
The system SHALL route backend-originated MCP fallback requests to the backend-hosted MCP endpoint.

#### Scenario: Orchestrator falls back to MCP tools
- **GIVEN** no suitable Agent is available for a chat request
- **WHEN** the orchestrator falls back to MCP tool execution
- **THEN** it connects to the MCP endpoint hosted by the backend runtime
- **AND** it does not depend on a separate `stock-mcp` container hostname