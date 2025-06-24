# Attachment Downloader Feature - TODO

This document outlines the tasks required to implement the attachment downloader feature, based on our detailed discussion.

## 1. Core Application Flow & UI Changes (`main.py`, `screens.py`)

This phase focuses on building the new user interface screens and updating the application's startup and navigation logic.

-   [x] **Create a new `MainMenuScreen` in `screens.py`:**
    -   This will be the new initial screen after authentication.
    -   It should present two choices to the user:
        1.  `Button("Manage Emails")`
        2.  `Button("Download Attachments")`

-   [x] **Create a new `DaysInputScreen` in `screens.py`:**
    -   This should be a modal screen that prompts the user to enter the number of days to look back for attachments.
    -   It should include a `TextInput` widget for the number and "OK" / "Cancel" buttons.
    -   It should validate that the input is a positive integer.

-   [x] **Create a new `DownloadProgressScreen` in `screens.py`:**
    -   This screen is displayed while the download is active.
    -   It should be a non-interactive screen showing:
        -   A `ProgressBar` for overall progress (e.g., attachments downloaded / total attachments found).
        -   A `Static` widget for status updates (e.g., "Downloading `file.pdf` from `sender@example.com`...").
    -   Since cancellation is not required, no "Cancel" button is needed.

-   [x] **Create a new `DownloadSummaryScreen` in `screens.py`:**
    -   This screen is displayed after the download worker finishes (on success or failure).
    -   **On success:** Display a table or formatted text with the results:
        -   Header: "Download Complete"
        -   For each sender/directory: `Directory`, `Files Downloaded`, `Total Size`.
    -   **On failure:** Display the error message that stopped the process.
        -   Header: "Download Failed"
        -   Content: The specific error message.
    -   It must include a `Button("Main Menu")` to dismiss the screen and return.

-   [x] **Modify `GmailCtrlApp.on_mount` in `main.py`:**
    -   Change the logic to authenticate, and then `push_screen(MainMenuScreen())` instead of immediately fetching emails.

-   [x] **Update `GmailCtrlApp` navigation in `main.py`:**
    -   Add methods to orchestrate the new flow: e.g., showing the `DaysInputScreen`, then running the download worker, and finally showing the `DownloadSummaryScreen`.

## 2. Gmail API Interaction (`gmail_client.py`)

This phase adds the necessary functions to communicate with the Gmail API for fetching attachment information and content.

-   [ ] **Create `fetch_attachment_metadata(...)` function:**
    -   This function will query for messages that have attachments within a specific date range.
    -   It should use the Gmail API query: `has:attachment newer_than:Xd` where `X` is the number of days.
    -   It should parse the results to build a list of all individual attachments to be downloaded, including `messageId`, `attachmentId`, original `filename`, `size`, `sender`, and `emailDate`.

-   [ ] **Create `download_single_attachment(...)` function:**
    -   This function will take a `messageId` and `attachmentId` as input.
    -   It will call the `users.messages.attachments.get` API endpoint.
    -   It should return the base64-decoded attachment data.

## 3. Download and File System Logic (New Module: `file_handler.py`)

This phase implements the logic for writing files to the disk safely and correctly.

-   [ ] **Create a new file `file_handler.py`.**

-   [ ] **Implement directory creation logic:**
    -   Create the root `downloads/` directory if it doesn't exist.
    -   For each sender, create a subdirectory. Sanitize the sender's email address to create a valid directory name (e.g., replace invalid characters).

-   [ ] **Implement "safe download" logic:**
    -   Downloads should first be written to a temporary file (e.g., in a `.tmp` subdirectory or with a `.tmp` extension).
    -   Only after the download is fully complete should the file be moved to its final destination (`downloads/sender-email/filename.ext`). This prevents corrupt partial files.

-   [ ] **Implement filename collision and skipping logic:**
    -   Before downloading, check if the final target file already exists. If so, skip the download for that attachment.
    -   When determining the final filename, if `filename.ext` already exists, try `filename-1.ext`, then `filename-2.ext`, and so on, until an unused name is found.

-   [ ] **Implement file timestamp logic:**
    -   After a file is successfully moved to its final destination, set its "last modified" timestamp to match the date of the email it came from.

## 4. Worker and Orchestration (`main.py`)

This phase ties everything together into a background worker process.

-   [ ] **Create a new worker method `perform_attachment_download` in `GmailCtrlApp`:**
    -   This worker will be triggered after the user provides the number of days.
    -   It orchestrates the entire process:
        1.  Switch to the `DownloadProgressScreen`.
        2.  Call `gmail_client.fetch_attachment_metadata` to get the list of attachments.
        3.  Loop through the list of attachments to download.
        4.  For each attachment:
            -   Use `file_handler` logic to determine the final path and check if it should be skipped.
            -   If not skipping, call `gmail_client.download_single_attachment`.
            -   Use `file_handler` to save the file safely.
            -   Update the `DownloadProgressScreen` with progress.
        5.  Implement the **fail-fast** logic: if any step fails, catch the exception, and immediately stop the loop.
        6.  After the loop finishes (or fails), collect the summary data (files/sizes per directory or the error message).
        7.  Use `call_from_thread` to switch to the `DownloadSummaryScreen` with the collected data.
