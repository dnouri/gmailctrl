# Gmail Bulk Email Manager TUI: Developer TODO List

This document outlines the development plan for a Textual-based TUI application designed to identify and manage bulk emails in a user's Gmail account.

## Milestones

### Milestone 1: Project Setup & Google Authentication

The primary goal of this milestone is to establish the project foundation and implement a robust and secure authentication flow with Google's services.

-   [x] **Task 1.1: Initial Project Scaffolding**
    -   [x] Set up the basic project structure, including `pyproject.toml` for dependencies (`textual`, `google-api-python-client`, `google-auth-oauthlib`).
    -   [x] Create the main entry point file, `main.py`, with a basic Textual app structure.
    -   [x] Implement a global exception handler in the main app class.
    -   [x] Configure file-based logging to `gmailctrl.log`.

-   [x] **Task 1.2: Implement OAuth 2.0 Authentication**
    -   [x] Create a module to handle Google API authentication.
    -   [x] The flow must be browser-based (OAuth 2.0 Installed Application flow).
    -   [x] On the first run, the application should guide the user to authorize access via their web browser.
    -   [x] Successfully obtained credentials (access and refresh tokens) must be stored securely on the user's local machine (e.g., in a file like `token.json`).
    -   [x] On subsequent runs, the application should automatically use the stored refresh token to get a new access token without requiring user interaction, unless the token is revoked or expired.

### Milestone 2: Core Gmail API Interaction Logic

This milestone focuses on creating the non-UI logic for fetching, parsing, and acting upon emails. This code should be independent of the TUI.

-   [x] **Task 2.1: Implement Email Fetching**
    -   [x] Create a function to fetch a list of emails from the user's Gmail account.
    -   [x] Initially, this function will only query for emails present in the `INBOX`.
    -   [x] The number of recent emails to scan should be configurable, with a sensible default (e.g., 1000).

-   [x] **Task 2.2: Implement Email Grouping and Analysis**
    -   [x] Create a function that takes a list of fetched emails and groups them by sender (`From` header).
    -   [x] For each group, the function must compute the following summary statistics:
        -   [x] Sender's name and email address.
        -   [x] Total count of emails in the group.
        -   [x] The date of the oldest and newest email in the group.
        -   [x] The total count of attachments across all emails in the group.
        -   [x] A boolean flag indicating if at least one email in the group contains a `List-Unsubscribe` header.

-   [x] **Task 2.3: Implement Bulk Action Functions**
    -   [x] Create a function to bulk archive emails given a list of email IDs.
    -   [x] Create a function to bulk delete (move to trash) emails given a list of email IDs.

### Milestone 3: Textual TUI Implementation

This milestone involves building the user interface and connecting it to the core logic from Milestone 2.

-   [x] **Task 3.1: Main Application Shell & Error Handling**
    -   [x] Set up the main Textual `App` class.
    -   [x] **Crucially**, implement a single, global exception handler. As per the design, any unhandled exception from any part of the application should be caught here. The handler must print the full exception traceback to `stderr` and then cleanly terminate the application. There should be minimal to no `try...except` blocks in the rest of the application code.

-   [x] **Task 3.2: Main Screen - Sender List View**
    -   [x] This is the default screen after a successful login.
    -   [x] It should display a list of the sender groups.
    -   [x] The list must be sorted by the email count (descending).
    -   [x] Each item in the list must display the sender, the email count, and a visual indicator (e.g., a `[U]` tag) if the group contains `List-Unsubscribe` headers.
    -   [x] Implement a manual refresh mechanism (e.g., via a `Ctrl+R` key binding) that triggers a full re-scan and rebuilds the list.
    -   [x] Display a loading indicator during the initial scan and subsequent refreshes.
    -   [x] Implement multi-row selection (e.g., using the spacebar).
    -   [x] Provide a visual indicator for selected rows.

-   [ ] **Task 3.3: Detail Screen - Group Detail View**
    -   [ ] This is a new, full-screen view that is displayed when a user selects a sender from the main list.
    -   [ ] It must display the summary statistics for the selected group at the top.
    -   [ ] Below the summary, it must display a list of all individual emails within that group, showing at least the subject and date of each email.
    -   [ ] Provide two clear action buttons/options: `Archive All` and `Delete All`.

-   [ ] **Task 3.4: Implement Action and Navigation Flow**
    -   [ ] **Sub-task 3.4.1: Main Screen Bulk Actions**
        -   [ ] Add key bindings to trigger bulk archive/delete on selected rows (e.g., `a` and `d`).
        -   [ ] Implement a confirmation dialog that summarizes the action (e.g., "Archive 123 emails from 4 senders?").
        -   [ ] Upon confirmation, trigger the bulk action functions for all selected groups.
        -   [ ] After the action, automatically refresh the sender list.
    -   [ ] **Sub-task 3.4.2: Detail Screen Actions**
        -   [ ] When a user selects `Archive All` or `Delete All` on the detail screen, show a confirmation dialog.
        -   [ ] Upon confirmation, trigger the bulk action function for that single group.
        -   [ ] After a successful action, navigate back to the main sender list and refresh it.

### Milestone 4: Testing Plan

-   [ ] **Task 4.1: Unit Tests**
    -   Write unit tests for the email grouping and analysis logic using mock email data to ensure correct calculation of counts, dates, attachments, and the unsubscribe flag.

-   [ ] **Task 4.2: Integration Tests**
    -   Write integration tests for the Gmail API interaction layer.
    -   Use mocking/patching to simulate API responses from Google to test:
        -   The authentication flow.
        -   Email fetching and parsing.
        -   Correct formation of API requests for archive/delete actions.

-   [ ] **Task 4.3: Manual End-to-End Testing**
    -   Perform a full user journey test with a real (but non-critical) Gmail account.
    -   Verify the one-time browser login and subsequent automatic logins.
    -   Verify the initial scan, list sorting, and display.
    -   Verify navigation to the detail view and back.
    -   Verify the confirmation dialog and the successful execution of both archive and delete actions.
    -   Verify the manual refresh functionality.
    -   Verify the "crash on error" strategy by simulating failures (e.g., disconnecting from the internet during an API call) and ensuring the program exits with a clear traceback to `stderr`.
