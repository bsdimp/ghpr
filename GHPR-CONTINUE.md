# Stage --continue Implementation

## Overview

Added `ghpr.py stage --continue <PR>` to resume staging after resolving rebase conflicts.

## Problem

When staging a PR, the rebase may encounter conflicts if:
- The PR modifies the same files as previously staged PRs
- The PR's base branch has diverged from the staging branch
- There are incompatible changes between PRs

Previously, users had to manually run `git rebase --continue` and then figure out how to finish the staging process.

## Solution

The `--continue` flag handles the complete continuation workflow:

1. Continues the interrupted rebase
2. Saves PR metadata to config
3. Moves staging branch to include the PR
4. Runs style checker
5. Shows success message

## Usage

### Normal flow (no conflicts)

```bash
ghpr.py stage 1234
# PR staged successfully
```

### Flow with conflicts

```bash
# Start staging
ghpr.py stage 1234

# Output shows:
# ======================================================================
# REBASE FAILED - Conflicts need to be resolved
# ======================================================================
#
# To resolve:
#   1. Fix conflicts in the affected files
#   2. Stage resolved files: git add <files>
#   3. Continue staging: ghpr stage --continue 1234
#
# Or to abort:
#   git rebase --abort
# ======================================================================

# Resolve conflicts
vim src/sys/kern/vfs_subr.c
git add src/sys/kern/vfs_subr.c

# Continue staging
ghpr.py stage --continue 1234
# PR staged successfully!
```

## Implementation Details

### Detection

The code checks for an active rebase by looking for:
- `.git/rebase-merge/` directory (interactive rebase)
- `.git/rebase-apply/` directory (non-interactive rebase)

If neither exists when `--continue` is used, it errors out.

### Workflow

```python
if do_continue:
    # 1. Verify rebase is in progress
    if not (rebase_merge.exists() or rebase_apply.exists()):
        die("No rebase in progress")

    # 2. Continue the rebase
    git rebase --continue

    # 3. Save metadata (if not already saved)
    if PR not in staged PRs:
        save upstream info
        add PR to list

    # 4. Move staging branch
    git checkout -B staging HEAD

    # 5. Run style checker

    # 6. Success!
```

### Error Handling

**No rebase in progress:**
```
Error: No rebase in progress. Cannot continue.
```

**Rebase continue fails (still has conflicts):**
```
Error: Rebase continue failed. Resolve conflicts and run 'ghpr stage --continue <PR>' again.
```

User should check:
- All conflicts are resolved
- All resolved files are staged with `git add`

### Idempotency

The `--continue` flag is designed to be run multiple times if needed:
- Only saves config if PR isn't already in the list
- Safe to run after each conflict resolution step
- No side effects from repeated execution

## Edge Cases

### Multiple conflicts in same PR

If a PR has multiple commits that each have conflicts:

```bash
ghpr.py stage 1234
# Conflict in commit 1

vim file.c
git add file.c
ghpr.py stage --continue 1234
# Conflict in commit 2

vim file2.c
git add file2.c
ghpr.py stage --continue 1234
# PR staged successfully!
```

The `--continue` can be run multiple times, once for each conflicting commit.

### Config already saved

If metadata is already saved (e.g., from a previous failed attempt):
```python
if str(pr_number) not in prs:
    # Only save if not already present
    save_metadata()
```

This prevents duplicate entries in the config.

### Wrong PR number

If user provides wrong PR number during continue:
- The metadata might not match
- But the rebase will complete
- User should ensure they use the same PR number throughout

## Comparison with Shell Scripts

The original shell scripts (`ghpr-stage.sh`) required manual intervention:

1. Rebase would fail
2. User runs: `git rebase --continue`
3. User manually runs remaining commands
4. User manually updates config
5. User manually moves staging branch

Now it's just:
1. Rebase fails with clear instructions
2. User runs: `ghpr.py stage --continue <PR>`
3. Done!

## Testing

### Manual test

```bash
# Create a test conflict scenario
echo "test content" > testfile.txt
git add testfile.txt
git commit -m "Test" --trailer "Pull-Request: https://github.com/freebsd/freebsd-src/pull/9999"
git config --add branch.staging.opabinia.prs 9999

# Try to stage another PR that modifies the same file
# (In real scenario, use gh pr checkout)
# This will create a conflict

# Resolve it
vim testfile.txt
git add testfile.txt

# Continue
ghpr.py stage --continue 9999

# Verify
git log --oneline
ghpr.py status
```

## Future Enhancements

- [ ] Auto-detect PR number from rebase state (read from `.git/rebase-merge/head-name`)
- [ ] Dry-run mode to show what `--continue` will do
- [ ] Better detection of partial state (e.g., config saved but rebase not complete)
- [ ] Interactive conflict resolution guide
- [ ] Integration with `git mergetool`

## Error Messages

The implementation provides clear error messages:

**Better error output on initial conflict:**
```
======================================================================
REBASE FAILED - Conflicts need to be resolved
======================================================================

To resolve:
  1. Fix conflicts in the affected files
  2. Stage resolved files: git add <files>
  3. Continue staging: ghpr stage --continue 1234

Or to abort:
  git rebase --abort
======================================================================
```

**When --continue fails:**
```
Error: Rebase continue failed. Resolve conflicts and run 'ghpr stage --continue <PR>' again.
```

**When no rebase in progress:**
```
Error: No rebase in progress. Cannot continue.
```
