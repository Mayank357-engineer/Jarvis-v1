"""
Jarvis v1 - Shared Tool Layer
5 tools available to both offline (LFM2.5) and online (Gemini) brains
Tool schemas compatible with both OpenAI-style and Google Gemini APIs

Tools:
1. get_time() - Current time
2. search_web(query) - Web search via DuckDuckGo
3. read_webpage(result_id) - Read cached webpage
4. remember_fact(key, value) - Store to memory
5. recall_memory(key) - Retrieve from memory
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import traceback

# Try to import web search library
try:
    from duckduckgo_search import DDGS
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    print("⚠️  duckduckgo-search not installed: pip install duckduckgo-search")

# Memory storage
try:
    from memory import load_memory, save_memory
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    print("⚠️  memory.py not found - memory tools will not persist")


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL SCHEMAS FOR GEMINI API
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current time in HH:MM format",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information using DuckDuckGo. Returns top 5 results with titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g., 'Python 3.13 release date')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Read the content of a webpage from a previous search result. Use the result_id (0-4) from search_web results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "result_id": {
                        "type": "integer",
                        "description": "The index of the search result (0-4) to read"
                    }
                },
                "required": ["result_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Store a fact in persistent memory. Examples: 'remember my favorite color is blue', 'save that the user prefers coffee'",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The key to store (e.g., 'favorite_color', 'preferred_drink')"
                    },
                    "value": {
                        "type": "string",
                        "description": "The value to remember (e.g., 'blue', 'coffee')"
                    }
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Retrieve a fact from persistent memory. Examples: 'what is my favorite color', 'do you remember my preferred drink'",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The key to retrieve (e.g., 'favorite_color', 'preferred_drink')"
                    }
                },
                "required": ["key"]
            }
        }
    }
]


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Web search cache (stores results from last search)
_web_cache = {}


def get_time() -> Dict[str, Any]:
    """
    Get current time in HH:MM format
    
    Returns:
        dict with 'success' and 'result' fields
    """
    try:
        current_time = datetime.now().strftime("%I:%M %p")
        return {
            "success": True,
            "result": current_time
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get time: {str(e)}"
        }


def search_web(query: str) -> Dict[str, Any]:
    """
    Search the web using DuckDuckGo
    
    Args:
        query: Search query string
    
    Returns:
        dict with 'success' and 'results' (list) or 'error'
    """
    if not SEARCH_AVAILABLE:
        return {
            "success": False,
            "error": "DuckDuckGo search not available. Install: pip install duckduckgo-search"
        }
    
    try:
        print(f"  [SEARCH] Querying: {query}")
        
        ddgs = DDGS()
        results = []
        
        # Search with timeout
        try:
            search_results = ddgs.text(query, max_results=5)
        except Exception as e:
            return {
                "success": False,
                "error": f"Search failed: {str(e)}"
            }
        
        # Format results
        for i, result in enumerate(search_results):
            formatted = {
                "id": i,
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", "")[:200]  # First 200 chars
            }
            results.append(formatted)
            
            # Cache for read_webpage
            _web_cache[i] = {
                "title": formatted["title"],
                "url": formatted["url"],
                "full_snippet": result.get("body", "")
            }
        
        if not results:
            return {
                "success": False,
                "error": f"No results found for '{query}'"
            }
        
        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Search error: {type(e).__name__}: {str(e)}"
        }


def read_webpage(result_id: int) -> Dict[str, Any]:
    """
    Read content from a cached search result
    
    Args:
        result_id: Index of result from search_web (0-4)
    
    Returns:
        dict with 'success' and 'content' or 'error'
    """
    try:
        if result_id not in _web_cache:
            return {
                "success": False,
                "error": f"Result {result_id} not found in cache. Run search_web first."
            }
        
        cached = _web_cache[result_id]
        return {
            "success": True,
            "title": cached["title"],
            "url": cached["url"],
            "content": cached["full_snippet"]
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read webpage: {str(e)}"
        }


def remember_fact(key: str, value: str) -> Dict[str, Any]:
    """
    Store a fact in persistent memory (JSON file)
    
    Args:
        key: Memory key (e.g., 'favorite_color')
        value: Memory value (e.g., 'blue')
    
    Returns:
        dict with 'success' status
    """
    if not MEMORY_AVAILABLE:
        return {
            "success": False,
            "error": "Memory system not available"
        }
    
    try:
        # Validate inputs
        if not key or not isinstance(key, str):
            return {
                "success": False,
                "error": "Key must be a non-empty string"
            }
        
        if not value or not isinstance(value, str):
            return {
                "success": False,
                "error": "Value must be a non-empty string"
            }
        
        # Load current memory
        memory = load_memory()
        
        # Store fact
        memory[key] = value
        
        # Save back
        save_memory(memory)
        
        print(f"  [MEMORY] Stored: {key} = {value}")
        
        return {
            "success": True,
            "message": f"Remembered: {key} = {value}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to remember fact: {str(e)}"
        }


def recall_memory(key: str) -> Dict[str, Any]:
    """
    Retrieve a fact from persistent memory
    
    Args:
        key: Memory key to retrieve
    
    Returns:
        dict with 'success' and 'value' or 'error'
    """
    if not MEMORY_AVAILABLE:
        return {
            "success": False,
            "error": "Memory system not available"
        }
    
    try:
        # Load memory
        memory = load_memory()
        
        # Check if key exists
        if key not in memory:
            return {
                "success": False,
                "error": f"No memory found for '{key}'"
            }
        
        value = memory[key]
        print(f"  [MEMORY] Retrieved: {key} = {value}")
        
        return {
            "success": True,
            "key": key,
            "value": value
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to recall memory: {str(e)}"
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_FUNCTIONS = {
    "get_time": get_time,
    "search_web": search_web,
    "read_webpage": read_webpage,
    "remember_fact": remember_fact,
    "recall_memory": recall_memory,
}


def get_tool_function(tool_name: str):
    """Get a tool function by name"""
    return TOOL_FUNCTIONS.get(tool_name)


def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by name and arguments
    
    Args:
        tool_name: Name of tool
        tool_args: Arguments dict
    
    Returns:
        Tool result dict
    """
    tool_func = get_tool_function(tool_name)
    
    if not tool_func:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }
    
    try:
        # Call tool with unpacked arguments
        result = tool_func(**tool_args)
        return result
    
    except TypeError as e:
        return {
            "success": False,
            "error": f"Invalid arguments for {tool_name}: {str(e)}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Tool error: {type(e).__name__}: {str(e)}"
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI TEST MODE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*70)
    print("JARVIS v1 - Tool Testing CLI")
    print("="*70 + "\n")
    
    # Test get_time
    print("[1] Testing get_time()...")
    result = get_time()
    print(f"    Result: {result}\n")
    
    # Test search_web
    print("[2] Testing search_web('Python 3.13')...")
    result = search_web("Python 3.13")
    if result.get("success"):
        print(f"    Found {result['count']} results:")
        for r in result["results"]:
            print(f"      [{r['id']}] {r['title']}")
    else:
        print(f"    Error: {result.get('error')}\n")
    
    # Test read_webpage
    if result.get("success") and result["results"]:
        print("[3] Testing read_webpage(0)...")
        result2 = read_webpage(0)
        print(f"    Title: {result2.get('title', 'N/A')}")
        print(f"    URL: {result2.get('url', 'N/A')}")
        print(f"    Content preview: {result2.get('content', 'N/A')[:100]}...\n")
    
    # Test memory tools
    print("[4] Testing remember_fact('favorite_color', 'blue')...")
    result = remember_fact("favorite_color", "blue")
    print(f"    Result: {result}\n")
    
    print("[5] Testing recall_memory('favorite_color')...")
    result = recall_memory("favorite_color")
    print(f"    Result: {result}\n")
    
    print("✓ All tools tested successfully!")
