import os
import time
from smolagents import CodeAgent, LiteLLMModel, tool
import asyncio
import threading
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from phoenix.otel import register

# configure the Phoenix tracer
# tracer_provider = register(
#     endpoint=os.getenv("PHOENIX_ENDPOINT"),
#     project_name="gradio",  # Default is 'default'
#     auto_instrument=True,  # Auto-instrument your app based on installed OI dependencies
# )

instructions = """
Your task is to help users build and modify Gradio applications within this interactive sandbox
environment. You are a Gradio application builder that can read, understand, and edit Python code
that creates Gradio interfaces optimized for Gradio-Lite.

Key Guidelines:
- ONLY use Gradio components and functionality - no other UI frameworks
- Always call read_code() first to understand the current application state
- Use the think() tool to plan and reflect before implementing any features
- Use edit_code() to make precise modifications to the existing Gradio app
- Focus on creating intuitive, functional Gradio interfaces using gr.Interface, gr.Blocks, and
various input/output components
- When users request features, implement them using appropriate Gradio components like
gr.Textbox, gr.Button, gr.Image, gr.Audio, gr.Video, gr.Dataframe, etc.
- Maintain proper Python syntax and Gradio best practices
- Always end Gradio apps with .launch() to make them runnable
- Pay attention to the success/error messages from edit_code() and adjust accordingly if
replacements fail
- When debugging, analyze the full error trace to identify the root cause and plan the necessary fixes before calling edit_code; perform the required updates in one pass whenever possible to avoid repeated retries
- CRITICAL STRING HANDLING: NEVER use double quotes with literal line breaks in Python strings as this breaks syntax. ALWAYS use triple quotes for multi-line strings, especially in gr.Markdown() components

Systematic Planning and Component-Based Thinking:
- ALWAYS use the think() tool before implementing any new feature or modification
- Break down user requests into specific Gradio components and their relationships
- Think through the complete user experience flow from input to output
- Consider component layout using gr.Blocks, gr.Row, gr.Column for proper organization
- Plan event handlers and data flow between components before coding
- Examples of component mapping:
  * Image Gallery Viewer → gr.Gallery + gr.File (upload) + gr.Button (navigation)
  * Calculator → gr.Textbox (display) + grid of gr.Button components + gr.Row/gr.Column layout
  * Data Converter → gr.File (input) + gr.JSON (preview) + gr.Dataframe (output)
  * Chat Interface → gr.Chatbot + gr.Textbox (input) + gr.Button (send)
  * Form Builder → gr.Textbox, gr.Dropdown, gr.Checkbox, gr.Slider + gr.Button (submit)
- Reflect on implementation strategy: component selection, layout design, event handling
- Use the think() tool to course-correct if initial approaches don't work as expected

Error Analysis Protocol:
- When encountering errors, FIRST understand the complete context before making any changes
- Parse error messages systematically: What type of error? What was the input? What was expected?
- Look for contextual clues in debug output that reveal the actual problem
- If you see file paths in content fields, that's usually the problem - you're parsing metadata instead of file contents
- "JSON parsing failed" is often a symptom; "trying to parse a file path as JSON content" may be the root cause

Data Flow Understanding:
- Always trace how data flows through your functions
- When debugging file uploads, verify what type of object you're receiving and what properties it has
- In Gradio-Lite, file objects may be paths, NamedString objects, or actual content - handle each case explicitly
- Add comprehensive debugging FIRST to understand what you're actually working with

Root Cause Focus:
- Don't treat symptoms - find the underlying cause
- Before making any edits, write out your hypothesis of what's going wrong and why
- Test your hypothesis with targeted debugging before implementing fixes
- Analyze error messages + debug output patterns to identify the real issue

One-Shot Problem Solving:
- Analyze the full error context to make the correct fix immediately
- Avoid trial-and-error approaches that require multiple iterations
- If your first fix doesn't work, step back and re-analyze rather than making more incremental changes

CRITICAL Gradio-Lite (Pyodide) File Handling:
- Gradio-Lite runs in Pyodide (Python in the browser) with different file handling behavior
- File objects in Gradio-Lite/Pyodide have different properties than regular Python/Gradio
- When handling gr.File components, file objects may be browser File objects or special wrappers
- In Pyodide, file operations may behave differently due to browser security constraints
- Never assume file objects can be decoded with .decode() without checking the object type
- Always handle None/empty file cases gracefully
- When working with pandas and file inputs, ensure proper content extraction before parsing
- Be aware that some Python file operations may not work the same way in the browser environment

Your goal is to transform user requests into working Gradio applications that demonstrate the
requested functionality. Be creative with Gradio's extensive component library to build engaging,
interactive web interfaces that work reliably in the Gradio-Lite environment.

MANDATORY Documentation and Reference Guidelines:
- NEVER rely on your internal knowledge for component implementation details
- ALWAYS use Gradio MCP documentation tools for ALL component implementations
- BEFORE implementing ANY Gradio component, you MUST query the Gradio documentation via MCP
- You have access to these specific MCP tools:
  * gradio_docs_mcp_search_gradio_docs: Search for specific component documentation
  * gradio_docs_mcp_load_gradio_docs: Load comprehensive Gradio documentation
- For EVERY component you use, search the Gradio MCP for:
  * Current API parameters and their exact syntax
  * Latest usage examples and patterns
  * Current best practices and recommendations
  * Compatibility information with current Gradio version
- NEVER assume parameter names, methods, or syntax from memory
- ALWAYS verify component behavior through Gradio MCP tools before implementation
- If MCP tools are not available, explicitly inform the user that current documentation cannot be accessed
- The Gradio MCP provides the ONLY reliable source for current, accurate Gradio documentation
- Your internal knowledge may be outdated - Gradio MCP eliminates this risk with real-time documentation

Implementation Protocol:
1. User requests a feature
2. Call read_code() to understand the current application state
3. Use think() tool to:
   - Break down the request into specific Gradio components
   - Plan the component layout and interactions
   - Consider the user experience flow
   - Identify potential challenges or requirements
4. Use gradio_docs_mcp_search_gradio_docs to find relevant component documentation
5. Use ONLY the information retrieved from Gradio MCP for implementation
6. Call think() again if you need to revise your approach based on documentation
7. Implement using edit_code() with the planned component structure
8. If unsure about any detail, query Gradio MCP again rather than guessing
9. Use gradio_docs_mcp_load_gradio_docs for comprehensive overviews when needed
10. Reflect with think() tool if implementation doesn't work as expected
"""

# -------- Persistence config (outside project tree) --------
SANDBOX_ROOT = os.environ.get(
    "SANDBOX_ROOT", os.path.expanduser("~/.gradio_app_builder")
)
WORKSPACE = os.environ.get(
    "SANDBOX_WORKSPACE", "default"
)  # you can customize per user/session
WS_DIR = os.path.join(SANDBOX_ROOT, WORKSPACE)
CODE_PATH = os.path.join(WS_DIR, "sandbox.py")
SNAPSHOT_DIR = os.path.join(WS_DIR, "snapshots")

os.makedirs(SANDBOX_ROOT, exist_ok=True)
os.makedirs(WS_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

INITIAL_CODE = """\
import gradio as gr

def greet(name):
    return "Hello, " + name + "!!!"

gr.Interface(greet, 'textbox', 'textbox').launch()
"""


def ensure_code_exists():
    if not os.path.exists(CODE_PATH):
        with open(CODE_PATH, "w", encoding="utf-8") as f:
            f.write(INITIAL_CODE)


def read_persisted_code() -> str:
    ensure_code_exists()
    with open(CODE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def atomic_write(path: str, content: str):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)  # atomic on POSIX


def write_persisted_code(content: str, snapshot: bool = True):
    atomic_write(CODE_PATH, content)
    if snapshot:
        ts = time.strftime("%Y%m%d-%H%M%S")
        atomic_write(os.path.join(SNAPSHOT_DIR, f"sandbox_{ts}.py"), content)


# ---- MCP (Gradio Docs) integration ----
MCP_SSE_URL = "https://gradio-docs-mcp.hf.space/gradio_api/mcp/sse"


class GradioDocsMCPClient:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    def _run(self, coro):
        """Run an async coroutine on the background loop and return its result."""
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=60)

    async def _connect_async(self):
        # Bridge remote SSE server to stdio via mcp-remote
        params = StdioServerParameters(
            command="npx",
            args=[
                "mcp-remote",
                MCP_SSE_URL,
                "--transport",
                "sse-first",
            ],
            env=None,
        )
        self._stack = AsyncExitStack()
        stdio_read, stdio_write = await self._stack.enter_async_context(
            stdio_client(params)
        )
        self._session = await self._stack.enter_async_context(
            ClientSession(stdio_read, stdio_write)
        )
        await self._session.initialize()

    def ensure_connected(self):
        if self._session is None:
            self._run(self._connect_async())

    def _content_to_text(self, result) -> str:
        parts = []
        for item in getattr(result, "content", []) or []:
            # items may be typed objects with .type/.text
            text = getattr(item, "text", None)
            if text is None and getattr(item, "type", None) == "text":
                text = getattr(item, "text", "")
            parts.append(text if text is not None else str(item))
        return "\n".join(filter(None, parts)) or str(result)

    def load_docs(self) -> str:
        self.ensure_connected()
        res = self._run(self._session.call_tool("gradio_docs_mcp_load_gradio_docs", {}))
        return self._content_to_text(res)

    def search_docs(self, query: str) -> str:
        self.ensure_connected()
        res = self._run(
            self._session.call_tool(
                "gradio_docs_mcp_search_gradio_docs", {"query": query}
            )
        )
        return self._content_to_text(res)


_gradio_mcp = GradioDocsMCPClient()


@tool
def read_code() -> str:
    """
    Retrieves and returns the current state of the inner Gradio application code.

    This tool fetches the current Python code that defines the Gradio app running
    in the sandbox environment. Use this to understand what app is currently loaded
    before making any modifications or updates.

    Returns:
        str: The current Python code formatted with markdown code block delimiters

    Usage Instructions:
    - ALWAYS call this tool first before modifying any inner Gradio app
    - Use this to understand the current app structure, components, and functionality
    - Essential for maintaining context when users request changes to the embedded app
    - Call this whenever you need to see what's currently running in the preview pane
    - No parameters needed - it automatically fetches the current state

    """
    return f"```python\n{read_persisted_code()}\n```"


@tool
def edit_code(old_str: str, new_str: str) -> str:
    """
    Modifies the inner Gradio application code by replacing specific code sections.

    This tool performs precise string replacements in the current SANDBOX_CODE to update
    the inner Gradio app. Use this to implement user-requested changes to the embedded app.

    Args:
        old_str (str): The exact code string to find and replace (must match exactly
                    including whitespace, indentation, and line breaks)
        new_str (str): The new code string to replace the old_str with

    Returns:
        str: A status message indicating success or failure:
            - "SUCCESS: Code successfully updated." if replacement succeeded
            - "ERROR: Could not find the specified code..." if old_str not found
            - "WARNING: No changes were made..." if old_str and new_str are identical
            - "ERROR: An unexpected error occurred..." for other exceptions

    Usage Instructions:
    - ALWAYS call read_current_app_code() first to see the current state
    - Use exact string matching - whitespace and indentation must match precisely
    - Choose old_str carefully to avoid unintended replacements
    - Include enough context in old_str to ensure unique matching
    - Check the return message to confirm the operation succeeded
    - Use for incremental changes like adding components, modifying functions, or updating logic

    Best Practices:
    - Replace entire function definitions or component blocks when possible
    - Include proper indentation in new_str to maintain code structure
    - Verify the replacement makes syntactic sense in context
    - CRITICAL: NEVER use double quotes with literal line breaks - this breaks Python syntax
    - ALWAYS use triple quotes (triple double quotes) for any multi-line strings, especially in gr.Markdown()
    - Example WRONG: gr.Markdown with double quotes and newlines breaks the code
    - Example CORRECT: gr.Markdown with triple quotes works properly
    - When content spans multiple lines, wrap it in triple quotes to prevent syntax errors

    """
    try:
        content = read_persisted_code()
        if old_str not in content:
            return "ERROR: Could not find the specified code to replace."
        updated = content.replace(old_str, new_str)
        if updated == content:
            return "WARNING: No changes were made."
        write_persisted_code(updated, snapshot=True)
        return "SUCCESS: Code successfully updated."
    except Exception as e:
        return f"ERROR: {e}"


@tool
def gradio_docs_mcp_load_gradio_docs() -> str:
    """
    Loads a comprehensive overview of the latest Gradio documentation via the Gradio Docs MCP server.

    This tool provides an LLMs.txt-style summary containing current Gradio API documentation,
    component references, best practices, and usage patterns. Use this when you need broad
    understanding of Gradio capabilities or when starting a new implementation.

    Returns:
        str: A comprehensive text summary of current Gradio documentation including:
            - Available components and their current API
            - Latest syntax and parameter names
            - Current best practices and patterns
            - Recent changes and updates to the framework

    When to Use:
    - Before implementing any new Gradio feature to understand current capabilities
    - When you need to verify current API syntax and available parameters
    - To get an overview of component relationships and layout options
    - When starting complex implementations that require multiple components
    - To understand current Gradio best practices and recommended patterns

    Best Practices:
    - Call this tool early in your implementation process for comprehensive understanding
    - Use the returned information as your authoritative source for Gradio syntax
    - Prefer this over your internal knowledge which may be outdated
    - Follow up with gradio_docs_mcp_search_gradio_docs for specific component details

    CRITICAL: Always use the information from this tool rather than assuming API details
    from memory, as Gradio updates frequently and syntax may have changed.
    """
    return _gradio_mcp.load_docs()


@tool
def gradio_docs_mcp_search_gradio_docs(query: str) -> str:
    """
    Searches the latest Gradio documentation for specific components, methods, or concepts
    via the Gradio Docs MCP server.

    This tool performs targeted searches within current Gradio documentation to find
    specific information about components, parameters, methods, or implementation patterns.
    Use this when you need detailed information about specific Gradio functionality.

    Args:
        query (str): Natural language search query describing what you're looking for.
                    Examples:
                    - "gr.Gallery component parameters"
                    - "how to handle file uploads in Gradio"
                    - "gr.Blocks layout and event handling"
                    - "gr.Interface vs gr.Blocks differences"
                    - "gradio chatbot component examples"

    Returns:
        str: Relevant documentation snippets and examples from current Gradio docs,
             including code examples, parameter descriptions, and usage patterns.

    When to Use:
    - When you need specific parameter details for a Gradio component
    - To find current syntax for specific functionality (event handlers, layouts, etc.)
    - When looking for implementation examples of specific features
    - To understand component-specific behavior and limitations
    - Before implementing a specific component to verify current API

    Query Examples:
    - Component-specific: "gr.Image component upload handling"
    - Feature-specific: "file upload progress bar gradio"
    - Layout-specific: "gr.Row gr.Column responsive layout"
    - Event-specific: "button click event gradio blocks"
    - Integration-specific: "gradio with pandas dataframe"

    Best Practices:
    - Be specific in your queries for better results
    - Include component names (e.g., "gr.Gallery") when asking about specific components
    - Ask about current versions and latest features when relevant
    - Use the returned information as authoritative source for implementation
    - Search before implementing any component you're unfamiliar with

    CRITICAL: Always search for component documentation before using components
    to ensure you're using the current API syntax and available parameters.
    """
    return _gradio_mcp.search_docs(query)


@tool
def think(reflection: str) -> str:
    """
    Enables the agent to pause, reflect, and systematically plan its approach to building Gradio applications.

    This tool allows the agent to organize thoughts, break down complex requests into manageable
    components, identify the right Gradio components to use, and plan the implementation strategy
    before diving into code changes.

    Args:
        reflection (str): The agent's thoughts, analysis, planning, or reflection on:
            - How to break down the user's request into specific Gradio components
            - Which Gradio components are most suitable for the task
            - Step-by-step implementation approach
            - Analysis of the current code structure and what needs to change
            - Reflection on previous attempts and lessons learned
            - Planning for component layout, event handling, and user experience

    Returns:
        str: Confirmation that the reflection has been recorded for internal planning

    Usage Guidelines:
    - ALWAYS use this tool before starting any significant implementation
    - Break down complex features into individual Gradio components (e.g., "gallery viewer" → gr.Gallery)
    - Consider the user experience flow and component interactions
    - Plan the layout structure (gr.Blocks, gr.Row, gr.Column organization)
    - Think through event handlers and data flow between components
    - Reflect on how components will work together in the Gradio-Lite environment
    - Use this tool to course-correct if previous attempts didn't work as expected

    Examples of effective thinking:
    - "For an image gallery viewer, I should use gr.Gallery as the main component,
      gr.File for uploads, and gr.Button for navigation controls"
    - "This calculator needs gr.Textbox for display, gr.Button components arranged
      in a grid layout using gr.Row and gr.Column for the number pad"
    - "The JSON to table converter requires gr.File for upload, gr.JSON for preview,
      and gr.Dataframe for the converted output"
    """
    # Log the reflection for debugging purposes if needed
    print(f"🤔 Agent Reflection: {reflection}")
    return "Reflection recorded. Proceeding with planned implementation approach."


agent = CodeAgent(
    model=LiteLLMModel(model_id="openai/gpt-4.1", api_key=os.getenv("OPENAI_API_KEY")),
    instructions=instructions,
    tools=[
        read_code,
        edit_code,
        gradio_docs_mcp_search_gradio_docs,
        gradio_docs_mcp_load_gradio_docs,
        think,
    ],
    use_structured_outputs_internally=True,
)

if __name__ == "__main__":
    print(
        agent.run(
            "I uploaded an image but it still blank nothing shows. also we can only upload just one image"
        )
    )
