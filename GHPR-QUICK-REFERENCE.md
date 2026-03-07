# ghpr.py Quick Reference

## What Was Done

Converted three shell scripts (ghpr-init.sh, ghpr-stage.sh, ghpr-push.sh) into a unified Python tool `ghpr.py` with additional features.

## Global Options

| Option | What It Does |
|--------|-------------|
| `-v`, `--verbose` | Print all commands before executing |
| `-n`, `--dry-run` | Show what would happen without doing it |

Combine them: `ghpr.py -v -n <command>` to see exactly what would be done.

## Commands

| Command | What It Does |
|---------|-------------|
| `ghpr.py init` | Create staging branch from main |
| `ghpr.py stage <PR>` | Download and apply PR to staging, add 'staged' label |
| `ghpr.py stage --continue <PR>` | Resume after conflict resolution |
| `ghpr.py stage --force <PR>` | Force staging even if already staged |
| `ghpr.py unstage <PR>` | Remove a PR from staging, remove 'staged' label |
| `ghpr.py status` | Show what's staged |
| `ghpr.py push` | Push to FreeBSD, close PRs, add 'merged' label |

## Quick Start

```bash
# Install location
cd /usr/home/imp/git/head/tools/tools/git

# Make executable (already done)
chmod +x ghpr.py

# Optional: add to PATH
ln -s $(pwd)/ghpr.py /usr/local/bin/ghpr

# Test it works
./ghpr.py --help
./test-ghpr.sh
```

## Basic Workflow

```bash
# 1. Initialize once
ghpr.py init

# 2. Stage PRs
ghpr.py stage 1234

# 3. If conflicts occur
vim file.c
git add file.c
ghpr.py stage --continue 1234

# 4. Check what's staged
ghpr.py status

# 5. Push to FreeBSD
ghpr.py push
```

## New Features vs Shell Scripts

1. **`unstage` command** - Remove PRs from staging
2. **`status` command** - See what's staged
3. **`--continue` flag** - Better conflict resolution
4. **Unified interface** - One tool, not three scripts
5. **Better error messages** - Clear instructions on failure
6. **GitHub label tracking** - Automatically manages 'staged' and 'merged' labels
7. **Duplicate prevention** - Won't stage already-staged PRs (use --force to override)
8. **Review display** - Shows PR approvers after successful staging
9. **Current user default** - Uses your username as default reviewer, not hardcoded

## Files Created

```
ghpr.py                    # Main tool (executable Python)
GHPR-README.md             # User guide
GHPR-UNSTAGE.md            # Unstage implementation
GHPR-CONTINUE.md           # Continue implementation
GHPR-STATUS.md             # Development status
GHPR-QUICK-REFERENCE.md    # This file
test-ghpr.sh               # Smoke tests
```

## Files Modified

```
CLAUDE.md                  # Updated with ghpr.py documentation
```

## Implementation Details

**Architecture:**
- `GitConfig` class - Git config operations
- `GitHelper` class - Git command wrappers
- `GHHelper` class - GitHub CLI wrappers (pr_checkout, pr_edit, pr_view, pr_close)
- `GHPR` class - Main orchestration

**State tracking:**
- Uses git config: `branch.staging.opabinia.*`
- PR list: `branch.staging.opabinia.prs`
- Per-PR metadata: `branch.staging.opabinia.<PR>.*`
- GitHub labels: 'staged' (during landing), 'merged' (after push)

**Commit identification:**
- Uses `Pull-Request:` trailer in commit messages
- Added automatically during stage
- Used by unstage to identify which commits to remove

**PR information:**
- Fetches labels, assignees, and reviews from GitHub
- Prevents duplicate staging
- Shows approvers after successful stage

## Testing Notes

**Smoke tests pass:**
```bash
./test-ghpr.sh
# ✅ All smoke tests passed!
```

**Manual testing needed:**
- Test with real PRs from freebsd/freebsd-src
- Test conflict resolution with --continue
- Test unstage with multiple PRs
- Test push to actual FreeBSD repo
- Compare behavior with shell scripts

## Common Issues to Check

1. **gh not installed/authenticated:**
   ```bash
   pkg install gh
   gh auth login
   ```

2. **Not in git repo:**
   - Must run from FreeBSD src tree
   - Must have 'freebsd' remote configured

3. **Staging branch already exists:**
   - Check: `git branch | grep staging`
   - Use different name: `ghpr.py --staging-branch other-name init`

4. **Rebase conflicts:**
   - Resolve conflicts in files
   - `git add <files>`
   - `ghpr.py stage --continue <PR>`

## Equivalence to Shell Scripts

| Old | New |
|-----|-----|
| `ghpr-init.sh` | `ghpr.py init` |
| `ghpr-init.sh mybranch` | `ghpr.py --staging-branch mybranch init` |
| `ghpr-stage.sh 1234` | `ghpr.py stage 1234` |
| `ghpr-push.sh` | `ghpr.py push` |

## Where to Find Help

1. **Built-in help:**
   ```bash
   ghpr.py --help
   ghpr.py stage --help
   ```

2. **Documentation:**
   - `GHPR-README.md` - Full user guide
   - `GHPR-STATUS.md` - Current status, known issues
   - `GHPR-UNSTAGE.md` - How unstage works
   - `GHPR-CONTINUE.md` - How --continue works

3. **Original scripts:**
   - Still available in `ghpr/` directory
   - Can be used as fallback if needed

## Next Steps

1. Test with real PRs
2. Document any issues found
3. Compare behavior with shell scripts
4. Adjust based on feedback
5. Consider adding to Makefile for installation

## Code Statistics

- ~930 lines of Python
- 4 helper classes
- 6 commands
- Type hints throughout
- Comprehensive error handling
- GitHub API integration

## Dependencies

- Python 3.6+ (standard library only)
- git (command-line)
- gh (GitHub CLI)
- perl (for style checker, optional)

## Environment

Works in:
- FreeBSD src repository
- Requires 'freebsd' remote
- Requires 'main' base branch
- GitHub PRs must be from freebsd-src (configurable with --repo)
