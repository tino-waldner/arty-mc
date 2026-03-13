import sys
from textual.app import App

from config import load_config
from ui.commander_screen import CommanderScreen


class artymc(App):
    TITLE = "Arty-Mc"
    def __init__(self, repo):
        super().__init__()
        self.repo = repo

    def on_mount(self):
        config = load_config()
        config["default_repo"] = self.repo

        self.push_screen(
            CommanderScreen(config)
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("     python arty-mc.py <repository>")
        sys.exit(1)

    repo = sys.argv[1]
    app = artymc(repo)
    app.run()
