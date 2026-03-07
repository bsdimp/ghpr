# Unstage Command Implementation

## Overview

Added `ghpr.py unstage <PR>` command to remove a staged PR from the staging branch while preserving other staged PRs.

## How It Works

### 1. PR Identification
The command identifies commits belonging to a PR by searching for the `Pull-Request:` trailer in commit messages:

```
Pull-Request: https://github.com/freebsd/freebsd-src/pull/1234
```

This trailer is added automatically during `ghpr.py stage`.

### 2. Commit Removal Algorithm

```
1. Get all commits in staging branch (base..staging)
2. Find commits with matching Pull-Request trailer
3. Calculate: remaining_commits = all_commits - pr_commits
4. If no remaining commits:
   - Reset staging to base
5. Else:
   - Create temp branch from base
   - Cherry-pick remaining commits (in order)
   - Force-update staging to temp branch
   - Delete temp branch
```

### 3. Cleanup
- Deletes PR branch (`PR-1234`)
- Removes git config entries:
  - `branch.staging.opabinia.prs` (removes PR from list)
  - `branch.staging.opabinia.1234.*` (entire section)

## Usage

```bash
# Stage multiple PRs
ghpr.py stage 1234
ghpr.py stage 1235
ghpr.py stage 1236

# Remove one PR
ghpr.py unstage 1235

# Check what remains
ghpr.py status
```

## Edge Cases

### No commits found
If the PR was manually rebased and the trailer was lost:
- Warns user
- Proceeds with config cleanup only
- Leaves staging branch unchanged

### Cherry-pick conflicts
If remaining commits conflict when being cherry-picked:
- Cleans up temp branch
- Exits with error
- User must manually rebase

### Last PR unstaged
If unstaging the last PR:
- Resets staging to base
- Preserves branch initialization

## Implementation Details

### New Helper Methods

**GitConfig.unset()**
```python
def unset(key: str, value: Optional[str] = None) -> None
    """Remove a specific value from a multi-value config key"""
```

**GitHelper.get_commits_with_trailer()**
```python
def get_commits_with_trailer(base: str, head: str, trailer: str, value: str) -> List[str]
    """Find commits containing a specific trailer"""
```

**GitHelper.cherry_pick()**
```python
def cherry_pick(commits: List[str], allow_empty: bool = False) -> None
    """Cherry-pick a list of commits"""
```

### Command Flow

```
unstage(pr_number)
  ├─ Check if initialized
  ├─ Check if PR is staged
  ├─ Find PR commits by trailer
  ├─ Calculate remaining commits
  ├─ If remaining commits:
  │   ├─ Create temp branch from base
  │   ├─ Cherry-pick remaining commits
  │   └─ Move staging to temp branch
  ├─ Else:
  │   └─ Reset staging to base
  ├─ Delete PR branch
  ├─ Remove config entries
  └─ Show status
```

## Testing

Run smoke tests:
```bash
./test-ghpr.sh
```

Manual testing workflow:
```bash
# Initialize
ghpr.py init

# Mock staging (without actual PRs)
git checkout staging
echo "test" > file1.txt
git add file1.txt
git commit -m "Test 1" --trailer "Pull-Request: https://github.com/freebsd/freebsd-src/pull/1234"
git config --add branch.staging.opabinia.prs 1234

echo "test2" > file2.txt
git add file2.txt
git commit -m "Test 2" --trailer "Pull-Request: https://github.com/freebsd/freebsd-src/pull/1235"
git config --add branch.staging.opabinia.prs 1235

# Check status
ghpr.py status

# Unstage middle PR
ghpr.py unstage 1234

# Verify
git log main..staging --oneline
ghpr.py status
```

## Limitations

1. **Requires trailers**: PRs must have the Pull-Request trailer to be identified
2. **Order preservation**: Cherry-picking preserves commit order but may have conflicts
3. **Manual rebases**: If user manually rebased and changed commits, trailer matching may fail
4. **Interactive resolution**: No interactive conflict resolution - fails if cherry-pick conflicts

## Future Enhancements

- [ ] Interactive mode to confirm which commits to remove
- [ ] Dry-run mode to preview changes
- [ ] Better conflict resolution (guide user through conflicts)
- [ ] Support unstaging by commit hash instead of PR number
- [ ] Batch unstage multiple PRs at once
