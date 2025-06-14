import logging
import sys
import traceback

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static

from gmail_client import get_credentials


class GmailCtrlApp(App):
    """A Textual app to manage Gmail."""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Static("Authenticating... please check your browser.", id="auth-status")
        yield Footer()
        logging.info("App composed.")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        logging.info("App mounted. Initializing authentication.")
        self.run_worker(self.authenticate, exclusive=True)

    def authenticate(self) -> None:
        """Run the authentication process in a worker."""
        creds = get_credentials()
        if creds:
            self.query_one("#auth-status").update("Authentication successful.")
            logging.info("Authentication successful.")
        else:
            # This path should ideally not be reached due to the exception handling
            # in get_credentials, but it's here for completeness.
            self.query_one("#auth-status").update("[bold red]Authentication failed.[/]")
            logging.error("Authentication failed to return credentials.")

    def on_exception(self, exception: Exception) -> None:
        """Called when an unhandled exception is raised."""
        logging.critical("Unhandled exception occurred", exc_info=True)
        traceback.print_exc(file=sys.stderr)
        self.exit(1, f"Application error: {exception}")

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark
        logging.info(f"Dark mode toggled to {self.dark}")


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="gmailctrl.log",
        filemode="w",
    )
    logging.info("Application starting up.")
    app = GmailCtrlApp()
    app.run()
    logging.info("Application shutting down.")


if __name__ == "__main__":
    main()
