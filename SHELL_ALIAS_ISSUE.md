# Shell Alias Issue Troubleshooting Guide

## 🔍 Overview

When using `app-hound`, you may encounter unexpected behavior with the `--app` flag due to shell aliases or functions that intercept and transform your commands before they reach the actual `app-hound` executable.

## 🐛 The Problem

### Symptoms

You may see output like this when running commands:

```bash
$ app-hound --app "n8n"
🐾 trail: poetry run app-hound --app-name n8n --app
usage: app-hound [-v] [-i INPUT] ... 
app-hound: error: argument -a/--app/--app-name: expected one argument
```

Notice the `🐾 trail:` line shows your command was transformed to `--app-name n8n --app`, which causes an error.

### Root Cause

A shell alias or function (likely in your `.zshrc`, `.bashrc`, or similar) is intercepting `app-hound` commands and modifying them before execution. This is typically done to add default flags or transform argument syntax.

Common culprits:
- Alias that wraps `app-hound` with `poetry run`
- Function that transforms `--flag value` to `--flag-name value`
- Wrapper that adds default arguments

## ✅ Solutions

### Solution 1: Use Correct Syntax (Recommended)

Use the syntax patterns that work correctly:

**✅ WORKS: Single-dash with space**
```bash
app-hound -a "n8n"
app-hound -a "Slack" --interactive
```

**✅ WORKS: Double-dash with equals**
```bash
app-hound --app="n8n"
app-hound --app-name="Slack" --interactive
```

**❌ FAILS: Double-dash with space (transformed by alias)**
```bash
app-hound --app "n8n"  # Gets transformed incorrectly
```

### Solution 2: Bypass the Alias

You can bypass shell aliases using these methods:

**Method 1: Use backslash**
```bash
\app-hound --app "n8n"
```

**Method 2: Use full path**
```bash
/path/to/.venv/bin/app-hound --app "n8n"
```

**Method 3: Use command builtin**
```bash
command app-hound --app "n8n"
```

### Solution 3: Fix or Remove the Alias

#### Find the Alias

Check your shell configuration files:

```bash
# For zsh
grep -r "app-hound" ~/.zshrc ~/.zsh* 2>/dev/null

# For bash
grep -r "app-hound" ~/.bashrc ~/.bash* ~/.profile 2>/dev/null

# Check current aliases
alias | grep app-hound
type app-hound
```

#### Remove the Alias

If you find an unwanted alias, you can:

1. **Temporarily disable** (current session only):
   ```bash
   unalias app-hound
   ```

2. **Permanently remove**:
   - Edit your shell config file (e.g., `~/.zshrc`)
   - Remove or comment out the alias/function
   - Reload: `source ~/.zshrc`

#### Fix the Alias

If the alias is intentional but broken, fix it to preserve argument syntax:

**Bad alias** (causes issues):
```bash
# DON'T DO THIS - transforms arguments incorrectly
alias app-hound='poetry run app-hound'  # If it transforms --app to --app-name
```

**Good alias** (preserves arguments):
```bash
# DO THIS - passes arguments through correctly
alias app-hound='poetry run app-hound'  # Only if it doesn't transform args
function app-hound() {
    poetry run app-hound "$@"  # Preserves all arguments as-is
}
```

## 🔍 Detecting the Issue

### Check for Trail Output

The `🐾 trail:` prefix in output indicates command transformation is happening:

```bash
$ app-hound --app="Slack"
🐾 trail: poetry run app-hound --app=Slack
# ↑ This shows what command is actually being executed
```

### Test Different Syntax Forms

Run these tests to see which work:

```bash
# Test 1: Short form with space
app-hound -a "test"

# Test 2: Long form with equals
app-hound --app="test"

# Test 3: Long form with space (often fails)
app-hound --app "test"

# Test 4: Bypass alias
\app-hound --app "test"
```

If Test 1 and Test 2 work, but Test 3 fails and Test 4 works, you have a shell alias issue.

## 📋 Best Practices

### For Users

1. **Use short form** for simplicity:
   ```bash
   app-hound -a "AppName"
   ```

2. **Use equals with long form**:
   ```bash
   app-hound --app="AppName"
   ```

3. **Avoid space with long form** if you have aliases:
   ```bash
   # AVOID: app-hound --app "AppName"
   ```

4. **Check the trail output** to see what's actually being executed

### For Developers

If you're creating shell aliases or functions:

1. **Preserve argument syntax**:
   ```bash
   function app-hound() {
       poetry run app-hound "$@"  # Use "$@" not $*
   }
   ```

2. **Don't transform user arguments** unless absolutely necessary

3. **Document any transformations** clearly

4. **Test all syntax forms**:
   - `-a value`
   - `--app=value`
   - `--app value`
   - `-i path`
   - `--input=path`
   - `--input path`

## 🛠️ Common Alias Patterns

### Pattern 1: Poetry Wrapper

**Problematic version:**
```bash
# May transform arguments
alias app-hound='poetry run app-hound'
```

**Working version:**
```bash
# Preserves arguments correctly
function app-hound() {
    poetry run app-hound "$@"
}
```

### Pattern 2: Default Flags

**Problematic version:**
```bash
# Hardcoded flags can interfere
alias app-hound='app-hound --interactive'
```

**Working version:**
```bash
# User flags override defaults
function app-hound() {
    command app-hound --interactive "$@"
}
```

### Pattern 3: Argument Transformation

**Problematic version:**
```bash
# Transforms --app to --app-name (breaks syntax)
function app-hound() {
    # Complex argument parsing that changes syntax
    ...
}
```

**Working version:**
```bash
# Passes arguments unchanged
function app-hound() {
    poetry run app-hound "$@"
}
```

## 📚 Reference

### Argument Syntax Rules

| Form | Syntax | Example | Works With Alias? |
|------|--------|---------|-------------------|
| Short | `-a VALUE` | `app-hound -a "Slack"` | ✅ Usually |
| Long (equals) | `--app=VALUE` | `app-hound --app="Slack"` | ✅ Usually |
| Long (space) | `--app VALUE` | `app-hound --app "Slack"` | ⚠️ Depends on alias |

### All Valid Forms for App Flag

These are all valid forms accepted by argparse:

```bash
-a "AppName"           # Short form, space
--app="AppName"        # Long form, equals
--app-name="AppName"   # Alternate long form, equals
```

**Note:** The space-separated long forms (`--app "AppName"`, `--app-name "AppName"`) are valid in argparse but may be transformed by shell aliases.

## 🆘 Still Having Issues?

### Debug Steps

1. **Check what's running:**
   ```bash
   which app-hound
   type app-hound
   ```

2. **Inspect the alias:**
   ```bash
   alias app-hound
   declare -f app-hound  # For functions
   ```

3. **Test with bypass:**
   ```bash
   \app-hound --app "test" -v
   ```

4. **Check environment:**
   ```bash
   env | grep -i app
   printenv | grep -i hound
   ```

5. **Enable shell debugging:**
   ```bash
   set -x  # zsh/bash
   app-hound --app "test"
   set +x
   ```

### Get Help

If you're still stuck:

1. Check the output of `type app-hound`
2. Look for the `🐾 trail:` line in output
3. Try running with `\app-hound` to bypass aliases
4. Report the issue with:
   - Your shell (`echo $SHELL`)
   - The trail output
   - Output of `type app-hound`

## 📝 Summary

- **Problem:** Shell aliases can transform `--app "value"` syntax
- **Detection:** Look for `🐾 trail:` output showing transformation
- **Solution:** Use `-a "value"` or `--app="value"` syntax
- **Alternative:** Bypass with `\app-hound` or fix/remove the alias
- **Best Practice:** Stick to `-a` (short form) for reliability

---

**Last Updated:** 2024-12-31  
**Related:** [GitHub Issue #XXX](https://github.com/rohit1901/app-hound/issues/XXX)