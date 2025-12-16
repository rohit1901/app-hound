# 🐶 app-hound

**app-hound** is your energetic Mac audit companion! It sniffs out, fetches, and reports all top-level folders and files related to your apps, making it easy to clean up old traces or confidently uninstall software. Big on fun, clarity, and reliability, app-hound never includes noisy missing data or deep file listings, giving you a clear audit trail.

***

## Features

- 🐶 **Playful, doggy-themed audit messages**
- Sniffs out **top-level folders and files only**—anything inside can safely be deleted!
- **Automatic scanning of common macOS application and user data locations**
- **Extensible config** for additional custom locations (`additional_locations`)
- **Launches installers** for apps where desired
- **Clean, standards-compliant CSV output**:
  `App Name, Base Path, Folder, File name`
- **Tested to >95% coverage**
- Works with __Poetry__ for easy setup and dependency management

***

## Installation & Setup

1. **Install [Poetry](https://python-poetry.org/docs/#installation):**
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/app-hound.git
   cd app-hound
   ```

3. **Install dependencies:**
   ```bash
   poetry install
   ```

***

## Configuration (`apps_config.json`)

App-hound uses a single config file at the project root.

**Example:**
```json
{
  "apps": [
    {
      "name": "PDF Expert",
      "additional_locations": ["/opt/pdfexpert", "/usr/local/share/pdfexpert"],
      "installation_path": "~/Downloads/pdf_expert_installer.pkg"
    },
    {
      "name": "Slack"
      // Only defaults, no extra locations
    }
  ]
}
```

- **name:** The application's name.
- **additional_locations:** Optional extra locations to sniff for top-level folders/files.
- **installation_path:** Optional installer path (local only) if installation should be performed.

***

## Usage

1. **Run app-hound:**
   ```bash
   poetry run app-hound -i ./
   ```
   Or sniff a single app without a config file:
   ```bash
   poetry run app-hound -a "Slack"
   ```
2. **Follow prompts:**
   - Enter any installer paths if relevant (app-hound will fetch them for you!).
   - Enter the desired output CSV filename.

## Help

- **app-hound -h**: Display help message.
- **app-hound -i <path>**: Specify the directory containing apps_config.json.
- **app-hound -o <filename>**: Specify output CSV filename.
- **app-hound -a "<app name>"**: Audit a single application without using apps_config.json.

***

## Audit Logic

- App-hound **lists only top-level folders and files whose name includes the app name**.
- If a folder named with your app exists in a target location, everything inside can be considered for deletion.
- **No "not found" entries** appear in the final CSV; playful status is shown in the console only.

**Example audit results in the CSV:**
```
App Name,Base Path,Folder,File name
PDF Expert,/Applications/PDF Expert.app,False,PDF Expert.app
PDF Expert,/Users/rohitkhanduri/Library/Application Support/PDF Expert,True,none
```

**Example console output:**
```
🐶 app-hound sniffs extra spots for 'PDF Expert'!
🐶 app-hound checks custom path: /opt/pdfexpert... Bingo! Found!
🐶 app-hound checks custom path: /usr/local/share/pdfexpert... No scent detected!
🐶 app-hound sniffs: '/Users/rohitkhanduri/Library/Application Support/PDF Expert' (folder exists). Ready to fetch all traces!
```

***

## Testing & Coverage

- Tests cover installer logic, config loading, playful console output, audit CSV, edge cases, and top-level matching.
- Confirm coverage with:
  ```bash
  poetry run pytest --cov=src/app_hound
  ```
- All console output and audit logic is covered; **coverage >95%**.

***

## Advanced & Contributing

- All major Mac user and system locations are searched by default—extend `additional_locations` for niche app data!
- Playful emoji and dog jokes are always welcome in PRs.
- Want an option to list all files recursively? Open an issue or send a PR!

***

## License

MIT

***

## About

A friendly doggy companion for Mac users and admins, app-hound helps you keep your system lean and clean (and might earn itself a treat!).
