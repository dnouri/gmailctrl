from textual.app import App
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable

from gmail_client import EmailGroup


class SenderListScreen(Screen):
    """The main screen displaying the list of email groups."""

    BINDINGS = [("ctrl+r", "refresh", "Refresh")]

    def __init__(self, email_groups: list[EmailGroup]):
        self.email_groups = email_groups
        super().__init__()

    def compose(self):
        yield Header()
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table when the screen is mounted."""
        self.populate_table()

    def populate_table(self) -> None:
        """Populate the DataTable with email group information."""
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns(
            "Sender", "Emails", "Latest Subject", "Newest Date", "Unsubscribe"
        )

        # Sort groups by the email count, descending
        sorted_groups = sorted(self.email_groups, key=lambda g: g.count, reverse=True)

        for group in sorted_groups:
            unsubscribe_tag = "[U]" if group.has_unsubscribe else ""
            sender_display = group.sender_name or group.sender_email
            table.add_row(
                sender_display,
                group.count,
                group.newest_subject,
                group.newest_date.strftime("%Y-%m-%d"),
                unsubscribe_tag,
                key=group.sender_email,
            )

    def action_refresh(self) -> None:
        """Handle the refresh action."""
        self.app.action_refresh_scan()
