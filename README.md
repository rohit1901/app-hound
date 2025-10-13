# app-hound 🐶

**app-hound** is a playful utility for macOS that helps you track, audit, and clean up all the files and folders left behind by any software you install. It can even launch your installer for you, sniff out every new pawprint, and export a full audit report to CSV!

***

## Features

- **Launch Mac installers** (`.app`, `.pkg`, `.dmg`) directly from the utility
- **Audit any number of applications** using a simple JSON config file
- **Recursively scans all provided paths** for files and folders
- **Colorful, verbose terminal output** using Rich
- **Exports results to a CSV** for easy review, reporting, or scripting
- **Modular, testable codebase** in `src/app_hound`
- **Poetry** for dependency management and project structure

***

## Project Structure

```
app-hound/
├── src/
│   └── app_hound/
│       ├── __init__.py
│       ├── finder.py
│       └── constants.py
├── main.py
├── app_config.json
├── tests/
│   └── test_finder.py
├── pyproject.toml
├── README.md
```

***

## Getting Started

### 1. Install [Poetry](https://python-poetry.org/docs/#installation)

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/app-hound.git
cd app-hound
```

### 3. Install Dependencies

```bash
poetry install
```

***

## Configuration: app_config.json

Create or edit `app_config.json` in the project root.
Example:
```json
{
  "apps": [
    {
      "name": "PDF Expert",
      "paths": [
        "/Applications/PDF Expert.app",
        "~/Library/Application Support/PDF Expert",
        "~/Library/Preferences/com.readdle.PDFExpert.plist"
      ]
    },
    {
      "name": "Slack",
      "paths": [
        "/Applications/Slack.app",
        "~/Library/Application Support/Slack",
        "~/Library/Preferences/com.tinyspeck.slackmacgap.plist"
      ]
    }
  ]
}
```
- **name:** Should match the real application name.
- **paths:** List all relevant places the app stores binaries, support files, preferences, or logs.

***

## Usage

### 1. Launch Poetry Shell (recommended)
```bash
poetry shell
```

### 2. Run app-hound

```bash
python main.py
```

### 3. Steps you’ll follow

- **Step 1:**
  Enter the path to your installer when prompted (e.g. `/Applications/Slack.app` or `/Users/youruser/Downloads/Name.pkg`).
  - Use an absolute path, or `~/Downloads/...`
  - If it’s a `.dmg`, mount manually as prompted by the utility.
- **Step 2:**
  Enter your desired CSV output filename (e.g. `audit_report.csv`)
- **Step 3:**
  app-hound will:
  - **Run the installer** (if found and supported)
  - **Recursively audit files and folders** listed in `app_config.json`
  - **Print real-time colored status** (found, not found, empty, etc)
  - **Save all results** in your CSV file

### Sample Output

```
[bold magenta]Auditing PDF Expert[/bold magenta]
[green]PDF Expert: /Applications/PDF Expert.app (file exists)[/green]
[green]PDF Expert: /Users/youruser/Library/Application Support/PDF Expert/library_file.db[/green]
...
```

***

## Testing

Run all tests with Poetry:
```bash
poetry run pytest
```
or, while in the poetry shell:
```bash
pytest
```

All code and test imports use:
```python
from app_hound.finder import ...
```

***

## Troubleshooting

- **Installer not found:** Double-check the path, filename, and spelling.
- **Config file not found:** Make sure `app_config.json` is in your project root, next to `main.py`.
- **Import/module errors in tests:**
  - Make sure you run pytest from the project root.
  - Use Poetry or set `PYTHONPATH=src` when running tests.

***

## Contributing

- Add new application path patterns to app_config.json
- PRs to improve installer support or add new auditing features welcome!
- Feel free to add plugins for exporting in other formats or OSes.

***

## License

MIT

***

## About

Created by [Rohit Khanduri](https://github.com/rohit1901).
**app-hound** is here to help software professionals, sysadmins, and security teams sniff out every last file for easy migration, clean uninstalls, and compliance!

***

**Ready, set, fetch those files! 🐶**

***
