# Product Requirements Document: Joplin MCP (Model Context Protocol)

## Introduction/Overview

The Joplin MCP is a Python-based implementation of the Model Context Protocol that enables AI assistants and developers to interact with Joplin note-taking application data through its REST API. This MCP will automate note-taking workflows by providing seamless integration between AI systems and Joplin's comprehensive note management capabilities, allowing for intelligent note searching, summarization, and automated note creation.

The primary problem this feature solves is the disconnect between AI assistants and personal knowledge management systems, enabling researchers and knowledge workers to leverage AI for enhanced productivity within their existing Joplin workflows.

## Goals

1. **Enable AI-Joplin Integration**: Provide a standardized MCP interface for AI assistants to interact with Joplin data
2. **Automate Research Workflows**: Allow researchers to search, summarize, and create notes through AI assistance
3. **Ensure Ease of Integration**: Create a plug-and-play solution that developers can easily incorporate into their AI applications
4. **Maintain Data Integrity**: Provide reliable CRUD operations while preserving Joplin's data structure and relationships
5. **Support Comprehensive Operations**: Cover all essential Joplin API endpoints for a complete integration experience

## User Stories

1. **As a researcher**, I want to ask my AI assistant to search my Joplin notes for relevant information so that I can quickly find and summarize the most relevant parts without manually browsing through hundreds of notes.

2. **As a knowledge worker**, I want to instruct my AI assistant to create new notes in Joplin based on my verbal or text instructions so that I can capture ideas and information without interrupting my workflow.

3. **As a developer**, I want to integrate Joplin functionality into my AI application using a standardized MCP interface so that I can build powerful knowledge management features without learning the Joplin API directly.

4. **As a content creator**, I want my AI assistant to organize my research notes by tags and notebooks so that my knowledge base remains structured and searchable.

5. **As a student**, I want to ask my AI assistant to summarize notes from specific notebooks or with certain tags so that I can quickly review material for exams or projects.

## Functional Requirements

### Core MVP Requirements

1. **Connection Management**: The system must automatically discover and connect to the Joplin clipper server (ports 41184-41194) and handle authentication using user-provided tokens.

2. **Note Search**: The system must provide full-text search capabilities across all notes, supporting Joplin's search syntax and returning relevant results with metadata.

3. **Note Reading**: The system must allow reading individual notes by ID, returning title, body (markdown), creation/modification dates, parent notebook, and associated tags.

4. **Note Creation**: The system must enable creation of new notes with title, markdown body, optional parent notebook assignment, and optional tag associations.

5. **Note Updates**: The system must support updating existing notes including title, body, notebook assignment, and tag associations.

6. **Note Deletion**: The system must provide safe deletion of notes with appropriate confirmation mechanisms.

### Extended MVP Requirements

7. **Notebook Management**: The system must allow listing, reading, creating, and organizing notebooks (folders) to maintain proper note organization.

8. **Tag Management**: The system must support listing, creating, and managing tags, including associating/disassociating tags with notes.

9. **Search by Type**: The system must support searching for notebooks and tags using wildcard patterns (e.g., "project-*" for all project tags).

10. **Pagination Support**: The system must handle paginated responses for large datasets, providing options for page size, sorting, and navigation.

11. **Connection Testing**: The system must provide a ping/health check mechanism to verify Joplin server availability and authentication status.

12. **Error Handling**: The system must provide comprehensive error handling with descriptive messages for common scenarios (server unavailable, invalid token, missing resources).

## Non-Goals (Out of Scope)

1. **Resource/Attachment Management**: File uploads and attachment handling will not be included in the MVP (can be added in future versions).

2. **Advanced Markdown Processing**: No markdown-to-HTML conversion or advanced formatting will be provided - raw markdown content will be returned.

3. **Joplin Installation/Setup**: The MCP will not handle Joplin application installation or initial configuration.

4. **Multi-User Support**: Single-user operation only - no multi-tenant or user management features.

5. **Offline Synchronization**: No offline caching or sync conflict resolution - requires active Joplin server connection.

6. **Custom Plugin Development**: The MCP will not provide frameworks for developing custom Joplin plugins.

## Design Considerations

- **MCP Compliance**: Must strictly follow the official Model Context Protocol specification for tool definitions, error handling, and response formats.
- **Pythonic Design**: Use modern Python practices with type hints, async/await patterns, and proper exception handling.
- **Configuration Management**: Support both environment variables and configuration files for server discovery and authentication.
- **Logging**: Implement comprehensive logging for debugging and monitoring integration issues.
- **Documentation**: Provide clear examples and integration guides for both developers and end-users.

## Technical Considerations

- **Dependencies**: Utilize the official MCP Python SDK and standard HTTP libraries (httpx/requests) for API communication.
- **Authentication**: Securely handle Joplin API tokens with proper storage and transmission practices.
- **Server Discovery**: Implement the port-scanning algorithm described in Joplin documentation for automatic server detection.
- **Rate Limiting**: Consider implementing rate limiting to prevent overwhelming the Joplin server.
- **Testing**: Include comprehensive unit tests and integration tests with mock Joplin server responses.
- **Async Support**: Design with async/await patterns to support concurrent operations and better performance.

## Success Metrics

1. **Ease of Integration**: Developers can integrate the MCP into their applications with less than 10 lines of configuration code.

2. **API Coverage**: Successfully implements 100% of planned MVP endpoints (notes, notebooks, tags, search).

3. **Reliability**: 99%+ success rate for valid API operations under normal conditions.

4. **Performance**: Average response time under 500ms for typical operations (single note read, search with <100 results).

5. **Developer Experience**: Clear documentation and examples that enable integration without referring to Joplin API documentation.

6. **Error Handling**: Provides actionable error messages for all common failure scenarios.

## Open Questions

1. **Token Management**: Should the MCP provide mechanisms for token refresh or validation, or rely on manual token management?

2. **Batch Operations**: Would batch note creation/update operations provide significant value for the MVP?

3. **Search Result Formatting**: Should search results include snippet previews or just metadata?

4. **Notebook Hierarchy**: How should nested notebook structures be represented in MCP responses?

5. **Configuration Storage**: What's the preferred method for storing server connection details and tokens (environment variables, config files, or both)?

6. **Deployment**: Should the MCP include Docker containerization or installation scripts for easier deployment? 