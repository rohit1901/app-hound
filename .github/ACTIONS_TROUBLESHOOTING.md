# GitHub Actions Troubleshooting Guide

This guide helps you troubleshoot issues with the `release.yml` workflow.

## 🔴 Current Issue: Authentication Failure

### Error Message
```
fatal: could not read Username for 'https://github.com': terminal prompts disabled
The process '/usr/bin/git' failed with exit code 128
```

### Root Cause
The `AH_PAT_STRONG` secret is either:
- Not set in your repository secrets
- Expired (PATs have expiration dates)
- Missing required permissions
- Incorrectly formatted

---

## ✅ Solution Steps

### Step 1: Verify/Create Personal Access Token (PAT)

1. **Go to GitHub Settings**
   - Navigate to: https://github.com/settings/tokens
   - Or: Profile → Settings → Developer settings → Personal access tokens → Tokens (classic)

2. **Create New Token** (or regenerate existing)
   - Click "Generate new token" → "Generate new token (classic)"
   - Name: `app-hound-release-workflow`
   - Expiration: Choose your preference (90 days, 1 year, or no expiration)
   
3. **Required Scopes** (check these boxes):
   - ✅ `repo` (Full control of private repositories)
     - Includes: `repo:status`, `repo_deployment`, `public_repo`, `repo:invite`
   - ✅ `workflow` (Update GitHub Action workflows)
   - ✅ `write:packages` (Upload packages to GitHub Package Registry)
   - ✅ `delete:packages` (Delete packages from GitHub Package Registry)

4. **Generate and Copy Token**
   - Click "Generate token"
   - **IMPORTANT:** Copy the token immediately (it won't be shown again)
   - Format should be: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### Step 2: Add Token to Repository Secrets

1. **Go to Repository Settings**
   - Navigate to your repository: https://github.com/rohit1901/app-hound
   - Click "Settings" tab
   - Click "Secrets and variables" → "Actions"

2. **Add/Update Secret**
   - Click "New repository secret" (or edit existing)
   - Name: `AH_PAT_STRONG`
   - Value: Paste the token you copied
   - Click "Add secret"

3. **Verify Secret is Set**
   - You should see `AH_PAT_STRONG` in the list of secrets
   - Updated date should be recent

### Step 3: Add GPG Key (Optional but Recommended)

If you want signed commits:

1. **Export Your GPG Private Key**
   ```bash
   # List your keys
   gpg --list-secret-keys --keyid-format=long
   
   # Export the key (replace KEY_ID with your actual key ID)
   gpg --armor --export-secret-keys YOUR_KEY_ID
   ```

2. **Add to Repository Secrets**
   - Name: `GPG_PRIVATE_KEY`
   - Value: Paste the entire output (including `-----BEGIN PGP PRIVATE KEY BLOCK-----`)

**Note:** The updated workflow will work without GPG signing if this secret is not available.

### Step 4: Test the Workflow

1. **Go to Actions Tab**
   - Navigate to: https://github.com/rohit1901/app-hound/actions
   - Click "Create Release and Bump Version" workflow

2. **Run Workflow Manually**
   - Click "Run workflow" button
   - Enter a test version (e.g., `2.0.2`)
   - Click "Run workflow"

3. **Monitor Execution**
   - Click on the running workflow
   - Watch each step complete
   - Check for green checkmarks ✅

---

## 🔧 Common Issues & Solutions

### Issue: "Resource not accessible by integration"

**Cause:** The PAT doesn't have sufficient permissions.

**Solution:**
- Verify the token has `repo` and `workflow` scopes
- Regenerate the token with correct permissions
- Update the `AH_PAT_STRONG` secret

### Issue: "GPG signing failed"

**Cause:** GPG key is not properly formatted or has a passphrase.

**Solution:**
- The workflow now gracefully handles missing GPG keys
- If you want signing: ensure the key has no passphrase
- If you don't need signing: remove the `GPG_PRIVATE_KEY` secret

### Issue: "Push rejected - non-fast-forward"

**Cause:** Someone else pushed to the branch while the workflow was running.

**Solution:**
- The workflow now automatically retries with `--force-with-lease`
- This is safe and won't overwrite others' work

### Issue: "Poetry command not found"

**Cause:** Poetry installation failed.

**Solution:**
- Check Python version compatibility (workflow uses 3.13)
- Verify `snok/install-poetry@v1` action is working
- Try pinning to an older Poetry version if needed

---

## 🧪 Testing Locally

Before triggering the workflow, test locally:

```bash
# 1. Check if poetry works
poetry version 2.0.2

# 2. Check if git is configured
git config --list | grep user

# 3. Simulate the version bump
poetry version 2.0.2
git add pyproject.toml
git commit -m "chore: bump version to 2.0.2"

# 4. Check if you can push
git push origin HEAD:main

# 5. Clean up test commit
git reset --hard HEAD~1
```

---

## 🔍 Debugging Workflow Failures

### Enable Debug Logging

1. Go to repository Settings → Secrets and variables → Actions
2. Add a new variable (not secret):
   - Name: `ACTIONS_STEP_DEBUG`
   - Value: `true`
3. Re-run the workflow
4. Check logs for detailed output

### Check Workflow Logs

1. Go to Actions tab
2. Click on the failed workflow run
3. Click on each step to see detailed logs
4. Look for red ❌ indicators

### Useful Log Commands

The updated workflow now includes:
- `echo` statements for each step
- `git log` output after commits
- `ls -lh dist/` to verify builds
- Summary with commit hash and version

---

## 📝 Workflow Improvements Made

The updated workflow now includes:

1. **Fallback Authentication**
   - Uses `secrets.GITHUB_TOKEN` if `AH_PAT_STRONG` is not available
   - Format: `token: ${{ secrets.AH_PAT_STRONG || secrets.GITHUB_TOKEN }}`

2. **Optional GPG Signing**
   - Detects if GPG key is available
   - Falls back to unsigned commits if not
   - No workflow failure if key is missing

3. **Better Error Handling**
   - Rebase conflicts are detected and handled
   - Push failures trigger force-with-lease retry
   - Each step includes error messages

4. **Enhanced Logging**
   - Echo statements for debugging
   - Git log output after commits
   - Distribution file listing
   - Summary page with key information

5. **Improved Push Authentication**
   - Sets git remote URL with token explicitly
   - Format: `https://x-access-token:${GITHUB_TOKEN}@github.com/...`

---

## 🆘 Still Having Issues?

### Quick Checklist

- [ ] PAT token is created and copied correctly
- [ ] PAT token has `repo` and `workflow` scopes
- [ ] `AH_PAT_STRONG` secret is set in repository
- [ ] Secret name matches exactly (case-sensitive)
- [ ] Token is not expired
- [ ] Repository permissions allow Actions to run
- [ ] Workflow file syntax is valid (no YAML errors)

### Alternative: Use GITHUB_TOKEN

If you can't get PAT working, use the built-in token:

1. Edit `.github/workflows/release.yml`
2. Replace all `secrets.AH_PAT_STRONG` with `secrets.GITHUB_TOKEN`
3. Update `permissions` section:
   ```yaml
   permissions:
     contents: write
     packages: write
     actions: write
   ```

**Limitation:** `GITHUB_TOKEN` cannot trigger other workflows, but it works for releases.

### Contact Support

If all else fails:
1. Check GitHub Status: https://www.githubstatus.com/
2. GitHub Actions Documentation: https://docs.github.com/en/actions
3. Repository Issues: Create an issue with workflow logs

---

## 📚 Additional Resources

- [GitHub PAT Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [GPG Signing Commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)
- [Poetry Version Management](https://python-poetry.org/docs/cli/#version)
- [GitHub Actions Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)

---

**Last Updated:** 2024-12-31
**Workflow Version:** 2.0 (with improved error handling and fallbacks)