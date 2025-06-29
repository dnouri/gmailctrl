import argparse
import logging
import sys
import time
import traceback
from collections import defaultdict
from typing import List, Optional

from google.oauth2.credentials import Credentials
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, LoadingIndicator, ProgressBar

import file_handler
from gmail_client import (
    get_credentials,
    fetch_emails,
    analyze_and_group_emails,
    EmailGroup,
    bulk_archive_emails,
    bulk_delete_emails,
    fetch_attachment_metadata,
    download_single_attachment,
)
from screens import (
    SenderListScreen,
    MainMenuScreen,
    DaysInputScreen,
    DownloadProgressScreen,
    DownloadSummaryScreen,
)


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
        logging.info("App mounted. Starting authentication.")
        self.run_worker(self.authenticate, exclusive=True, thread=True)

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

    def authenticate(self) -> None:
        """Worker that handles authentication."""
        self.update_status("Authenticating... please check your browser if needed.")
        self.creds = get_credentials()
        logging.info("Authentication successful.")

        # Hide loading indicator and push the main menu screen
        self.call_from_thread(self.show_loading_indicator, False)
        self.call_from_thread(self.push_screen, MainMenuScreen())

    def action_manage_emails(self) -> None:
        """Starts the email management flow."""
        self.pop_screen()
        self.show_loading_indicator(True)
        self.run_worker(self.perform_initial_scan, exclusive=True, thread=True)

    def action_download_attachments_start(self) -> None:
        """Starts the attachment download flow by asking for days."""

        def on_days_selected(days: int | None) -> None:
            if days:
                logging.info(f"User wants to download attachments from last {days} days.")

                def worker() -> None:
                    """Worker that calls the download method with the selected days."""
                    self.perform_attachment_download(days)

                self.run_worker(worker, exclusive=True, thread=True)

        self.push_screen(DaysInputScreen(), on_days_selected)

    def action_goto_main_menu(self) -> None:
        """Pops the current screen to return to the main menu."""
        self.pop_screen()

    def perform_initial_scan(self) -> None:
        """Worker that handles fetching and analyzing emails."""
        if not self.creds:
            logging.error("perform_initial_scan called without credentials.")
            self.update_status("Error: Not authenticated.")
            return

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
        self.pop_screen()
        self.show_loading_indicator(True)
        self.perform_initial_scan()

    def action_refresh_scan(self) -> None:
        """Starts the refresh worker."""
        self.run_worker(self.perform_refresh_scan, exclusive=True, thread=True)

    def perform_attachment_download(self, days: int) -> None:
        """Worker that handles attachment download."""
        self.call_from_thread(self.pop_screen)  # Pop DaysInputScreen
        self.call_from_thread(self.push_screen, DownloadProgressScreen())

        summary_data = {}
        error = None
        try:
            # Step 1: Fetch metadata for all attachments.
            attachments = fetch_attachment_metadata(
                creds=self.creds,
                days=days,
                status_callback=self.update_status,
                progress_callback=self.update_progress,
            )

            if not attachments:
                self.update_status("No new attachments found to download.")
                self.call_from_thread(
                    self.query_one(ProgressBar).update, total=1, progress=1
                )
                time.sleep(2)  # Give user time to read the message
            else:
                total_attachments = len(attachments)
                self.update_status(
                    f"Found {total_attachments} attachments. Starting download."
                )
                logging.info(
                    f"Found {total_attachments} attachments. Starting download."
                )

                # Step 2: Loop through metadata and download each attachment.
                summary = defaultdict(lambda: {"count": 0, "size": 0})
                for i, att in enumerate(attachments):
                    self.update_status(
                        f"Downloading '{att.filename}' ({i + 1}/{total_attachments})"
                    )
                    self.update_progress(i + 1, total_attachments)

                    # Download the actual attachment content.
                    content = download_single_attachment(
                        creds=self.creds,
                        message_id=att.message_id,
                        attachment_id=att.attachment_id,
                    )

                    # Save the attachment using the file handler.
                    file_handler.save_attachment(
                        content=content,
                        sender=att.sender,
                        original_filename=att.filename,
                        email_date=att.email_date,
                    )

                    # Update summary data.
                    summary[att.sender]["count"] += 1
                    summary[att.sender]["size"] += att.size

                summary_data = dict(summary)
                self.update_status("Download process completed successfully.")
                logging.info("Download process completed successfully.")
                time.sleep(1)  # Brief pause on completion

        except Exception as e:
            logging.error(f"Error during attachment download: {e}", exc_info=True)
            # The error will be displayed on the summary screen.
            error = f"An error occurred: {e}"
            self.update_status(error)
            time.sleep(2)  # Show error before switching screen

        # Step 3: Show the summary screen.
        self.call_from_thread(self.pop_screen)  # Pop DownloadProgressScreen
        self.call_from_thread(
            self.push_screen, DownloadSummaryScreen(summary_data, error)
        )

    def perform_bulk_action(self, email_ids: List[str], action: str) -> None:
        """
        Shows loading indicator and runs a bulk action (archive/delete) in a worker.
        Refreshes the list upon completion.
        """
        self.pop_screen()
        self.show_loading_indicator(True)

        def worker() -> None:
            """The work to be done in the background."""
            action_name_capitalized = action.capitalize()
            self.update_status(
                f"{action_name_capitalized}ing {len(email_ids)} emails..."
            )

            action_func = (
                bulk_archive_emails if action == "archive" else bulk_delete_emails
            )
            action_func(
                creds=self.creds,
                email_ids=email_ids,
                status_callback=self.update_status,
                progress_callback=self.update_progress,
            )

            # After the action is complete, run the refresh logic.
            self.perform_initial_scan()

        self.run_worker(worker, exclusive=True, thread=True)

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
    parser = argparse.ArgumentParser(
        description="A TUI to manage bulk email in Gmail."
    )
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
