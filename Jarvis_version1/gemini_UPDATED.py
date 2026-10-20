"""
J.A.R.V.I.S v1 - Online Brain (Gemini)

Uses the NEW google-genai SDK.

IMPORTANT:
- API key is stored directly in this file.
- No .env file is required.
- No PowerShell $env command is required.
- GUI can continue using:
      from gemini import complete
      response = complete(user_text)
"""

import json
import sys
from pathlib import Path

from google import genai
from google.genai import types


# ============================================================================
# API CONFIGURATION
# ============================================================================

# Paste your Gemini API key BETWEEN the quotes.
#
# Example:
# GEMINI_API_KEY = "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXX"
#
# Do NOT share this file publicly after putting your real key here.
GEMINI_API_KEY = "Paste your Gemini API key here"


# Current Gemini model
MODEL_NAME = "gemini-3.8-flash"


# Gemini client
gemini_client = None


class GeminiRequestCancelled(Exception):
    pass


def shutdown_gemini():
    global gemini_client

    if gemini_client is not None:
        client = gemini_client
        gemini_client = None
        client.close()


# ============================================================================
# JARVIS TOOLS
# ============================================================================

# Allow only these tools to be used by Gemini.
ALLOWED_TOOLS = {
    "get_time",
    "search_web",
    "read_webpage",
    "remember_fact",
    "recall_memory",
}


MAX_TOOL_ROUNDS = 5
TOOL_TIMEOUT = 10


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT = """You are J.A.R.V.I.S (Just A Rather Very Intelligent System), a personal AI assistant.

You have access to the following tools:

- get_time: Get current time
- search_web: Search the web for information
- read_webpage: Read content from a previously searched URL
- remember_fact: Store information in persistent memory
- recall_memory: Retrieve stored information

You are helpful, intelligent, and concise.
Keep responses brief and direct.

Always use tools when they would provide better information than your knowledge.

Remember that you are running on a local machine, so prefer offline solutions when possible.

When using tools:

1. Use search_web to find current information.
2. Use read_webpage to get full details from results.
3. Use remember_fact to store important information.
4. Use recall_memory to retrieve stored facts.
5. Always check memory first before searching.
"""


# ============================================================================
# IMPORT JARVIS TOOLS
# ============================================================================

sys.path.insert(0, str(Path(__file__).parent))

try:

    from jarvis_tools_COMPLETE import (
        TOOL_SCHEMAS,
        execute_tool,
    )

    TOOLS_AVAILABLE = True

except ImportError as e:

    print(f"ERROR: Could not import jarvis_tools_COMPLETE.py: {e}")

    TOOLS_AVAILABLE = False

    sys.exit(1)


# ============================================================================
# INITIALIZE GEMINI
# ============================================================================

def initialize_gemini() -> bool:
    """
    Initialize the Gemini client.

    The API key is taken directly from GEMINI_API_KEY above.
    No .env or environment variable is required.
    """

    global gemini_client

    # ------------------------------------------------------------
    # Check API key
    # ------------------------------------------------------------

    if (
        not GEMINI_API_KEY
        or GEMINI_API_KEY == "PASTE_YOUR_GEMINI_API_KEY_HERE"
    ):

        raise ValueError(
            "Gemini API key is missing.\n\n"
            "Open gemini.py and replace:\n\n"
            'GEMINI_API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"\n\n'
            "with your real Gemini API key."
        )


    try:

        # --------------------------------------------------------
        # NEW GOOGLE GENAI SDK
        # --------------------------------------------------------

        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )


        print("✓ Gemini API initialized")
        print(f"✓ Model: {MODEL_NAME}")
        print(
            f"✓ Tools: {', '.join(sorted(ALLOWED_TOOLS))}"
        )
        print(
            f"✓ Max tool rounds: {MAX_TOOL_ROUNDS}"
        )

        return True


    except Exception as e:

        raise ValueError(
            f"Failed to initialize Gemini API: {e}"
        ) from e


# ============================================================================
# EXECUTE JARVIS TOOL
# ============================================================================

def execute_gemini_tool(
    tool_name: str,
    tool_args: dict
) -> dict:

    """
    Execute a Jarvis tool safely.
    """

    # ------------------------------------------------------------
    # Whitelist
    # ------------------------------------------------------------

    if tool_name not in ALLOWED_TOOLS:

        return {
            "success": False,
            "error": (
                f"Tool '{tool_name}' is not allowed."
            ),
        }


    try:

        print(
            f"  [TOOL] "
            f"{tool_name}"
            f"({json.dumps(tool_args, default=str)})"
        )


        # --------------------------------------------------------
        # Execute actual Jarvis tool
        # --------------------------------------------------------

        result = execute_tool(
            tool_name,
            tool_args
        )


        print(
            f"  [RESULT] "
            f"{json.dumps(result, default=str)[:200]}..."
        )


        return result


    except Exception as e:

        return {
            "success": False,
            "error": (
                f"Tool execution error: "
                f"{type(e).__name__}: {str(e)}"
            ),
        }


# ============================================================================
# CONVERT YOUR EXISTING TOOL SCHEMAS TO GOOGLE GENAI FORMAT
# ============================================================================

def _build_tools_for_api():

    """
    Convert TOOL_SCHEMAS from jarvis_tools_COMPLETE.py
    into the format expected by google-genai.
    """

    if not TOOLS_AVAILABLE:
        return None


    function_declarations = []


    for schema in TOOL_SCHEMAS:

        function_data = schema.get(
            "function",
            {}
        )


        tool_name = function_data.get(
            "name"
        )


        # Only allow whitelisted tools
        if tool_name not in ALLOWED_TOOLS:
            continue


        parameters = function_data.get(
            "parameters",
            {
                "type": "object",
                "properties": {},
            }
        )


        # --------------------------------------------------------
        # Google GenAI function declaration
        # --------------------------------------------------------

        function_declarations.append(

            types.FunctionDeclaration(

                name=tool_name,

                description=function_data.get(
                    "description",
                    ""
                ),

                parameters_json_schema=parameters,
            )
        )


    if not function_declarations:
        return None


    return [
        types.Tool(
            function_declarations=function_declarations
        )
    ]


# ============================================================================
# MAIN GEMINI FUNCTION
# ============================================================================
#
# IMPORTANT FOR GUI:
#
# Your GUI can continue using:
#
#     from gemini import complete
#
#     response = complete(user_text)
#
# DO NOT change this function name.
# ============================================================================

def complete(
    prompt: str,
    temperature: float = 0.7,
    cancel_event=None
) -> str:

    """
    Send a prompt to Gemini.

    This is the function your GUI should call.
    """

    global gemini_client


    try:
        if cancel_event is not None and cancel_event.is_set():
            raise GeminiRequestCancelled("Gemini request was cancelled.")

        # --------------------------------------------------------
        # Initialize client if it hasn't been initialized yet
        # --------------------------------------------------------

        if gemini_client is None:

            initialize_gemini()

        if cancel_event is not None and cancel_event.is_set():
            raise GeminiRequestCancelled("Gemini request was cancelled.")

        print(
            f"\n[GEMINI] Model: {MODEL_NAME}"
        )

        print(
            f"[PROMPT] {prompt}\n"
        )


        # --------------------------------------------------------
        # Initial conversation
        # --------------------------------------------------------

        messages = [

            types.Content(

                role="user",

                parts=[

                    types.Part.from_text(
                        text=prompt
                    )

                ],
            )

        ]


        # --------------------------------------------------------
        # Tools
        # --------------------------------------------------------

        tools_for_api = _build_tools_for_api()


        # --------------------------------------------------------
        # Gemini generation configuration
        # --------------------------------------------------------

        config = types.GenerateContentConfig(

            temperature=temperature,

            max_output_tokens=1024,

            system_instruction=SYSTEM_PROMPT,

            tools=tools_for_api,

            # We execute the functions ourselves.
            automatic_function_calling=(
                types.AutomaticFunctionCallingConfig(
                    disable=True
                )
            ),
        )


        # ========================================================
        # TOOL-CALLING LOOP
        # ========================================================

        for tool_round in range(
            1,
            MAX_TOOL_ROUNDS + 1
        ):
            if cancel_event is not None and cancel_event.is_set():
                raise GeminiRequestCancelled("Gemini request was cancelled.")

            print(
                f"[ROUND {tool_round}] "
                f"Calling Gemini..."
            )


            # ----------------------------------------------------
            # Call Gemini
            # ----------------------------------------------------

            try:

                response = gemini_client.models.generate_content(
                    model=MODEL_NAME,
                    contents=messages,
                     config=config,
               )


            except Exception as e:
                if cancel_event is not None and cancel_event.is_set():
                    raise GeminiRequestCancelled(
                        "Gemini request was cancelled."
                    ) from e

                error_text = str(e)

                if "503" in error_text or "UNAVAILABLE" in error_text:
                    print("[WARNING] Gemini is temporarily busy.")
                    return (
                            "Gemini is temporarily unavailable due to "
                             "high server demand. Please try again."
                 )
                print(f"[ERROR] Gemini API call failed: {e}")
                return (
                    "Error: Failed to get response "
                    f"from Gemini: {str(e)}"
                )


            if cancel_event is not None and cancel_event.is_set():
                raise GeminiRequestCancelled("Gemini request was cancelled.")

            # ----------------------------------------------------
            # Validate response
            # ----------------------------------------------------

            if (
                not response
                or not response.candidates
            ):

                print(
                    "[ERROR] Gemini returned no candidates."
                )

                return (
                    "No response from Gemini API."
                )


            candidate = response.candidates[0]


            if (
                not candidate.content
                or not candidate.content.parts
            ):

                print(
                    "[ERROR] Gemini returned no content."
                )

                return (
                    "No response generated by Gemini."
                )


            # ----------------------------------------------------
            # Find function calls
            # ----------------------------------------------------

            tool_results = []


            for part in candidate.content.parts:
                if cancel_event is not None and cancel_event.is_set():
                    raise GeminiRequestCancelled(
                        "Gemini request was cancelled."
                    )

                function_call = getattr(
                    part,
                    "function_call",
                    None
                )


                if not function_call:
                    continue


                tool_name = function_call.name


                tool_args = dict(
                    function_call.args or {}
                )


                print(
                    f"\n[TOOL_CALL] {tool_name}"
                )


                # ------------------------------------------------
                # Execute tool
                # ------------------------------------------------

                tool_result = execute_gemini_tool(

                    tool_name,

                    tool_args
                )

                if cancel_event is not None and cancel_event.is_set():
                    raise GeminiRequestCancelled(
                        "Gemini request was cancelled."
                    )

                tool_results.append({

                    "name": tool_name,

                    "response": tool_result,

                })


            # ====================================================
            # NO TOOL CALL
            #
            # Gemini has produced its final answer.
            # ====================================================

            if not tool_results:
                if cancel_event is not None and cancel_event.is_set():
                    raise GeminiRequestCancelled(
                        "Gemini request was cancelled."
                    )

                final_text = ""


                for part in candidate.content.parts:

                    text = getattr(
                        part,
                        "text",
                        None
                    )


                    if text:

                        final_text += text


                if not final_text:

                    final_text = (
                        "(No response generated)"
                    )


                print(
                    f"\n[RESPONSE] {final_text}"
                )


                return final_text


            # ====================================================
            # ADD GEMINI'S FUNCTION-CALL MESSAGE
            # ====================================================

            messages.append(
                candidate.content
            )


            # ====================================================
            # BUILD FUNCTION RESPONSES
            # ====================================================

            tool_response_parts = []


            for tool_result in tool_results:

                tool_response_parts.append(

                    types.Part.from_function_response(

                        name=tool_result["name"],

                        response=tool_result["response"],
                    )

                )


            # ====================================================
            # IMPORTANT FIX
            #
            # Your API rejected role="tool".
            # Therefore this message deliberately uses
            # role="user".
            # ====================================================

            messages.append(

                types.Content(

                    role="user",

                    parts=tool_response_parts,
                )

            )


            print(
                "[SENT] Tool results back to Gemini..."
            )


        # ========================================================
        # MAX TOOL ROUNDS REACHED
        # ========================================================

        print(
            "[WARNING] Maximum tool rounds reached."
        )


        return (
            "I reached the maximum number of "
            "tool-processing steps."
        )


    # ============================================================
    # ERROR HANDLING
    # ============================================================

    except GeminiRequestCancelled:
        raise


    except ValueError as e:

        error_msg = (
            f"Configuration error: {str(e)}"
        )

        print(
            f"[ERROR] {error_msg}"
        )

        raise


    except Exception as e:

        print(
            f"[ERROR] "
            f"{type(e).__name__}: {str(e)}"
        )


        import traceback

        traceback.print_exc()


        raise


# ============================================================================
# SIMPLE TERMINAL TEST
# ============================================================================

def interactive_mode():

    print(
        "\n" + "=" * 70
    )

    print(
        "J.A.R.V.I.S v1 - Online Brain (Gemini)"
    )

    print(
        "=" * 70
    )


    try:

        initialize_gemini()


        print(
            "\nType 'exit' to quit.\n"
        )


        while True:

            try:

                user_input = input(
                    "You: "
                ).strip()


                if user_input.lower() in (
                    "exit",
                    "quit",
                    "bye",
                ):

                    print(
                        "Jarvis: Goodbye!"
                    )

                    break


                if not user_input:
                    continue


                response = complete(
                    user_input
                )


                print(
                    f"Jarvis: {response}\n"
                )


            except KeyboardInterrupt:

                print(
                    "\nJarvis: Conversation interrupted."
                )

                break


            except Exception as e:

                print(
                    f"Error: {e}\n"
                )


    except Exception as e:

        print(
            f"\n❌ Initialization failed: {e}"
        )

        sys.exit(1)


# ============================================================================
# PROGRAM ENTRY
# ============================================================================

if __name__ == "__main__":

    interactive_mode()