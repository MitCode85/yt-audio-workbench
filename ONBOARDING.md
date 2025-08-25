## Developer Onboarding Guide

Welcome to the project! Here’s how to get your development environment set up in a few minutes.

### 1. Prerequisites

Before you begin, make sure you have the following installed on your system:

* **Python 3.9+**
* **Git**
* **ffmpeg** & **ffprobe**
* **mp3gain** (optional, but recommended)

*You can run the `check-deps.sh` (macOS/Linux) or `check-deps.ps1` (Windows) script in the repository to verify the external tools.*

---

### 2. Project Setup

The project includes setup scripts that will handle creating a virtual environment and installing all necessary Python packages.

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-folder>
    ```

2.  **Run the setup script for your OS:**

    * For **Windows** (in PowerShell):
        ```powershell
        .\setup-venv.ps1
        ```
    * For **macOS / Linux** (in your terminal):
        ```bash
        bash setup-venv.sh
        ```

3.  **Activate the virtual environment:**

    * For **Windows** (in PowerShell):
        ```powershell
        .\.venv\Scripts\Activate.ps1
        ```
    * For **macOS / Linux** (in your terminal):
        ```bash
        source .venv/bin/activate
        ```

---

### 3. Running the Application

With the virtual environment active, you can run the application with a simple command:

```bash
python yt_audio_backup_gui.py
```

---

### 4. Development Workflow

This project uses standard tools to maintain code quality.

* **Linting & Testing:** Use the `Makefile` for common tasks.
    ```bash
    # Run all linters and type checkers
    make lint

    # Run a quick smoke test
    make test
    ```

* **Pre-commit Hooks (Recommended):** The project is set up with pre-commit hooks to automatically format code and run checks before you commit. To enable this, run:
    ```bash
    # Install the hooks into your local .git folder
    pre-commit install
    ```

That's it! You're ready to start developing.