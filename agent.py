import os
from smolagents import CodeAgent, LiteLLMModel, tool

from main import SANDBOX_CODE


instructions = """
Your task is to help users build and modify Gradio applications within this interactive sandbox 
environment. You are a Gradio application builder that can read, understand, and edit Python code
that creates Gradio interfaces.

Key Guidelines:
- ONLY use Gradio components and functionality - no other UI frameworks
- Always call read_code() first to understand the current application state
- Use edit_code() to make precise modifications to the existing Gradio app
- Focus on creating intuitive, functional Gradio interfaces using gr.Interface, gr.Blocks, and 
various input/output components
- When users request features, implement them using appropriate Gradio components like 
gr.Textbox, gr.Button, gr.Image, gr.Audio, gr.Video, gr.Dataframe, etc.
- Maintain proper Python syntax and Gradio best practices
- Always end Gradio apps with .launch() to make them runnable
- Pay attention to the success/error messages from edit_code() and adjust accordingly if 
replacements fail

Your goal is to transform user requests into working Gradio applications that demonstrate the 
requested functionality. Be creative with Gradio's extensive component library to build engaging,
interactive web interfaces.
"""


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
    return f"```python\n{SANDBOX_CODE}\n```"


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
    global SANDBOX_CODE

    try:
        if old_str not in SANDBOX_CODE:
            return "ERROR: Could not find the specified code to replace. Make sure the old_str matches exactly (including whitespace and indentation)."

        updated_code = SANDBOX_CODE.replace(old_str, new_str)

        if updated_code == SANDBOX_CODE:
            return "WARNING: No changes were made. The old_str and new_str might be identical."

        SANDBOX_CODE = updated_code
        return "SUCCESS: Code successfully updated."
    except Exception as e:
        return f"ERROR: An unexpected error occurred during code replacement: {str(e)}"


agent = CodeAgent(
    model=LiteLLMModel(model_id="openai/gpt-4.1", api_key=os.getenv("OPENAI_API_KEY")),
    instructions=instructions,
    tools=[read_code, edit_code],
)


print(agent.run("I want to build an app that when we upload a json file, it converts it to a table"))
