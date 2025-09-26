import gradio as gr


def greet(name):
    return "Hello, " + name + "!!!"


gr.Interface(greet, "textbox", "textbox").launch()
