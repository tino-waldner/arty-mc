from textual import on  # type: ignore
from textual.message import Message  # type: ignore
from textual.widget import Widget  # type: ignore
from textual.widgets import Input  # type: ignore


class FilterBar(Widget):
    DEFAULT_CSS = """
    FilterBar {
        height: 3;
    }

    FilterBar Input {
        width: 100%;
    }
    """

    class Changed(Message):
        def __init__(self, sender, value: str):
            super().__init__()
            self.sender = sender
            self.value = value

    def compose(self):
        self.input = Input(placeholder="Filter (* wildcard)")
        yield self.input

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        self.post_message(self.Changed(self, event.value))
