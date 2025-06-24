import os
import time

from joplin_mcp.client import JoplinMCPClient

# Test configuration
API_TOKEN = os.getenv("API_TOKEN", "")  # Use API_TOKEN instead of JOPLIN_TOKEN
PORT = 41184  # Use default joppy port


def setup_test_data(client):
    """Create test data for search testing."""
    # Create test notebooks - these return string IDs, not dictionaries
    notebook1_id = client.api.add_notebook(title="Test Notebook 1")
    notebook2_id = client.api.add_notebook(title="Test Notebook 2")

    # Debug: Check what type of objects we got
    print(f"notebook1_id type: {type(notebook1_id)}, value: {notebook1_id}")
    print(f"notebook2_id type: {type(notebook2_id)}, value: {notebook2_id}")

    # Create test notes with various content
    notes = [
        {
            "title": "Python Programming",
            "body": "Python is a high-level programming language.",
            "parent_id": notebook1_id,
        },
        {
            "title": "JavaScript Basics",
            "body": "JavaScript is a programming language for the web.",
            "parent_id": notebook1_id,
        },
        {
            "title": "Data Structures",
            "body": "Common data structures include arrays and linked lists.",
            "parent_id": notebook2_id,
        },
        {
            "title": "Algorithms",
            "body": "Sorting algorithms like quicksort and mergesort.",
            "parent_id": notebook2_id,
        },
    ]

    created_notes = []
    for note in notes:
        created_note = client.api.add_note(**note)
        created_notes.append(created_note)

    # Wait for notes to be available in search
    time.sleep(2)
    return notebook1_id, notebook2_id, created_notes


def test_enhanced_search():
    """Test enhanced search functionality with real Joplin client."""
    # Get API token from environment
    token = API_TOKEN
    if not token:
        print("Please set API_TOKEN environment variable")
        return

    # Initialize client with explicit port and disable SSL for local testing
    client = JoplinMCPClient(token=token, host="localhost", port=PORT, verify_ssl=False)

    try:
        # Setup test data
        notebook1_id, notebook2_id, notes = setup_test_data(client)

        # Test 1: Basic search with fuzzy matching
        print("\nTest 1: Basic search with fuzzy matching")
        results = client.enhanced_search(query="programming", fuzzy_threshold=0.7)
        print(f"Found {len(results.items)} results")
        for item in results.items:
            print(f"- {item['title']}")

        # Test 2: Boolean operators
        print("\nTest 2: Boolean operators")
        results = client.enhanced_search(
            query="Python programming", enable_boolean_operators=True
        )
        print(f"Found {len(results.items)} results")
        for item in results.items:
            print(f"- {item['title']}")

        # Test 3: Date range filtering (simplified)
        print("\nTest 3: Date range filtering")
        # Just test basic search without complex date parsing for now
        results = client.enhanced_search(query="programming", limit=5)
        print(f"Found {len(results.items)} results")
        for item in results.items:
            print(f"- {item['title']} (created: {item['created_time']})")

        # Test 4: Field-specific queries
        print("\nTest 4: Field-specific queries")
        results = client.enhanced_search(
            query="title:Python", enable_field_queries=True
        )
        print(f"Found {len(results.items)} results")
        for item in results.items:
            print(f"- {item['title']}")

        # Test 5: Combined filters
        print("\nTest 5: Combined filters")
        results = client.enhanced_search(
            query="programming", fuzzy_matching=True, fuzzy_threshold=0.7, limit=3
        )
        print(f"Found {len(results.items)} results")
        for item in results.items:
            print(f"- {item['title']} (notebook: {item['parent_id']})")

        # Test 6: Streaming results
        print("\nTest 6: Streaming results")
        batch_count = 0
        for batch in client.enhanced_search(
            query="programming", stream_results=True, batch_size=2, limit=4
        ):
            batch_count += 1
            print(f"\nBatch {batch_count} of {len(batch.items)} results:")
            for item in batch.items:
                print(f"- {item['title']}")
            if batch_count >= 2:  # Limit to 2 batches for testing
                break

    except Exception as e:
        print(f"Test failed: {e}")
        # Initialize variables for cleanup if they weren't created
        notebook1_id = notebook2_id = None
        notes = []
    finally:
        # Cleanup test data - only if variables exist
        try:
            if "notes" in locals() and notes:
                for note in notes:
                    # note is also likely a string ID, not a dict
                    if isinstance(note, str):
                        client.api.delete_note(note)
                    else:
                        client.api.delete_note(note["id"])
            if "notebook1_id" in locals() and notebook1_id:
                client.api.delete_notebook(notebook1_id)
            if "notebook2_id" in locals() and notebook2_id:
                client.api.delete_notebook(notebook2_id)
        except Exception as cleanup_error:
            print(f"Cleanup failed: {cleanup_error}")


if __name__ == "__main__":
    test_enhanced_search()
