import base64
import gradio as gr

# Initial inner Gradio-Lite app (editable at runtime in the UI)
INITIAL_INNER_PY = """
import gradio as gr

def greet(name):
    return "Hello, " + name + "!!!"

gr.Interface(greet, 'textbox', 'textbox').launch()
"""


def build_srcdoc(py_code: str) -> str:
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <script type="module" crossorigin src="https://cdn.jsdelivr.net/npm/@gradio/lite/dist/lite.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@gradio/lite/dist/lite.css" />
  </head>
  <body>
    <gradio-lite>
{py_code}
    </gradio-lite>
  </body>
</html>"""


def make_iframe_html(py_code: str, height: int = 650) -> str:
    srcdoc = build_srcdoc(py_code)
    b64 = base64.b64encode(srcdoc.encode("utf-8")).decode()
    return (
        f'<iframe loading="lazy" referrerpolicy="no-referrer" '
        f'sandbox="allow-scripts allow-same-origin" '
        f'style="width:100%;height:{height}px;border:0" '
        f'src="data:text/html;base64,{b64}"></iframe>'
    )


def chat(message, history):
    if "python" in message.lower():
        return "Type Python or JavaScript to see the code.", gr.Code(
            language="python", value=python_code
        )
    elif "javascript" in message.lower():
        return "Type Python or JavaScript to see the code.", gr.Code(
            language="javascript", value=js_code
        )
    else:
        return "Please ask about Python or JavaScript.", None


with gr.Blocks() as demo:
    frame = gr.HTML(
        make_iframe_html(INITIAL_INNER_PY),
        render=False,
    )
    with gr.Row():
        with gr.Column():
            gr.Markdown("<center><h1>Write Python or JavaScript</h1></center>")
            gr.ChatInterface(
                chat,
                examples=["Python", "JavaScript"],
                additional_outputs=[frame],
                type="messages",
            )
        with gr.Column():
            gr.Markdown("<center><h1>Code Artifacts</h1></center>")
            frame.render()

demo.launch()
