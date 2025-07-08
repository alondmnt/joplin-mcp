# Joplin MCP Server API Documentation

This document provides comprehensive API documentation for all 18 MCP tools available in the Joplin MCP Server.

## Table of Contents

- [Note Management](#note-management)
  - [search_notes](#search_notes)
  - [get_note](#get_note)
  - [create_note](#create_note)
  - [update_note](#update_note)
  - [delete_note](#delete_note)
- [Notebook Management](#notebook-management)
  - [list_notebooks](#list_notebooks)
  - [get_notebook](#get_notebook)
  - [create_notebook](#create_notebook)
- [Tag Management](#tag-management)
  - [list_tags](#list_tags)
  - [create_tag](#create_tag)
  - [tag_note](#tag_note)
  - [untag_note](#untag_note)
- [System Tools](#system-tools)
  - [ping_joplin](#ping_joplin)
- [Error Handling](#error-handling)
- [Response Format](#response-format)

---

## Note Management

### search_notes

Search for notes using full-text query with advanced filtering options.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | ✅ | - | Search query for full-text search across notes |
| `limit` | integer | ❌ | 20 | Maximum number of results to return (1-100) |
| `notebook_id` | string | ❌ | - | Optional notebook ID to limit search scope |
| `tags` | array[string] | ❌ | - | Optional list of tags to filter notes |
| `sort_by` | string | ❌ | "updated_time" | Field to sort results by |
| `sort_order` | string | ❌ | "desc" | Sort order for results |

#### Valid Values

- **sort_by**: `"title"`, `"created_time"`, `"updated_time"`, `"relevance"`
- **sort_order**: `"asc"`, `"desc"`

#### Example Request

```json
{
  "query": "meeting notes",
  "limit": 10,
  "notebook_id": "abc123def456",
  "tags": ["important", "work"],
  "sort_by": "updated_time",
  "sort_order": "desc"
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "Found 3 note(s) for query: \"meeting notes\"\n\n📝 **Weekly Team Meeting**\n**ID:** note_789xyz\n**Notebook:** Work Projects\n**Created:** 2024-01-15 14:30\n**Updated:** 2024-01-15 16:45\n**Tags:** important, work, weekly\n**Preview:** Discussed project milestones and upcoming deadlines...\n\n📝 **Client Meeting Notes**\n**ID:** note_456abc\n**Notebook:** Client Relations\n**Created:** 2024-01-12 10:00\n**Updated:** 2024-01-12 11:30\n**Tags:** important, client\n**Preview:** Key points from client discussion about requirements...\n\n📝 **Project Kickoff Meeting**\n**ID:** note_123def\n**Notebook:** Work Projects\n**Created:** 2024-01-10 09:00\n**Updated:** 2024-01-10 10:15\n**Tags:** work, project\n**Preview:** Initial project planning and team assignments..."
  }]
}
```

---

### get_note

Retrieve a specific note by its ID with full content and metadata.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `note_id` | string | ✅ | - | Unique identifier of the note to retrieve |
| `include_body` | boolean | ❌ | true | Whether to include the note body in the response |

#### Example Request

```json
{
  "note_id": "note_789xyz",
  "include_body": true
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "📝 **Weekly Team Meeting**\n\n**Note ID:** note_789xyz\n**Notebook:** Work Projects (notebook_456)\n**Created:** January 15, 2024 at 2:30 PM\n**Updated:** January 15, 2024 at 4:45 PM\n**Tags:** important, work, weekly\n\n---\n\n# Weekly Team Meeting - January 15, 2024\n\n## Attendees\n- Alice Johnson (Project Manager)\n- Bob Smith (Developer)\n- Carol Davis (Designer)\n\n## Agenda Items\n\n### 1. Project Status Update\n- Backend API development: 80% complete\n- Frontend implementation: 60% complete\n- Testing phase: Starting next week\n\n### 2. Upcoming Deadlines\n- Feature freeze: January 22, 2024\n- Beta release: January 29, 2024\n- Production release: February 5, 2024\n\n### 3. Action Items\n- [ ] Bob: Complete user authentication module\n- [ ] Carol: Finalize UI mockups for dashboard\n- [ ] Alice: Schedule client demo for January 25\n\n## Next Meeting\nJanuary 22, 2024 at 2:00 PM"
  }]
}
```

---

### create_note

Create a new note with support for todos, tags, and notebook assignment.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `title` | string | ✅ | - | Title of the new note |
| `parent_id` | string | ✅ | - | ID of the parent notebook where the note will be created |
| `body` | string | ❌ | "" | Content body of the note |
| `is_todo` | boolean | ❌ | false | Whether this note is a todo item |
| `todo_completed` | boolean | ❌ | false | Whether the todo item is completed |
| `tags` | array[string] | ❌ | - | List of tags to assign to the note |

#### Example Request

```json
{
  "title": "Project Documentation",
  "parent_id": "notebook_456",
  "body": "# Project Documentation\n\n## Overview\nThis document outlines the project requirements and specifications.\n\n## Requirements\n- User authentication\n- Data visualization\n- Export functionality",
  "is_todo": false,
  "tags": ["documentation", "project", "important"]
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "✅ Successfully created note\n\n**Title:** Project Documentation\n**Note ID:** note_new123\n**Notebook:** Work Projects (notebook_456)\n**Type:** 📝 Regular Note\n**Tags:** documentation, project, important\n\nThe note has been successfully created in Joplin and is ready for use."
  }]
}
```

#### Todo Note Example

```json
{
  "title": "Complete API documentation",
  "parent_id": "notebook_456",
  "body": "Write comprehensive API documentation for all endpoints",
  "is_todo": true,
  "todo_completed": false,
  "tags": ["urgent", "documentation"]
}
```

#### Todo Response

```json
{
  "content": [{
    "type": "text",
    "text": "✅ Successfully created todo note\n\n**Title:** Complete API documentation\n**Note ID:** todo_new456\n**Notebook:** Work Projects (notebook_456)\n**Type:** ✅ Todo Item\n**Todo Status:** 📝 Pending\n**Tags:** urgent, documentation\n\nThe todo note has been successfully created in Joplin and is ready for tracking."
  }]
}
```

---

### update_note

Update an existing note with flexible parameter support.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `note_id` | string | ✅ | - | ID of the note to update |
| `title` | string | ❌ | - | New title for the note |
| `body` | string | ❌ | - | New content body for the note |
| `is_todo` | boolean | ❌ | - | Convert to/from todo item |
| `todo_completed` | boolean | ❌ | - | Update todo completion status |
| `tags` | array[string] | ❌ | - | Replace existing tags with new ones |

#### Example Request

```json
{
  "note_id": "note_789xyz",
  "title": "Weekly Team Meeting - Updated",
  "body": "# Weekly Team Meeting - January 15, 2024 (Updated)\n\n## Additional Notes\n- Project timeline adjusted\n- New team member joining next week",
  "tags": ["important", "work", "weekly", "updated"]
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "✅ Successfully updated note\n\n**Note ID:** note_789xyz\n\nThe note has been successfully updated in Joplin."
  }]
}
```

---

### delete_note

Delete a note from Joplin with confirmation.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `note_id` | string | ✅ | - | ID of the note to delete |

#### Example Request

```json
{
  "note_id": "note_789xyz"
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "✅ Successfully deleted note\n\n**Note ID:** note_789xyz\n\nThe note has been successfully deleted from Joplin."
  }]
}
```

---

## Notebook Management

### list_notebooks

List all notebooks with hierarchical structure and metadata.

#### Parameters

No parameters required.

#### Example Request

```json
{}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "📁 **All Notebooks** (3 total)\n\n📁 **Work Projects**\n**ID:** notebook_456\n**Created:** January 1, 2024 at 9:00 AM\n**Updated:** January 15, 2024 at 4:45 PM\n**Notes:** 15 notes\n\n📁 **Personal**\n**ID:** notebook_789\n**Created:** December 15, 2023 at 2:30 PM\n**Updated:** January 10, 2024 at 6:20 PM\n**Notes:** 8 notes\n\n📁 **Research**\n**ID:** notebook_123\n**Created:** November 20, 2023 at 11:15 AM\n**Updated:** January 5, 2024 at 3:10 PM\n**Notes:** 12 notes"
  }]
}
```

---

### get_notebook

Get detailed information about a specific notebook.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `notebook_id` | string | ✅ | - | ID of the notebook to retrieve |

#### Example Request

```json
{
  "notebook_id": "notebook_456"
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "📁 **Work Projects**\n\n**Notebook ID:** notebook_456\n**Created:** January 1, 2024 at 9:00 AM\n**Updated:** January 15, 2024 at 4:45 PM\n**Parent:** None (Root notebook)\n**Notes Count:** 15 notes\n\n**Description:**\nNotebook containing all work-related projects and documentation."
  }]
}
```

---

### create_notebook

Create a new notebook with optional parent-child relationships.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `title` | string | ✅ | - | Title of the new notebook |
| `parent_id` | string | ❌ | - | ID of the parent notebook (for nested structure) |

#### Example Request

```json
{
  "title": "Client Projects",
  "parent_id": "notebook_456"
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "✅ Successfully created notebook\n\n**Title:** Client Projects\n**Notebook ID:** notebook_new789\n**Parent:** Work Projects (notebook_456)\n\nThe notebook has been successfully created in Joplin."
  }]
}
```

---

## Tag Management

### list_tags

List all available tags with usage statistics.

#### Parameters

No parameters required.

#### Example Request

```json
{}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "🏷️ **All Tags** (8 total)\n\n🏷️ **important** (ID: tag_123)\n**Created:** December 1, 2023 at 10:00 AM\n**Updated:** January 15, 2024 at 4:45 PM\n**Notes:** 12 notes tagged\n\n🏷️ **work** (ID: tag_456)\n**Created:** December 1, 2023 at 10:05 AM\n**Updated:** January 14, 2024 at 2:30 PM\n**Notes:** 18 notes tagged\n\n🏷️ **project** (ID: tag_789)\n**Created:** December 5, 2023 at 3:20 PM\n**Updated:** January 10, 2024 at 11:15 AM\n**Notes:** 8 notes tagged\n\n🏷️ **documentation** (ID: tag_abc)\n**Created:** December 10, 2023 at 9:45 AM\n**Updated:** January 8, 2024 at 4:00 PM\n**Notes:** 6 notes tagged\n\n🏷️ **urgent** (ID: tag_def)\n**Created:** January 2, 2024 at 8:30 AM\n**Updated:** January 12, 2024 at 5:15 PM\n**Notes:** 4 notes tagged\n\n🏷️ **meeting** (ID: tag_ghi)\n**Created:** January 5, 2024 at 1:20 PM\n**Updated:** January 15, 2024 at 3:45 PM\n**Notes:** 7 notes tagged\n\n🏷️ **client** (ID: tag_jkl)\n**Created:** January 8, 2024 at 11:30 AM\n**Updated:** January 13, 2024 at 2:10 PM\n**Notes:** 3 notes tagged\n\n🏷️ **research** (ID: tag_mno)\n**Created:** November 25, 2023 at 4:15 PM\n**Updated:** January 6, 2024 at 10:30 AM\n**Notes:** 9 notes tagged"
  }]
}
```

---

### create_tag

Create a new tag for organizing notes.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `title` | string | ✅ | - | Title/name of the new tag |

#### Example Request

```json
{
  "title": "quarterly-review"
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "✅ Successfully created tag\n\n**Title:** quarterly-review\n**Tag ID:** tag_new123\n\nThe tag has been successfully created in Joplin and is ready for use."
  }]
}
```

---

### tag_note

Add a tag to a note for organization and categorization.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `note_id` | string | ✅ | - | ID of the note to tag |
| `tag_id` | string | ✅ | - | ID of the tag to add |

#### Example Request

```json
{
  "note_id": "note_789xyz",
  "tag_id": "tag_123"
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "✅ Successfully added tag to note\n\n**Note ID:** note_789xyz\n**Tag ID:** tag_123\n\nThe tag has been successfully added to the note."
  }]
}
```

---

### untag_note

Remove a tag from a note.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `note_id` | string | ✅ | - | ID of the note to untag |
| `tag_id` | string | ✅ | - | ID of the tag to remove |

#### Example Request

```json
{
  "note_id": "note_789xyz",
  "tag_id": "tag_123"
}
```

#### Example Response

```json
{
  "content": [{
    "type": "text",
    "text": "✅ Successfully removed tag from note\n\n**Note ID:** note_789xyz\n**Tag ID:** tag_123\n\nThe tag has been successfully removed from the note."
  }]
}
```

---

## System Tools

### ping_joplin

Test connectivity to the Joplin server and verify API functionality.

#### Parameters

No parameters required.

#### Example Request

```json
{}
```

#### Example Response (Success)

```json
{
  "content": [{
    "type": "text",
    "text": "✅ **Joplin Connection Successful**\n\n**Server Status:** Connected\n**Host:** localhost:41184\n**Response Time:** 45ms\n**API Version:** Compatible\n\nThe Joplin MCP server is successfully connected and ready to handle requests."
  }]
}
```

#### Example Response (Failure)

```json
{
  "content": [{
    "type": "text",
    "text": "❌ **Joplin Connection Failed**\n\n**Server Status:** Disconnected\n**Host:** localhost:41184\n**Error:** Connection timeout\n\nPlease check that Joplin is running and the Web Clipper service is enabled."
  }]
}
```

---

## Error Handling

The Joplin MCP Server provides comprehensive error handling with detailed error messages.

### Common Error Types

#### Validation Errors

```json
{
  "error": {
    "code": "INVALID_PARAMS",
    "message": "note_id parameter is required and cannot be empty"
  }
}
```

#### Connection Errors

```json
{
  "error": {
    "code": "CONNECTION_ERROR",
    "message": "Failed to connect to Joplin server at localhost:41184"
  }
}
```

#### Authentication Errors

```json
{
  "error": {
    "code": "AUTH_ERROR",
    "message": "Invalid API token. Please check your Joplin API token."
  }
}
```

#### Not Found Errors

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Note with ID 'invalid_note_id' not found"
  }
}
```

#### Server Errors

```json
{
  "error": {
    "code": "SERVER_ERROR",
    "message": "Internal server error occurred while processing request"
  }
}
```

---

## Response Format

All MCP tool responses follow a consistent format:

### Success Response Structure

```json
{
  "content": [{
    "type": "text",
    "text": "Formatted response content with emojis and structured information"
  }]
}
```

### Response Content Features

- **Emojis**: Visual indicators for different content types (📝 for notes, 📁 for notebooks, 🏷️ for tags)
- **Structured Information**: Consistent formatting with bold headers and organized data
- **Metadata**: Comprehensive details including IDs, timestamps, and relationships
- **User-Friendly**: Human-readable format suitable for AI assistant interactions

### Content Types

- **📝 Notes**: Individual note information with content and metadata
- **📁 Notebooks**: Notebook listings and details with hierarchical structure
- **🏷️ Tags**: Tag information with usage statistics
- **✅ Success Messages**: Confirmation of successful operations
- **❌ Error Messages**: Clear error descriptions with troubleshooting hints

---

## Usage Tips

### Best Practices

1. **Search Optimization**: Use specific keywords and combine with notebook/tag filters for better results
2. **Batch Operations**: Create tags first, then apply them to notes for better organization
3. **Hierarchical Structure**: Use parent-child notebook relationships for logical organization
4. **Error Handling**: Always check response format and handle errors gracefully
5. **Connection Testing**: Use `ping_joplin` to verify connectivity before performing operations

### Performance Considerations

- **Search Limits**: Keep search limits reasonable (20-50) for better performance
- **Bulk Operations**: For multiple operations, consider the impact on Joplin's performance
- **Connection Pooling**: The server maintains persistent connections for efficiency
- **Caching**: Search results may be cached for improved response times

### Integration Examples

See the main [README.md](../README.md) for comprehensive integration examples and usage patterns.

---

*This API documentation is automatically generated from the Joplin MCP Server codebase and is kept up-to-date with the latest features and changes.* 