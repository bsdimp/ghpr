# ghpr.py - GitHub Pull Request Landing Tool

Python-based tool to land GitHub pull requests into FreeBSD repositories.

## Requirements

- Python 3
- `git` command-line tool
- `gh` (GitHub CLI) - Install with `pkg install gh` or from https://cli.github.com
- GitHub authentication configured (`gh auth login`)
- FreeBSD git repository with `freebsd` remote

## Installation

Build from ports (`devel/ghpr`) or install the package once the package builders have caught up.

## Global Options

| Short | Long | |
| Option | Option | Description |
|--------|--------|-------------|
| -v | --verbose | Verbose mode |
| -n | --dry-run | Tell what would happen, but don't execute |

## Usage

### 1. Initialize Staging Branch

Create a staging branch for landing PRs:

```bash
ghpr init
```

This creates a branch named `staging` from `main` and marks it for PR landing operations.

### 2. Stage Pull Requests

Add one or more PRs to the staging branch:

```bash
# Stage a single PR
ghpr stage 1234

# Stage multiple PRs sequentially
ghpr stage 1234
ghpr stage 1235
ghpr stage 1236
```

For each PR, this will:
- Check if PR is already staged (prevents duplicate staging)
- Check out the PR into a temporary branch
- Rebase it onto the staging branch
- Add commit trailers (Reviewed-by, Pull-Request URL)
- Run style checker if available
- Update staging branch
- Add 'staged' label to the GitHub PR
- Display who approved the PR (if any)

**Options:**
- `--reviewer NAME` - Reviewer for Reviewed-by trailer (default: current user)
- `--repo NAME` - GitHub repo name (default: freebsd-src)
- `--editor CMD` - Editor for commit message fixups
- `--continue` - Continue an interrupted rebase after resolving conflicts
- `-f, --force` - Force staging even if PR is already staged

**Handling Conflicts:**

If the rebase encounters conflicts:

```bash
# 1. The rebase will stop and show you which files have conflicts
ghpr stage 1234
# ... conflicts occur ...

# 2. Resolve conflicts in your editor
vim conflicted-file.c

# 3. Stage the resolved files
git add conflicted-file.c

# 4. Continue the staging process
ghpr stage --continue 1234
```

### 3. Check Status

View what's staged:

```bash
ghpr status
```

### 4. Unstage a PR (Optional)

If you need to remove a PR from staging:

```bash
ghpr unstage 1234
```

This will:
- Identify commits belonging to the PR (by Pull-Request trailer)
- Rebuild the staging branch without those commits
- Remove 'staged' label from the GitHub PR
- Clean up PR branch and config
- Preserve other staged PRs

### 5. Push to FreeBSD

After reviewing all staged commits, push to FreeBSD and close the PRs:

```bash
ghpr push
```

This will:
- Push all staged commits to FreeBSD's main branch
- Retry with rebase if push fails due to new commits
- Close GitHub PRs with merge message
- Remove 'staged' label and add 'merged' label to PRs
- Clean up temporary branches and config

## Workflow Example

```bash
# One-time setup
ghpr init

# Stage PRs
ghpr stage 1234

# Stage another PR (with conflicts)
ghpr stage 1235
# ... rebase stops with conflicts ...

# Resolve conflicts
vim file.c
git add file.c

# Continue staging
ghpr stage --continue 1235

# Stage one more
ghpr stage 1236

# Review the commits
git log main..staging

# Oops, don't want 1235 after all
ghpr unstage 1235

# Check what's left
ghpr status

# Make any final edits
git rebase -i main

# Push everything
ghpr push

# Done! Staging branch is cleaned up automatically
```

## Configuration

The tool uses git config to track state:

```
branch.staging.opabinia = true
branch.staging.opabinia.base = main
branch.staging.opabinia.prs = 1234 1235
branch.staging.opabinia.1234.upstream = origin
branch.staging.opabinia.1234.upstream-branch = patch-1
```

## GitHub Label Tracking

The tool automatically manages GitHub labels to track PR lifecycle:

- **'staged' label** - Added when a PR is staged for landing, removed when unstaged or merged
- **'merged' label** - Added when a PR is successfully pushed to FreeBSD main

When attempting to stage a PR that's already staged, the tool will:
- Report that the PR is already staged
- Display any assigned users from GitHub
- Require `--force` flag to override

If a PR has a stale 'staged' label but isn't actually in the local staging branch, the tool will warn but continue staging.

## Advanced Options

### Custom Staging Branch

Use a different branch name:

```bash
ghpr --staging-branch my-landing init
ghpr --staging-branch my-landing stage 1234
ghpr --staging-branch my-landing push
```

### Push to PR Branches (Experimental)

Also push to the original PR branches:

```bash
ghpr push --push-pr-branches
```

## Differences from Shell Scripts

### Improvements

1. **Unified interface** - Single command with subcommands instead of three scripts
2. **Better error handling** - Python exceptions with clear messages
3. **Status command** - See what's staged before pushing
4. **Type safety** - Catches errors earlier with type hints
5. **Extensibility** - Easy to add new features in Python
6. **Help text** - Built-in `--help` for all commands

### Behavioral Changes

- Interactive rebase during stage uses `-i` flag (matches original)
- Style checker errors are warnings, not failures
- Better handling of missing branches and config

## Troubleshooting

### "Branch staging has not been initialized"

Run `ghpr init` first.

### "Failed to checkout PR"

Make sure:
- `gh` CLI is installed and authenticated
- You have access to the repository
- PR number is correct

### Rebase conflicts during stage

If rebase fails during `stage`:
1. Resolve conflicts manually: `vim <conflicted-files>`
2. Stage resolved files: `git add <files>`
3. Continue: `ghpr stage --continue <PR>`

Alternatively, to abort:
```bash
git rebase --abort
```

### Rebase conflicts during push

If rebase fails during `push`:
1. Resolve conflicts manually
2. `git rebase --continue`
3. Re-run `ghpr push`

### Cherry-pick conflicts during unstage

If unstage fails while rebuilding the staging branch:
1. The operation will be rolled back
2. You can manually rebase to remove the PR
3. Or use `git rebase -i main` to interactively remove commits

### "PR is already staged"

If you try to stage a PR that's already in the staging branch:
- The tool will show you who the PR is assigned to (if anyone)
- Use `ghpr unstage <PR>` to remove it first
- Or use `ghpr stage --force <PR>` to override (not recommended)

If the PR has a 'staged' label but isn't actually staged:
- The tool will warn about the stale label
- Staging will continue normally
- The label will be refreshed

## Development Notes

### Future Enhancements

From the original scripts' TODO comments:

- [ ] Scrape PR for GitHub approvals and translate to FreeBSD names
- [ ] Auto-bump `.Dd` dates in man pages
- [ ] Run igor (man page linter) before/after
- [ ] Support staging multiple PRs at once with single command
- [ ] Dry-run mode to preview operations
- [ ] Better conflict resolution hints

### Editor Hook

The `--editor` option or `$HOME/bin/git-fixup-editor` can be used to automatically edit commit messages during rebase. This is useful for:
- Fixing commit message formatting
- Adding missing metadata
- Standardizing commit titles
