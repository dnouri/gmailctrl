from typing import Callable

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal, Grid
from textual.screen import Screen, ModalScreen
from textual.widgets import Header, Footer, DataTable, Static, Button

from gmail_client import EmailGroup


class ConfirmationScreen(ModalScreen[bool]):
    """A modal screen to confirm an action."""

    def __init__(self, prompt: str):
        self.prompt = prompt
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Grid(
            Static(self.prompt, id="confirmation-prompt"),
            Horizontal(
                Button("Confirm", variant="primary", id="confirm"),
                Button("Cancel", variant="default", id="cancel"),
                classes="buttons",
            ),
            id="confirmation-dialog",
        )

    def on_mount(self) -> None:
        """Focus the confirm button when the screen is mounted."""
        self.query_one("#confirm", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss the screen, returning True if 'Confirm' was pressed."""
        self.dismiss(event.button.id == "confirm")


class SenderListScreen(Screen):
    """The main screen displaying the list of email groups."""

    BINDINGS = [
        ("a", "archive_selected", "Archive"),
        ("d", "delete_selected", "Delete"),
        ("ctrl+r", "refresh", "Refresh"),
        ("space", "toggle_selection", "Toggle Selection"),
    ]

    def __init__(self, email_groups: list[EmailGroup]):
        self.email_groups = email_groups
        self.selected_rows = set()
        super().__init__()

    def compose(self):
        yield Header()
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table when the screen is mounted."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        self.populate_table()
        table.focus()

    def populate_table(self) -> None:
        """Populate the DataTable with email group information."""
        table = self.query_one(DataTable)
        table.clear(columns=True)
        # Add a checkbox column for selection and adjust other column widths.
        table.add_column("✓", key="selected", width=3)
        table.add_column("Sender", width=35)
        table.add_column("Emails", width=8)
        table.add_column("Latest Subject", width=47)
        table.add_column("Newest Date", width=12)
        table.add_column("Unsubscribe", width=12)

        # Sort groups by the email count, descending
        sorted_groups = sorted(self.email_groups, key=lambda g: g.count, reverse=True)

        for group in sorted_groups:
            unsubscribe_tag = "[U]" if group.has_unsubscribe else ""
            sender_display = group.sender_name or group.sender_email
            table.add_row(
                escape("[ ]"),  # Checkbox starts as unchecked
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

    def action_toggle_selection(self) -> None:
        """Toggles the selection state of the currently focused row."""
        table = self.query_one(DataTable)
        if not table.row_count:
            return

        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)

        if row_key in self.selected_rows:
            self.selected_rows.remove(row_key)
            table.update_cell(row_key, "selected", escape("[ ]"))
        else:
            self.selected_rows.add(row_key)
            table.update_cell(row_key, "selected", escape("[x]"))

    def _handle_bulk_action(self, action: str) -> None:
        """Generic handler for archive/delete actions on selected rows."""
        if not self.selected_rows:
            self.app.bell()
            return

        selected_groups = [
            g for g in self.email_groups if g.sender_email in self.selected_rows
        ]
        email_ids = [email.id for group in selected_groups for email in group.emails]

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self.app.perform_bulk_action(email_ids, action)

        prompt = f"{action.capitalize()} {len(email_ids)} emails from {len(selected_groups)} senders?"
        self.app.push_screen(ConfirmationScreen(prompt), on_confirm)

    def action_archive_selected(self) -> None:
        """Trigger archive for selected rows."""
        self._handle_bulk_action("archive")

    def action_delete_selected(self) -> None:
        """Trigger delete for selected rows."""
        self._handle_bulk_action("delete")

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
            yield Button("Back", id="back")
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

    @on(Button.Pressed, "#back")
    def on_button_pressed_back(self, event: Button.Pressed) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

    def _handle_action(self, action: str) -> None:
        """Generic handler for archive/delete actions on the current group."""
        email_ids = [email.id for email in self.email_group.emails]

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self.app.pop_screen()
                self.app.perform_bulk_action(email_ids, action)

        prompt = f"{action.capitalize()} all {self.email_group.count} emails from {self.email_group.sender_email}?"
        self.app.push_screen(ConfirmationScreen(prompt), on_confirm)

    @on(Button.Pressed, "#archive")
    def on_button_pressed_archive(self, event: Button.Pressed) -> None:
        """Handle archive button press."""
        self._handle_action("archive")

    @on(Button.Pressed, "#delete")
    def on_button_pressed_delete(self, event: Button.Pressed) -> None:
        """Handle delete button press."""
        self._handle_action("delete")
