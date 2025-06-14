from textual import on
from textual.app import App
from textual.containers import VerticalScroll, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static, Button

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
        self.query_one(DataTable).focus()

    def populate_table(self) -> None:
        """Populate the DataTable with email group information."""
        table = self.query_one(DataTable)
        table.clear(columns=True)
        # Use fixed column widths to prevent long text from pushing columns off-screen.
        table.add_column("Sender", width=35)
        table.add_column("Emails", width=8)
        table.add_column("Latest Subject", width=50)
        table.add_column("Newest Date", width=12)
        table.add_column("Unsubscribe", width=12)

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

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle the user selecting a row in the DataTable."""
        sender_email = event.row_key.value
        selected_group = next(
            (g for g in self.email_groups if g.sender_email == sender_email), None
        )
        if selected_group:
            self.app.push_screen(GroupDetailScreen(selected_group))


class GroupDetailScreen(Screen):
    """The screen showing details for a single email group."""

    def __init__(self, email_group: EmailGroup):
        self.email_group = email_group
        super().__init__()

    def compose(self):
        yield Header()
        with VerticalScroll():
            yield Static(id="summary")
            yield DataTable(id="email-list")
        with Horizontal():
            yield Button("Archive All", variant="primary", id="archive")
            yield Button("Delete All", variant="error", id="delete")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the widgets with group details."""
        summary = self.query_one("#summary")
        summary.update(self.get_summary_text())

        table = self.query_one("#email-list", DataTable)
        # Use fixed column widths here as well for consistency.
        table.add_column("Subject", width=80)
        table.add_column("Date", width=20)

        sorted_emails = sorted(
            self.email_group.emails, key=lambda e: e.date, reverse=True
        )
        for email in sorted_emails:
            table.add_row(email.subject, email.date.strftime("%Y-%m-%d %H:%M"))

    def get_summary_text(self) -> str:
        """Generates the summary text for the selected group."""
        g = self.email_group
        return f"""\
Sender:        {g.sender_name} <{g.sender_email}>
Count:         {g.count}
Date Range:    {g.oldest_date.strftime('%Y-%m-%d')} to {g.newest_date.strftime('%Y-%m-%d')}
Attachments:   {g.total_attachments}
Unsubscribe:   {'Yes' if g.has_unsubscribe else 'No'}
"""
