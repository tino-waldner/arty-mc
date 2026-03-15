import sys

from textual.app import App  # type: ignore

from arty_mc.config import load_config
from arty_mc.ui.commander_screen import CommanderScreen


class ArtyMc(App):
    TITLE = "Arty-Mc"

    def __init__(self, repo):
        super().__init__()
        self.repo = repo

    def on_mount(self):
        config = load_config()
        config["default_repo"] = self.repo
        self.push_screen(CommanderScreen(config))


def print_usage():
    print("Usage:")
    print("     arty-mc <repository>")
    print("Options:")
    print("     --help        Show this help message")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print_usage()
        sys.exit(0)

    repo = sys.argv[1]
    app = ArtyMc(repo)
    app.run()


if __name__ == "__main__":
    main()
