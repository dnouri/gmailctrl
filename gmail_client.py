import base64
import logging
import os.path
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"
GMAIL_API_BATCH_SIZE = 100


@dataclass
class IndividualEmail:
    """Represents a single email's metadata."""

    id: str
    subject: str
    date: datetime


@dataclass
class EmailGroup:
    """Represents a group of emails from a single sender."""

    sender_name: str
    sender_email: str
    count: int
    oldest_date: datetime
    newest_date: datetime
    newest_subject: str
    total_attachments: int
    has_unsubscribe: bool
    emails: List[IndividualEmail]


@dataclass
class AttachmentMetadata:
    """Represents the metadata for a single downloadable attachment."""

    message_id: str
    attachment_id: str
    sender: str
    email_date: datetime
    filename: str
    size: int


def get_credentials() -> Credentials:
    """
    Gets user credentials for the Gmail API.

    Handles the OAuth 2.0 flow, including token storage and refresh.
    """
    logging.info("Attempting to get Gmail API credentials.")
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_PATH):
        logging.info(f"Found existing token file at {TOKEN_PATH}.")
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Credentials expired, attempting to refresh.")
            creds.refresh(Request())
            logging.info("Credentials refreshed successfully.")
        else:
            logging.info("No valid credentials found, starting OAuth flow.")
            if not os.path.exists(CREDENTIALS_PATH):
                logging.error(f"{CREDENTIALS_PATH} not found. Cannot authenticate.")
                raise FileNotFoundError(
                    f"'{CREDENTIALS_PATH}' not found. Please download your OAuth 2.0 "
                    "Client ID JSON file from the Google Cloud Console and place it "
                    "in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(
                port=0,
                authorization_prompt_message="",
                success_message="Authentication successful. You can close this tab.",
            )
            logging.info("OAuth flow completed and credentials obtained.")

        # Save the credentials for the next run
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
        logging.info(f"Credentials saved to {TOKEN_PATH}.")

    logging.info("Successfully obtained credentials.")
    return creds


def _get_header(headers: List[Dict[str, str]], name: str) -> str:
    """Extracts a header value from a list of headers."""
    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]
    return ""


def fetch_emails(
    creds: Credentials,
    status_callback: Callable[[str], None],
    progress_callback: Callable[[int, int], None],
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches a list of emails from the user's inbox using the Gmail API.
    This function handles pagination to retrieve all emails up to an optional limit.

    Args:
        creds: Authorized Google API credentials.
        status_callback: A callable to send status updates to the UI.
        progress_callback: A callable to send progress updates to the UI.
        limit: An optional maximum number of emails to fetch.

    Returns:
        A list of email message resources, or an empty list if none are found.
    """
    logging.info("Building Gmail service.")
    service = build("gmail", "v1", credentials=creds)

    status_callback("Fetching email list from INBOX...")
    logging.info("Fetching message IDs from INBOX.")

    messages = []
    page_token = None
    page_count = 0
    while True:
        page_count += 1
        status_callback(f"Fetching email list from INBOX (page {page_count})...")
        request = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX"], pageToken=page_token)
        )
        response = request.execute()
        messages.extend(response.get("messages", []))
        page_token = response.get("nextPageToken")

        if not page_token or (limit and len(messages) >= limit):
            break

    if limit:
        messages = messages[:limit]

    if not messages:
        logging.info("No messages found in INBOX.")
        status_callback("No new messages found.")
        return []

    msg_count = len(messages)
    status_callback(f"Found {msg_count} emails. Fetching details...")
    logging.info(
        f"Found {msg_count} message IDs. Fetching details in batches of {GMAIL_API_BATCH_SIZE}."
    )

    emails: List[Dict[str, Any]] = []

    def batch_callback(request_id, response, exception):
        if exception:
            # A single failed request in a batch should not halt the entire process.
            # We log the error and continue with the other results.
            # The exception is not raised, as per google-api-python-client design.
            logging.error(f"Batch request {request_id} failed: {exception}")
        else:
            emails.append(response)

    # Process messages in chunks, as the batch API has a limit.
    for i in range(0, msg_count, GMAIL_API_BATCH_SIZE):
        chunk = messages[i : i + GMAIL_API_BATCH_SIZE]
        processed_count = i + len(chunk)
        status_callback(f"Fetching details... ({processed_count}/{msg_count})")
        progress_callback(processed_count, msg_count)

        batch = service.new_batch_http_request(callback=batch_callback)
        for msg in chunk:
            batch.add(
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date", "List-Unsubscribe"],
                )
            )
        batch.execute()

    logging.info(
        f"Successfully fetched details for {len(emails)} out of {msg_count} emails."
    )
    return emails


def analyze_and_group_emails(
    emails: List[Dict[str, Any]],
    status_callback: Callable[[str], None],
    progress_callback: Callable[[int, int], None],
) -> List[EmailGroup]:
    """
    Analyzes a list of raw email data, grouping them by sender and calculating
    summary statistics for each group.

    Args:
        emails: A list of raw email message resources from the Gmail API.
        status_callback: A callable to send status updates to the UI.
        progress_callback: A callable to send progress updates to the UI.

    Returns:
        A list of EmailGroup objects, each representing a unique sender.
    """
    total_emails = len(emails)
    status_callback(f"Analyzing {total_emails} emails...")
    logging.info(f"Analyzing {total_emails} emails.")

    groups: Dict[str, EmailGroup] = {}

    for i, email_data in enumerate(emails):
        processed_count = i + 1
        if processed_count % 100 == 0:
            status_callback(f"Analyzing emails... ({processed_count}/{total_emails})")
        progress_callback(processed_count, total_emails)

        headers = email_data.get("payload", {}).get("headers", [])

        # Parse sender from the 'From' header.
        from_header = _get_header(headers, "From")
        sender_name, sender_email = parseaddr(from_header)
        if not sender_email:
            logging.warning(f"Could not parse sender from header: '{from_header}'")
            continue  # Skip emails where a sender email cannot be determined.

        # Parse the date and handle potential timezone issues.
        date_header = _get_header(headers, "Date")
        email_date = parsedate_to_datetime(date_header)

        # Normalize all datetime objects to be offset-aware and in UTC.
        if email_date.tzinfo is None:
            # If the parsed date is naive, assume it's UTC.
            email_date = email_date.replace(tzinfo=timezone.utc)
        else:
            # If it's aware, convert it to the UTC timezone.
            email_date = email_date.astimezone(timezone.utc)

        subject = _get_header(headers, "Subject")

        # Check for the presence of a List-Unsubscribe header.
        has_unsubscribe_header = bool(_get_header(headers, "List-Unsubscribe"))

        # Count attachments by checking for parts with a 'filename'.
        attachment_count = 0
        if "parts" in email_data.get("payload", {}):
            for part in email_data["payload"]["parts"]:
                if part.get("filename"):
                    attachment_count += 1

        email_id = email_data["id"]
        individual_email = IndividualEmail(id=email_id, subject=subject, date=email_date)

        # Create a new group or update an existing one.
        if sender_email not in groups:
            groups[sender_email] = EmailGroup(
                sender_name=sender_name or sender_email,
                sender_email=sender_email,
                count=1,
                oldest_date=email_date,
                newest_date=email_date,
                newest_subject=subject,
                total_attachments=attachment_count,
                has_unsubscribe=has_unsubscribe_header,
                emails=[individual_email],
            )
        else:
            group = groups[sender_email]
            group.count += 1
            group.total_attachments += attachment_count
            if email_date < group.oldest_date:
                group.oldest_date = email_date
            if email_date > group.newest_date:
                group.newest_date = email_date
                group.newest_subject = subject
            if has_unsubscribe_header:
                group.has_unsubscribe = True
            group.emails.append(individual_email)

    logging.info(f"Grouped emails into {len(groups)} unique senders.")
    return list(groups.values())


def _find_attachments_in_parts(parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Recursively search through message parts to find attachments."""
    attachments = []
    for part in parts:
        if part.get("filename") and part.get("body", {}).get("attachmentId"):
            attachments.append(part)
        if "parts" in part:
            attachments.extend(_find_attachments_in_parts(part["parts"]))
    return attachments


def fetch_attachment_metadata(
    creds: Credentials,
    days: int,
    status_callback: Callable[[str], None],
    progress_callback: Callable[[int, int], None],
) -> List[AttachmentMetadata]:
    """
    Fetches metadata for all attachments in emails within a given number of days.
    """
    logging.info(
        f"Starting fetch for attachment metadata from the last {days} days."
    )
    service = build("gmail", "v1", credentials=creds)
    query = f"has:attachment newer_than:{days}d"
    status_callback(f"Searching for emails with attachments from last {days} days...")

    messages = []
    page_token = None
    while True:
        request = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX"], q=query, pageToken=page_token)
        )
        response = request.execute()
        messages.extend(response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    if not messages:
        logging.info("No messages with attachments found for the given criteria.")
        status_callback("No attachments found.")
        return []

    msg_count = len(messages)
    status_callback(f"Found {msg_count} emails. Fetching details...")
    logging.info(f"Found {msg_count} emails with attachments. Fetching details.")

    full_emails: List[Dict[str, Any]] = []

    def batch_callback(request_id, response, exception):
        if exception:
            logging.error(f"Batch request {request_id} failed: {exception}")
        else:
            full_emails.append(response)

    for i in range(0, msg_count, GMAIL_API_BATCH_SIZE):
        chunk = messages[i : i + GMAIL_API_BATCH_SIZE]
        processed_count = i + len(chunk)
        status_callback(
            f"Fetching email details... ({processed_count}/{msg_count})"
        )
        progress_callback(processed_count, msg_count)

        batch = service.new_batch_http_request(callback=batch_callback)
        for msg in chunk:
            batch.add(
                service.users().messages().get(userId="me", id=msg["id"], format="full")
            )
        batch.execute()

    attachments_metadata: List[AttachmentMetadata] = []
    total_emails = len(full_emails)
    status_callback(f"Analyzing {total_emails} emails for attachments...")
    logging.info(f"Analyzing {total_emails} emails for attachment parts.")

    for i, email_data in enumerate(full_emails):
        progress_callback(i + 1, total_emails)
        headers = email_data.get("payload", {}).get("headers", [])
        _, sender_email = parseaddr(_get_header(headers, "From"))
        if not sender_email:
            continue

        email_date = parsedate_to_datetime(_get_header(headers, "Date"))
        if email_date.tzinfo is None:
            email_date = email_date.replace(tzinfo=timezone.utc)
        else:
            email_date = email_date.astimezone(timezone.utc)

        attachment_parts = []
        if "parts" in email_data.get("payload", {}):
            attachment_parts = _find_attachments_in_parts(
                email_data["payload"]["parts"]
            )

        for part in attachment_parts:
            attachments_metadata.append(
                AttachmentMetadata(
                    message_id=email_data["id"],
                    attachment_id=part["body"]["attachmentId"],
                    sender=sender_email,
                    email_date=email_date,
                    filename=part["filename"],
                    size=part["body"]["size"],
                )
            )

    logging.info(
        f"Found {len(attachments_metadata)} attachments in {total_emails} emails."
    )
    status_callback(f"Found {len(attachments_metadata)} attachments to download.")
    return attachments_metadata


def download_single_attachment(
    creds: Credentials, message_id: str, attachment_id: str
) -> bytes:
    """Downloads a single attachment and returns its raw byte content."""
    logging.info(
        f"Downloading attachment {attachment_id} from message {message_id}."
    )
    service = build("gmail", "v1", credentials=creds)
    request = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
    )
    attachment = request.execute()
    encoded_data = attachment["data"]
    # The data is base64url encoded, which is slightly different from standard base64.
    return base64.urlsafe_b64decode(encoded_data)


def _perform_bulk_action(
    creds: Credentials,
    email_ids: List[str],
    action_body: Dict[str, Any],
    status_callback: Callable[[str], None],
    progress_callback: Callable[[int, int], None],
    action_name: str,
) -> None:
    """Helper to perform a bulk action (archive, delete) on a list of emails."""
    service = build("gmail", "v1", credentials=creds)
    total_ids = len(email_ids)
    logging.info(f"Performing bulk {action_name} on {total_ids} emails.")

    # The batchModify endpoint can take up to 1000 IDs at a time, but we use
    # the same batch size as fetching for consistency.
    for i in range(0, total_ids, GMAIL_API_BATCH_SIZE):
        chunk = email_ids[i : i + GMAIL_API_BATCH_SIZE]
        processed_count = i + len(chunk)
        status_callback(
            f"{action_name.capitalize()} emails... ({processed_count}/{total_ids})"
        )
        progress_callback(processed_count, total_ids)
        body = {"ids": chunk, **action_body}
        service.users().messages().batchModify(userId="me", body=body).execute()

    logging.info(f"Bulk {action_name} completed for {total_ids} emails.")


def bulk_archive_emails(
    creds: Credentials,
    email_ids: List[str],
    status_callback: Callable[[str], None],
    progress_callback: Callable[[int, int], None],
) -> None:
    """Archives a list of emails by removing them from the INBOX."""
    _perform_bulk_action(
        creds=creds,
        email_ids=email_ids,
        action_body={"removeLabelIds": ["INBOX"]},
        status_callback=status_callback,
        progress_callback=progress_callback,
        action_name="archive",
    )


def bulk_delete_emails(
    creds: Credentials,
    email_ids: List[str],
    status_callback: Callable[[str], None],
    progress_callback: Callable[[int, int], None],
) -> None:
    """Deletes a list of emails by moving them to the TRASH."""
    _perform_bulk_action(
        creds=creds,
        email_ids=email_ids,
        action_body={"addLabelIds": ["TRASH"]},
        status_callback=status_callback,
        progress_callback=progress_callback,
        action_name="delete",
    )
