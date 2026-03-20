import sys

from textual.app import App  # type: ignore

from arty_mc.config import load_config
from arty_mc.ui.commander_screen import CommanderScreen
from arty_mc.ui.error_dialog import ErrorDialog


class ArtyMc(App):
    TITLE = "Arty-Mc"

    def __init__(self, repo):
        super().__init__()
        self.repo = repo

    def on_mount(self):
        try:
            config = load_config()
        except RuntimeError as e:

            def on_dismiss():
                self.exit()

            self.push_screen(
                ErrorDialog(str(e), title="Configuration Error"),
                callback=lambda _: on_dismiss(),
            )
            return
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


if __name__ == "__main__":  # pragma: no cover
    main()
