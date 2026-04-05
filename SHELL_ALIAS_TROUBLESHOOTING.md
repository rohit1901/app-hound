# Shell Alias Troubleshooting Guide

## 🔍 Overview

When using `app-hound`, you may encounter unexpected behavior with command-line options due to shell aliases or functions that intercept and transform your commands before they reach the actual `app-hound` executable.

This guide helps you understand, detect, and resolve these issues.

---

## 🐛 The Problem

### Symptoms

You run a command and see unexpected transformations in the output:

```bash
$ app-hound --app "n8n"
🐾 trail: poetry run app-hound --app-name n8n --app
usage: app-hound [-v] [-i INPUT] ... 
app-hound: error: argument -a/--app/--app-name: expected one argument
```

**Notice:** The `🐾 trail:` line shows your command was transformed to `--app-name n8n --app`, which causes a parsing error because the argument appears twice.

### Root Cause

A shell alias or function (typically in `~/.zshrc`, `~/.bashrc`, or similar) is intercepting `app-hound` commands and modifying them before execution.

Common causes:
- Wrapper alias that transforms argument syntax
- Function that adds `poetry run` prefix and modifies flags
- Autocomplete or shell plugin interference
- Custom argument preprocessing logic

---

## ✅ Working vs Failing Syntax

### ✅ These Work

```bash
# Short form with space
app-hound -a "n8n"
app-hound -i ./config.json
app-hound -o ~/output.csv

# Long form with equals
app-hound --app="n8n"
app-hound --input=./config.json
app-hound --output=~/output.csv
app-hound --additional-location=~/.vscode
app-hound --pattern="*.log"
```

### ❌ These May Fail (Due to Shell Alias)

```bash
# Long form with space (gets transformed)
app-hound --app "n8n"           # Transformed incorrectly
app-hound --input ./config.json  # May cause issues
app-hound --output ~/output.csv  # May cause issues
```

---

## 🔧 Solutions

### Solution 1: Use Correct Syntax (Recommended)

**For simplicity and reliability, use short options:**

```bash
app-hound -a "Slack"
app-hound -i ./apps_config.json
app-hound -o ~/Desktop/audit.csv
```

**For long options, always use equals:**

```bash
app-hound --app="Slack"
app-hound --input=./apps_config.json
app-hound --output=~/Desktop/audit.csv
app-hound --additional-location=~/.config
```

### Solution 2: Bypass the Alias

**Method 1: Backslash prefix**
```bash
\app-hound --app "n8n"
```

**Method 2: Use full path**
```bash
# Find the path first
which app-hound
# Then use it
/path/to/.venv/bin/app-hound --app "n8n"
```

**Method 3: Use command builtin**
```bash
command app-hound --app "n8n"
```

**Method 4: Use env**
```bash
env app-hound --app "n8n"
```

### Solution 3: Fix or Remove the Alias

#### Step 1: Find the Alias

```bash
# Check what app-hound is
type app-hound

# List all aliases containing app-hound
alias | grep app-hound

# Search shell config files (zsh)
grep -rn "app-hound" ~/.zshrc ~/.zshenv ~/.zprofile 2>/dev/null

# Search shell config files (bash)
grep -rn "app-hound" ~/.bashrc ~/.bash_profile ~/.profile 2>/dev/null

# Check functions
declare -f app-hound
```

#### Step 2: Remove the Alias (Temporary)

```bash
# For the current session only
unalias app-hound

# Or unset if it's a function
unset -f app-hound
```

#### Step 3: Remove the Alias (Permanent)

1. Open your shell config file in an editor:
   ```bash
   # For zsh
   nano ~/.zshrc
   # or
   vim ~/.zshrc
   
   # For bash
   nano ~/.bashrc
   ```

2. Find and remove/comment the alias or function:
   ```bash
   # Before (problematic)
   alias app-hound='poetry run app-hound'
   
   # After (commented out)
   # alias app-hound='poetry run app-hound'
   ```

3. Reload your shell:
   ```bash
   source ~/.zshrc  # or ~/.bashrc
   ```

#### Step 4: Fix the Alias (If Needed)

If you need the alias for a legitimate reason (e.g., to run via poetry), fix it to preserve arguments:

**❌ Bad (transforms arguments):**
```bash
alias app-hound='poetry run app-hound'  # If it causes transformation
```

**✅ Good (preserves arguments):**
```bash
# Use a function instead
function app-hound() {
    poetry run app-hound "$@"  # "$@" preserves all arguments as-is
}
```

---

## 🔍 Detection Methods

### Check for Trail Output

The `🐾 trail:` prefix indicates command transformation:

```bash
$ app-hound --app="Slack"
🐾 trail: poetry run app-hound --app=Slack
# ↑ This shows what's actually being executed
```

### Test All Syntax Forms

Run these tests to identify what works:

```bash
# Test 1: Short form with space (should work)
app-hound -a "test"

# Test 2: Long form with equals (should work)
app-hound --app="test"

# Test 3: Long form with space (may fail with alias)
app-hound --app "test"

# Test 4: Bypass alias (should work)
\app-hound --app "test"
```

**Results interpretation:**
- Tests 1, 2, 4 work but Test 3 fails → Shell alias issue
- All tests fail → Different problem (check installation)
- All tests work → No alias issue

### Check Command Resolution

```bash
# See what app-hound resolves to
type app-hound

# Expected output (no alias):
# app-hound is /path/to/.venv/bin/app-hound

# Problem output (alias present):
# app-hound is aliased to `poetry run app-hound'
# app-hound is a shell function from /Users/.../.zshrc
```

---

## 📋 Reference Tables

### Argument Syntax Rules

| Option Type | Correct Syntax | Example | Works with Alias? |
|-------------|----------------|---------|-------------------|
| Short | `-X VALUE` | `app-hound -a "Slack"` | ✅ Usually |
| Long (equals) | `--option=VALUE` | `app-hound --app="Slack"` | ✅ Usually |
| Long (space) | `--option VALUE` | `app-hound --app "Slack"` | ⚠️ Depends on alias |

### All Option Formats

| Option | Short Form | Long Form (equals) | Long Form (space - risky) |
|--------|------------|-------------------|---------------------------|
| App name | `-a "Slack"` | `--app="Slack"` | `--app "Slack"` ⚠️ |
| Input file | `-i config.json` | `--input=config.json` | `--input config.json` ⚠️ |
| Output file | `-o out.csv` | `--output=out.csv` | `--output out.csv` ⚠️ |
| Additional location | N/A | `--additional-location=~/.config` | ⚠️ |
| Pattern | N/A | `--pattern="*.log"` | ⚠️ |
| Exclude | N/A | `--exclude="/System/*"` | ⚠️ |
| Color | N/A | `--accent-color=purple` | ⚠️ |

---

## 🛠️ Common Alias Patterns

### Pattern 1: Poetry Wrapper

**❌ Problematic:**
```bash
# This might transform arguments
alias app-hound='poetry run app-hound'
```

**✅ Fixed:**
```bash
# Use a function with "$@" to preserve arguments
function app-hound() {
    poetry run app-hound "$@"
}
```

### Pattern 2: Default Arguments

**❌ Problematic:**
```bash
# Hardcoded flags interfere with user input
alias app-hound='app-hound --quiet'
```

**✅ Better:**
```bash
# User arguments come after defaults
function app-hound() {
    command app-hound --quiet "$@"
}
```

### Pattern 3: Argument Transformation

**❌ Problematic:**
```bash
# Complex parsing that changes syntax
function app-hound() {
    # Converts --app to --app-name (breaks parsing)
    local args=()
    for arg in "$@"; do
        if [[ "$arg" == "--app" ]]; then
            args+=("--app-name")
        else
            args+=("$arg")
        fi
    done
    command app-hound "${args[@]}"
}
```

**✅ Fixed:**
```bash
# Pass arguments unchanged
function app-hound() {
    poetry run app-hound "$@"
}
```

---

## 🎯 Best Practices

### For Users

1. **Prefer short options when available:**
   ```bash
   app-hound -a "Slack" -i config.json -o output.csv
   ```

2. **Use equals with long options:**
   ```bash
   app-hound --app="Slack" --interactive
   ```

3. **Avoid space with long options** if you have aliases:
   ```bash
   # AVOID: app-hound --app "Slack"
   # USE:    app-hound --app="Slack"
   # OR:     app-hound -a "Slack"
   ```

4. **Check trail output** to see actual command execution

5. **Quote values** that contain spaces or special characters:
   ```bash
   app-hound -a "Google Chrome"
   app-hound --pattern="*.log"
   app-hound --exclude="/System/*"
   ```

### For Developers Creating Aliases

1. **Always use `"$@"` to preserve arguments:**
   ```bash
   function app-hound() {
       poetry run app-hound "$@"  # NOT $* or $@
   }
   ```

2. **Test all syntax forms:**
   - `-a value`
   - `--app=value`
   - `--app value`

3. **Don't transform user arguments** unless absolutely necessary

4. **Document any transformations** in comments

5. **Provide escape hatch** (users can bypass with `\command`)

---

## 🆘 Debug Steps

### Step 1: Identify What's Running

```bash
# Check command type
type app-hound

# Check which binary
which app-hound

# Check if it's aliased
alias app-hound 2>/dev/null

# Check if it's a function
declare -f app-hound 2>/dev/null
```

### Step 2: Enable Shell Debugging

```bash
# Turn on debug mode
set -x

# Run your command
app-hound --app "test"

# Turn off debug mode
set +x
```

This will show every command expansion and substitution.

### Step 3: Compare With and Without Alias

```bash
# With alias
app-hound --app "test"

# Without alias (bypassed)
\app-hound --app "test"

# Direct call
poetry run app-hound --app "test"
```

### Step 4: Check Environment

```bash
# Check PATH
echo $PATH

# Check for environment variables
env | grep -i app
env | grep -i hound

# Check shell
echo $SHELL
echo $0
```

### Step 5: Test Minimal Case

```bash
# Simplest possible command
app-hound --help

# Check version
app-hound --version

# Simple test
app-hound -a "test" 2>&1 | head
```

---

## 📞 Getting Help

### Information to Provide

When asking for help, include:

1. **Shell information:**
   ```bash
   echo $SHELL
   $SHELL --version
   ```

2. **Command type:**
   ```bash
   type app-hound
   ```

3. **Trail output** (if visible):
   ```
   🐾 trail: poetry run app-hound --app-name n8n --app
   ```

4. **The exact command you ran:**
   ```bash
   app-hound --app "n8n"
   ```

5. **Error message:**
   ```
   app-hound: error: argument -a/--app/--app-name: expected one argument
   ```

6. **Alias/function definition** (if found):
   ```bash
   alias app-hound
   declare -f app-hound
   ```

### Quick Fix Checklist

- [ ] Tried using `-a "value"` syntax
- [ ] Tried using `--app="value"` syntax
- [ ] Checked `type app-hound` output
- [ ] Tested with `\app-hound` (bypassing alias)
- [ ] Searched for aliases in shell config files
- [ ] Reloaded shell after config changes
- [ ] Verified app-hound is installed correctly
- [ ] Checked for conflicting shell plugins

---

## 💡 Quick Solutions Summary

| Problem | Quick Fix |
|---------|-----------|
| `--app "value"` fails | Use `-a "value"` or `--app="value"` |
| Alias transforms command | Use `\app-hound` to bypass |
| Need to use long form | Always use equals: `--option=value` |
| Permanent solution | Fix or remove alias in shell config |
| Testing which syntax works | Try `-a`, `--app=`, then `\app-hound --app` |

---

## 📚 Related Documentation

- [app-hound README](README.md) - General usage
- [app-hound --help](#) - Built-in help with syntax examples
- [GitHub Issues](https://github.com/rohit1901/app-hound/issues) - Report problems

---

## 🔖 Version

**Last Updated:** 2024-12-31  
**app-hound Version:** 2.0.1+  
**Guide Version:** 1.0

---

## 📝 Summary

**The Issue:** Shell aliases can transform `--option "value"` syntax before it reaches app-hound, causing parsing errors.

**The Detection:** Look for `🐾 trail:` output showing unexpected command transformations.

**The Solution:**
1. ✅ **Quick:** Use `-a "value"` (short form with space)
2. ✅ **Alternative:** Use `--app="value"` (long form with equals)
3. ✅ **Bypass:** Use `\app-hound` to skip aliases
4. ✅ **Permanent:** Fix or remove the problematic alias

**The Rule:** Short options use space, long options use equals.

---

**Remember:** When in doubt, use the short form (`-a`, `-i`, `-o`) - it's simpler and more reliable! 🐶