import logging
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"


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
