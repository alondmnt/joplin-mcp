#!/usr/bin/env python3
"""
Ollama MCP Client - Interactive chat with Ollama using Joplin MCP tools
"""

import asyncio
import json
import sys
from typing import Dict, List, Any
import subprocess
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class OllamaMCPClient:
    """Client that bridges Ollama and MCP servers."""
    
    def __init__(self, ollama_model: str = "gemma3:4b"):
        self.ollama_model = ollama_model
        self.session: ClientSession = None
        self.exit_stack = AsyncExitStack()
        self.tools: List[Dict[str, Any]] = []
        
    async def connect_to_mcp_server(self, server_script_path: str):
        """Connect to the MCP server."""
        print(f"🔗 Connecting to MCP server: {server_script_path}")
        
        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env={"PYTHONPATH": "/Users/alondmnt/projects/joplin/mcp"}
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # Get available tools
        response = await self.session.list_tools()
        self.tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
            for tool in response.tools
        ]
        
        print(f"✅ Connected! Available tools: {[tool['name'] for tool in self.tools]}")
        
    def call_ollama(self, prompt: str, system_message: str = None) -> str:
        """Call Ollama with the given prompt."""
        try:
            cmd = ["ollama", "run", self.ollama_model]
            
            if system_message:
                full_prompt = f"System: {system_message}\n\nUser: {prompt}"
            else:
                full_prompt = prompt
                
            result = subprocess.run(
                cmd,
                input=full_prompt,
                text=True,
                capture_output=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"❌ Ollama error: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return "❌ Ollama request timed out"
        except Exception as e:
            return f"❌ Error calling Ollama: {e}"
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute an MCP tool."""
        try:
            print(f"🔧 Executing tool: {tool_name} with args: {arguments}")
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract text content from result
            if hasattr(result, 'content') and result.content:
                content_parts = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        content_parts.append(content.text)
                    else:
                        content_parts.append(str(content))
                return "\n".join(content_parts)
            else:
                return str(result)
                
        except Exception as e:
            return f"❌ Error executing tool {tool_name}: {e}"
    
    async def chat_with_ollama(self):
        """Interactive chat session with Ollama and MCP tools."""
        print("\n🚀 Ollama + Joplin MCP Chat Started!")
        print("=" * 50)
        print("Available Joplin tools:")
        for tool in self.tools:
            print(f"  • {tool['name']}: {tool['description']}")
        print("\nType your message, 'help' for commands, or 'quit' to exit.")
        print("=" * 50)
        
        # System message for Ollama
        system_message = f"""You are an AI assistant with access to Joplin note-taking tools. 

Available tools:
{json.dumps([{
    'name': tool['name'], 
    'description': tool['description']
} for tool in self.tools], indent=2)}

When you need to use a tool, respond with a JSON object in this format:
{{"action": "use_tool", "tool": "tool_name", "arguments": {{"arg1": "value1"}}}}

For regular conversation, just respond normally. Be helpful and suggest using Joplin tools when appropriate."""

        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if user_input.lower() == 'quit':
                    break
                elif user_input.lower() == 'help':
                    print("\nCommands:")
                    print("  help - Show this help")
                    print("  quit - Exit the chat")
                    print("  tools - List available tools")
                    print("\nJust type normally to chat with Ollama!")
                    continue
                elif user_input.lower() == 'tools':
                    print("\nAvailable Joplin tools:")
                    for tool in self.tools:
                        print(f"  • {tool['name']}: {tool['description']}")
                    continue
                
                if not user_input:
                    continue
                
                # Get response from Ollama
                print("🤖 Thinking...")
                ollama_response = self.call_ollama(user_input, system_message)
                
                # Check if Ollama wants to use a tool
                tool_executed = False
                try:
                    # Extract JSON from response (handle code blocks and various formats)
                    json_content = None
                    response_lower = ollama_response.lower()
                    
                    # Debug: Show what we're analyzing
                    if '"action"' in response_lower:
                        print(f"🔍 Found potential tool request in response")
                    
                    # Check if it's wrapped in a code block
                    if "```json" in response_lower:
                        # Extract JSON from code block
                        start_idx = ollama_response.find("```json") + 7
                        end_idx = ollama_response.find("```", start_idx)
                        if end_idx != -1:
                            json_content = ollama_response[start_idx:end_idx].strip()
                            print(f"🔍 Extracted JSON from code block: {json_content[:100]}...")
                    elif "```" in ollama_response and "{" in ollama_response:
                        # Handle code blocks without "json" label
                        lines = ollama_response.split('\n')
                        in_code_block = False
                        json_lines = []
                        for line in lines:
                            if line.strip().startswith('```'):
                                if in_code_block:
                                    break
                                in_code_block = True
                                continue
                            if in_code_block and ('{' in line or '"action"' in line):
                                json_lines.append(line)
                        if json_lines:
                            json_content = '\n'.join(json_lines).strip()
                            print(f"🔍 Extracted JSON from unlabeled code block: {json_content[:100]}...")
                    elif ollama_response.strip().startswith('{') and '"action"' in ollama_response:
                        # Direct JSON response
                        json_content = ollama_response.strip()
                        print(f"🔍 Found direct JSON: {json_content[:100]}...")
                    elif '{' in ollama_response and '"action"' in ollama_response:
                        # JSON anywhere in the response (not just at start)
                        start_idx = ollama_response.find('{')
                        end_idx = ollama_response.rfind('}') + 1
                        if start_idx != -1 and end_idx > start_idx:
                            json_content = ollama_response[start_idx:end_idx].strip()
                            print(f"🔍 Found JSON in response: {json_content[:100]}...")
                    
                    # Try to parse and execute tool if we found JSON
                    if json_content and '"action"' in json_content:
                        try:
                            tool_request = json.loads(json_content)
                            if tool_request.get("action") == "use_tool":
                                tool_name = tool_request.get("tool")
                                arguments = tool_request.get("arguments", {})
                                
                                print(f"🔧 Executing tool: {tool_name} with args: {arguments}")
                                
                                # Execute the tool
                                tool_result = await self.execute_tool(tool_name, arguments)
                                tool_executed = True
                                
                                # Get Ollama's interpretation of the result
                                interpretation_prompt = f"The tool '{tool_name}' returned this result: {tool_result}\n\nPlease summarize and explain this result to the user in a helpful way."
                                print("🤖 Interpreting results...")
                                final_response = self.call_ollama(interpretation_prompt)
                                
                                print(f"🤖 Assistant: {final_response}")
                            else:
                                print(f"🔍 JSON found but action is not 'use_tool': {tool_request.get('action')}")
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON parsing failed: {e}")
                            print(f"🔍 Content that failed to parse: {json_content}")
                    else:
                        if '"action"' in response_lower:
                            print(f"🔍 Found 'action' in response but couldn't extract valid JSON")
                            print(f"🔍 Response: {ollama_response[:200]}...")
                        
                except Exception as e:
                    print(f"❌ Error processing tool request: {e}")
                
                # If no tool was executed, show the original response
                if not tool_executed:
                    print(f"🤖 Assistant: {ollama_response}")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()


async def main():
    """Main function."""
    server_path = "/Users/alondmnt/projects/joplin/mcp/run_mcp_server.py"
    
    client = OllamaMCPClient()
    try:
        await client.connect_to_mcp_server(server_path)
        await client.chat_with_ollama()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 