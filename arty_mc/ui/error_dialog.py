from textual.containers import Vertical  # type: ignore
from textual.screen import ModalScreen  # type: ignore
from textual.widgets import Button, Label  # type: ignore


class ErrorDialog(ModalScreen):
    DEFAULT_CSS = """
    ErrorDialog {
        align: center middle;
    }

    #dialog {
        width: 100%;
        max-width: 80;
        min-width: 30;
        height: auto;
        max-height: 16;
        border: round red;
        padding: 1 2;
        background: #1f1f1f;
        align-horizontal: center;
    }

    #title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
        content-align: center middle;
        width: 100%;
    }

    #message {
        margin-bottom: 1;
        content-align: center middle;
        width: 100%;
    }

    #ok-btn {
        margin-top: 1;
        min-width: 8;
        align-horizontal: center;
    }
    """

    def __init__(self, message: str, title: str = "Error"):
        super().__init__()
        self.message = message
        self.title_text = title

    def compose(self):
        with Vertical(id="dialog"):
            yield Label(self.title_text, id="title")
            yield Label(self.message, id="message")
            yield Button("OK", id="ok-btn", variant="error")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "ok-btn":
            self.dismiss()
