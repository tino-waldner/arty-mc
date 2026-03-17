from textual import (  # type: ignore
    events,  # type: ignore
    on,  # type: ignore
)  # type: ignore
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

    def on_input_submitted(self, event):
        self.app.set_focus(self.app.screen.get_active())  # type: ignore[attr-defined]

    def on_key(self, event: events.Key) -> None:
        if event.key == "tab":
            event.stop()
            self.app.set_focus(self.app.screen.get_active())  # type: ignore[attr-defined]
