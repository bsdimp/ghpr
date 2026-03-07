# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Context

This is the `/tools/tools/git` directory of the FreeBSD src repository. It contains tools for FreeBSD committers to integrate git with FreeBSD project workflows, particularly for working with Phabricator (reviews.freebsd.org) and managing code reviews.

## Key Tools

### ghpr.py
**NEW** - Unified Python tool for landing GitHub Pull Requests into FreeBSD repositories. Replaces three shell scripts (ghpr-init.sh, ghpr-stage.sh, ghpr-push.sh) with a single command-line tool.

**Commands:**
- `ghpr.py init` - Initialize staging branch for PR landing
- `ghpr.py stage <PR> [--continue]` - Stage a PR for landing (with conflict resolution support)
- `ghpr.py unstage <PR>` - Remove a staged PR from the staging branch
- `ghpr.py status` - Show what's currently staged
- `ghpr.py push [--push-pr-branches]` - Push staged PRs to FreeBSD and close them on GitHub

**Dependencies:**
- Python 3.6+
- `gh` (GitHub CLI) - Install with `pkg install gh`
- `git` command-line tool
- GitHub authentication configured (`gh auth login`)

**Workflow:**
```bash
# One-time setup
ghpr.py init

# Preview what a command would do (dry-run mode)
ghpr.py -n stage 1234

# See all commands being executed (verbose mode)
ghpr.py -v stage 1234

# Combine for detailed preview
ghpr.py -v -n push

# Stage PRs
ghpr.py stage 1234

# If conflicts occur during rebase
vim conflicted-file.c
git add conflicted-file.c
ghpr.py stage --continue 1234

# Check status
ghpr.py status

# Remove a PR if needed
ghpr.py unstage 1234

# Push to FreeBSD
ghpr.py push
```

**Global Options:**
- `-v, --verbose` - Print all commands before executing them
- `-n, --dry-run` - Preview operations without executing any commands (shows what would happen based on default code paths, not current repository state)

**Architecture:**
- Uses git config to track state: `branch.staging.opabinia.*`
- Identifies PR commits by `Pull-Request:` trailer in commit messages
- Rebases PRs onto staging branch with automatic trailer addition
- Cherry-picks for unstaging to preserve commit order
- Handles conflict resolution with `--continue` flag

**Key Implementation Classes:**
- `GitConfig` - Git config operations (get, set, unset)
- `GitHelper` - Git command wrappers (checkout, rebase, cherry-pick, etc.)
- `GHHelper` - GitHub CLI wrappers (pr checkout, edit, close)
- `GHPR` - Main orchestration class with all commands

See `GHPR-README.md` for detailed usage and `GHPR-CONTINUE.md` / `GHPR-UNSTAGE.md` for implementation details.

### git-arc.sh
The primary tool for managing Phabricator reviews from git commits. This is a shell script that wraps Arcanist (`arc`) to simplify creating and updating Differential reviews.

**Commands:**
- `git arc create [-l] [-r reviewer1,...] [-s subscriber1,...] [-p parent] <commit-ref>...` - Create Differential reviews from commits
- `git arc update [-l] [-m message] <commit-ref>...` - Update existing reviews with new diffs
- `git arc list <commit-ref>...` - Show review status for commits
- `git arc patch [-bcrs] <diff1> [<diff2> ...]` - Apply patches from reviews
- `git arc stage [-b branch] <commit-ref>...` - Prepare commits for pushing upstream (adds review tags)

**Dependencies:**
- `devel/arcanist-lib` (FreeBSD port) - Provides the `arc` command at `/usr/local/lib/php/arcanist/bin/arc`
- `textproc/jq` - JSON processing
- `devel/git`

### arcgit (Legacy)
Older wrapper script around `arc` for creating review series. Documented in the HOWTO file. Still present but `git-arc.sh` is the modern approach.

### mfc-candidates.lua
Lua script (using FreeBSD's `flua`) to identify commits that are candidates for MFC (Merge From Current). Compares a "from" branch (typically main) with a "to" branch (typically stable/*) to find commits not yet cherry-picked.

**Usage:**
```
./mfc-candidates.lua [-a] [-f from_branch] [-t to_branch] [-u user] [-X exclude_file] [path ...]
```

**Options:**
- `-a` - All authors (default is current user)
- `-f from_branch` - Source branch (default: freebsd/main or appropriate for repo)
- `-t to_branch` - Target branch (auto-detected for stable/releng)
- `-u user` - Filter by specific user
- `-X exclude_file` - File with hashes to exclude
- `-F git-show-fmt` - Custom format for output
- `-v` - Verbose output

### sanitize.lua
Lua script to strip comments and whitespace from C header files, typically used for importing device-tree bindings or minimal interface definitions.

**Usage:**
```
lua sanitize.lua <filename> [description...]
```

Outputs sanitized content to stdout with a generated-from header.

## Development Workflow

### Creating Reviews
1. Ensure commit titles are unique across your open reviews (git-arc matches commits to reviews by title)
2. Create review: `git arc create -r reviewer1,reviewer2 HEAD` or `git arc create HEAD~3..HEAD` for a series
3. Reviews are matched to commits by title - keep them synchronized if you change either

### Updating Reviews
1. Amend your commit with changes: `git commit --amend`
2. Update the review: `git arc update HEAD`
3. Add update message with `-m "message"` or use editor

### Staging for Commit
After review approval:
1. `git arc stage HEAD` - Cherry-picks commit, adds "Reviewed by:" and "Differential Revision:" tags
2. Edit commit message to add other metadata (MFC after, Sponsored by, etc.)
3. Push to upstream: `git push freebsd HEAD:main`

## Commit Message Format

FreeBSD uses structured commit metadata. See `hooks/prepare-commit-msg` for the template. Common tags:
- `Reviewed by:` - Reviewers who approved (added by `git arc stage`)
- `Differential Revision:` - Phabricator URL (added by `git arc stage`)
- `MFC after:` - Time until merge to stable (e.g., "3 days", "1 week")
- `Sponsored by:` - Organization funding
- `Fixes:` - Short hash of commit being fixed
- `PR:` - Problem Report number
- `Pull Request:` / `Closes:` - Full GitHub PR URL

## Architecture Notes

### git-arc.sh Implementation
- Uses Arcanist's Conduit API via `arc call-conduit` for querying Phabricator
- Maintains one-to-one mapping between commits and Differential revisions
- Matches reviews by commit title (via `title2diff()` function)
- Fallback: searches commit message for "Differential Revision: D####"
- Uses `jq` extensively for JSON parsing of API responses
- Temporary files created in `$GITARC_TMPDIR` (cleaned up on exit)

### Key Functions in git-arc.sh
- `commit2diff()` - Find Differential revision for a commit (by log or title)
- `diff2phid()` / `phid2diff()` - Convert between D#### and PHID identifiers
- `diff2reviewers()` - Extract reviewers who accepted a review
- `diff2status()` - Get review status
- `create_one_review()` - Create a single review from a commit
- `patch_commit()` - Create a commit from a review (with author heuristics)

### Author Detection (patch_commit)
When applying patches, `find_author()` attempts to determine the correct author:
1. Check if FreeBSD committer (no '.' in Phabricator username)
2. Use author_name/author_addr from bundle metadata if available
3. Search git log for similar email (username with _ → .)
4. Search git log for matching name (excluding generic "user" names)
5. Prompt user if uncertain

## Testing

No formal test suite. Manual testing against Phabricator instance required. The `-v` flag enables verbose output for debugging.

## Build

Install via FreeBSD Makefile:
```
make install  # Installs git-arc.sh to /usr/local/bin and man page git-arc.1
```

The Makefile uses BSD make syntax (`bsd.prog.mk`).

## Configuration

Git config options (via `git config`):
- `arc.assume-yes` - Auto-answer yes to prompts (default: false)
- `arc.browse` - Open reviews in browser (default: false)
- `arc.list` - Use list mode for create/update (default: false)
- `arc.verbose` - Verbose output (default: false)

Environment variables:
- `LOCALBASE` - Override base directory for ports (default: /usr/local)
- `ARC_CMD` - Override arc command path
- `GIT_EDITOR` - Editor for commit messages
- `GIT_PAGER` - Pager for output

## Important Constraints

1. **Commit titles must be unique** across all your open reviews - this is how git-arc matches commits to reviews
2. **Clean working tree required** for most operations (except list and patch)
3. **FreeBSD-specific** - Hardcoded for reviews.freebsd.org Phabricator instance
4. **Interactive operations** - Many commands prompt for confirmation unless `-y` or `arc.assume-yes` is set
5. **No interactive rebase** - Don't use `git rebase -i` or `git add -i` in scripts
