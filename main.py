import argparse
import logging
import sys
import traceback
from typing import List, Optional

from google.oauth2.credentials import Credentials
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, LoadingIndicator, ProgressBar

from gmail_client import (
    get_credentials,
    fetch_emails,
    analyze_and_group_emails,
    EmailGroup,
)
from screens import SenderListScreen


class GmailCtrlApp(App):
    """A Textual app to manage Gmail."""

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit"),
    ]

    creds: Credentials | None = None
    email_groups: List[EmailGroup] | None = None

    def __init__(self, limit: Optional[int] = None):
        super().__init__()
        self.limit = limit

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield LoadingIndicator()
        yield ProgressBar()
        yield Static("Initializing...", id="loading-status")
        yield Footer()
        logging.info("App composed.")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        logging.info("App mounted. Starting initial scan.")
        self.run_worker(self.perform_initial_scan, exclusive=True, thread=True)

    def show_loading_indicator(self, show: bool) -> None:
        """Shows or hides the loading indicator and status message."""
        self.query_one(LoadingIndicator).display = show
        self.query_one(ProgressBar).display = show
        self.query_one("#loading-status").display = show

    def update_status(self, message: str) -> None:
        """Helper method to update the status Static widget from any thread."""
        logging.info(f"UI Status Update: {message}")

        def do_update() -> None:
            self.query_one("#loading-status", Static).update(message)

        self.call_from_thread(do_update)

    def update_progress(self, progress: int, total: int) -> None:
        """Helper method to update the progress bar from any thread."""

        def do_update() -> None:
            self.query_one(ProgressBar).update(total=total, progress=progress)

        self.call_from_thread(do_update)

    def perform_initial_scan(self) -> None:
        """Worker that handles authentication and initial email fetching."""
        self.update_status("Authenticating... please check your browser if needed.")
        self.creds = get_credentials()
        logging.info("Authentication successful.")

        emails = fetch_emails(
            creds=self.creds,
            status_callback=self.update_status,
            progress_callback=self.update_progress,
            limit=self.limit,
        )
        self.email_groups = analyze_and_group_emails(
            emails=emails,
            status_callback=self.update_status,
            progress_callback=self.update_progress,
        )

        # Hide loading indicator and push the main screen
        self.call_from_thread(self.show_loading_indicator, False)
        self.call_from_thread(self.push_screen, SenderListScreen(self.email_groups))

    def perform_refresh_scan(self) -> None:
        """Worker that handles refreshing the email data."""
        emails = fetch_emails(
            creds=self.creds,
            status_callback=self.update_status,
            progress_callback=self.update_progress,
            limit=self.limit,
        )
        self.email_groups = analyze_and_group_emails(
            emails=emails,
            status_callback=self.update_status,
            progress_callback=self.update_progress,
        )

        # Hide loading indicator and push the new main screen
        self.call_from_thread(self.show_loading_indicator, False)
        self.call_from_thread(self.push_screen, SenderListScreen(self.email_groups))

    def action_refresh_scan(self) -> None:
        """Starts the refresh worker."""
        self.pop_screen()
        self.show_loading_indicator(True)
        self.run_worker(self.perform_refresh_scan, exclusive=True, thread=True)

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
    parser = argparse.ArgumentParser(description="A TUI to manage bulk email in Gmail.")
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of recent emails to fetch. For faster development loops.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="gmailctrl.log",
        filemode="w",
    )
    logging.info("Application starting up.")
    app = GmailCtrlApp(limit=args.limit)
    app.run()
    logging.info("Application shutting down.")


if __name__ == "__main__":
    main()
