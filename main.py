import logging
import sys
import traceback

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static

from gmail_client import get_credentials, fetch_emails, analyze_and_group_emails


class GmailCtrlApp(App):
    """A Textual app to manage Gmail."""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Static("Initializing...", id="auth-status")
        yield Footer()
        logging.info("App composed.")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        logging.info("App mounted. Starting login and fetch process.")
        self.run_worker(self.login_and_fetch, exclusive=True, thread=True)

    def update_status(self, message: str) -> None:
        """Helper method to update the status Static widget from any thread."""
        logging.info(f"UI Status Update: {message}")
        # Use call_from_thread to ensure UI updates happen on the main thread.
        self.call_from_thread(self.query_one("#auth-status").update, message)

    def login_and_fetch(self) -> None:
        """Worker that handles authentication and initial email fetching."""
        # The get_credentials function handles the entire OAuth flow, including
        # browser interaction and token refreshing. It will raise an exception
        # on failure (e.g., credentials.json not found), which will be
        # caught by the app's on_exception handler.
        self.update_status("Authenticating... please check your browser if needed.")
        creds = get_credentials()
        logging.info("Authentication successful.")

        # Now, fetch emails using the obtained credentials.
        # The fetch_emails function will use the status_callback to post
        # progress updates to the UI.
        emails = fetch_emails(creds=creds, status_callback=self.update_status)

        # Analyze and group the fetched emails.
        email_groups = analyze_and_group_emails(
            emails=emails, status_callback=self.update_status
        )

        # For now, just log the result for verification.
        # In the next milestone, we'll display this in the UI.
        if email_groups:
            logging.info("Top 5 email groups found:")
            # Sort groups by count for logging purposes
            sorted_groups = sorted(email_groups, key=lambda g: g.count, reverse=True)
            for group in sorted_groups[:5]:
                logging.info(
                    f"  - Sender: {group.sender_email}, Count: {group.count}, "
                    f"Newest: {group.newest_date.strftime('%Y-%m-%d')}"
                )

        final_message = (
            f"Scan complete. Found {len(emails)} emails from "
            f"{len(email_groups)} senders."
        )
        self.update_status(final_message)
        logging.info(final_message)

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
