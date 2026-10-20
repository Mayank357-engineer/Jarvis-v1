from datetime import datetime
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup
import json
from memory import remember_fact , recall_memory



# Temporary web-result storage
web_cache = {}


def get_time():
    return datetime.now().strftime("%I:%M %p")


def search_web(query):
    global web_cache

    try:
        results = list(
            DDGS().text(
                query,
                region="in-en",
                safesearch="moderate",
                max_results=5
            )
        )

        if not results:
            return "No search results found."

        # Clear old results
        web_cache.clear()

        output = []

        for i, result in enumerate(results[:5], start=1):

            title = result.get("title", "")
            url = result.get("href", "")
            summary = result.get("body", "")

            # Store the real URL privately in Python
            web_cache[i] = {
                "title": title,
                "url": url,
                "summary": summary
            }

            # Give LFM2.5 only the useful search information
            output.append({
                "result_id": i,
                "title": title,
                "summary": summary
            })

        return json.dumps(output, ensure_ascii=False)

    except Exception as e:
        return f"Web search failed: {e}"


def read_webpage(result_id):
    try:
        result_id = int(result_id)

        if result_id not in web_cache:
            return "That search result is no longer available."

        url = web_cache[result_id]["url"]

        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(" ", strip=True)

        return (
            f"Title: {web_cache[result_id]['title']}\n"
            f"URL: {url}\n\n"
            f"Page content:\n{text[:12000]}"
        )

    except Exception as e:
        return f"Could not read webpage: {e}"


def get_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "Use this function whenever the user asks for the current time.",
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
                "description": "Search the internet and return the top 5 relevant results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The web search query."
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
                "description": "Read one of the search results in detail using its result_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "result_id": {
                            "type": "integer",
                            "description": "The result_id from the previous web search."
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
        "description": "Save information that the user explicitly asks Jarvis to remember.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Short name for the memory."
                },
                "value": {
                    "type": "string",
                    "description": "Information to remember."
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
        "description": "Retrieve information that Jarvis previously saved in memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key of the saved memory to retrieve."
                }
            },
            "required": ["key"]
        }
    }
}
    ]