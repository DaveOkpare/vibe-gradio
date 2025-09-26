import os
import time
from smolagents import CodeAgent, LiteLLMModel, tool

from phoenix.otel import register

# configure the Phoenix tracer
tracer_provider = register(
    endpoint=os.getenv("PHOENIX_ENDPOINT"),
    project_name="gradio",  # Default is 'default'
    auto_instrument=True,  # Auto-instrument your app based on installed OI dependencies
)

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


agent = CodeAgent(
    model=LiteLLMModel(model_id="openai/gpt-4.1", api_key=os.getenv("OPENAI_API_KEY")),
    instructions=instructions,
    tools=[read_code, edit_code],
    use_structured_outputs_internally=True,  # Enable structured output
)
