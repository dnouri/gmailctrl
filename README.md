# gmailctrl

A TUI to manage bulk email in Gmail.

![gmailctrl screenshot](https://raw.githubusercontent.com/dnouri/gmailctrl/main/docs/screenshot.png)

## Motivation

Struggling with an overflowing inbox? Much of it is likely "graymail"—newsletters, notifications, and promotional content that, while not spam, clutters your digital life. Managing this in Gmail's web interface is slow. `gmailctrl` is a fast, keyboard-driven terminal application built to solve this. It groups emails by sender, letting you archive or delete large volumes of messages with a few keystrokes, making inbox cleanup fast and efficient.

This project, including its source code and this documentation, was written entirely using AI.

## Installation

To install `gmailctrl`, you will need Python 3.10+ and `uv`.

1.  Create and activate a virtual environment:
    ```sh
    uv venv
    source .venv/bin/activate
    ```

2.  Install the application directly from GitHub:
    ```sh
    uv pip install git+https://github.com/dnouri/gmailctrl
    ```

## Setup and First Run

Before you can use `gmailctrl`, you need to provide it with API credentials to access your Gmail account.

### 1. Get `credentials.json`

The application uses OAuth 2.0 to securely access your data. You'll need to get a credentials file from the Google Cloud Console.

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project (or select an existing one).
3.  Enable the **Gmail API** for your project. You can find it in the "APIs & Services" > "Library" section.
4.  Go to "APIs & Services" > "Credentials".
5.  Click **Create Credentials** and select **OAuth client ID**.
6.  Choose **Desktop app** as the application type.
7.  After creation, click the **Download JSON** button for the client ID you just created.
8.  Save this file as `credentials.json` in the directory where you will run `gmailctrl`.

### 2. First Launch

When you run `gmailctrl` for the first time, it will automatically open a new tab in your web browser.

1.  You will be asked to log in to your Google account.
2.  You will then be prompted to grant `gmailctrl` permission to "Read, compose, send, and permanently delete all your email from Gmail". This is required for the application to read, archive, and delete emails on your behalf.
3.  After you approve, a `token.json` file will be created in the same directory. This file securely stores your authorization and will be used for future sessions, so you won't have to log in every time.

## Usage

After the initial scan, you will be presented with the main screen, which lists all email groups found in your inbox, sorted by the number of messages from each sender.

### Main View & Keybindings

The main view is a table of all sender groups. You can navigate this list with the arrow keys.

| Key         | Action                                                 |
|-------------|--------------------------------------------------------|
| `Space`     | Toggle selection for the highlighted sender group.     |
| `a`         | Archive all emails from all selected sender groups.    |
| `d`         | Delete (move to trash) all emails from selected groups.|
| `Enter`     | Open the detail view for the highlighted sender group. |
| `Ctrl+R`    | Manually refresh the entire email list.                |
| `q`         | Quit the application.                                  |

Actions like archiving and deleting will always ask for confirmation.

### Detail View

Pressing `Enter` on a sender group opens the detail view. This screen shows a summary for that specific group and provides `Archive` and `Delete` buttons to act on all emails from only that sender. After the action is complete, you will be returned to the main list, which will be refreshed.
