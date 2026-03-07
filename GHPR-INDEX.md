# ghpr.py Documentation Index

Complete Python rewrite of FreeBSD GitHub PR landing tools.

## Start Here

📖 **[GHPR-QUICK-REFERENCE.md](GHPR-QUICK-REFERENCE.md)** - Quick start guide and command reference

## User Documentation

📘 **[GHPR-README.md](GHPR-README.md)** - Complete user guide
- Installation instructions
- Basic workflow
- All commands explained
- Examples and troubleshooting

## Implementation Details

🔧 **[GHPR-UNSTAGE.md](GHPR-UNSTAGE.md)** - How the `unstage` command works
- Algorithm explanation
- Edge cases
- Implementation details

🔧 **[GHPR-CONTINUE.md](GHPR-CONTINUE.md)** - How the `--continue` flag works
- Conflict resolution workflow
- Detection and recovery
- Error handling

📊 **[GHPR-STATUS.md](GHPR-STATUS.md)** - Development status
- Completed features
- Testing checklist
- Known limitations
- Future enhancements
- Migration plan

## Code

💻 **[ghpr.py](ghpr.py)** - Main implementation (~550 lines)
- Executable Python script
- Four helper classes
- Six commands
- Type hints throughout

🧪 **[test-ghpr.sh](test-ghpr.sh)** - Smoke tests
- Command structure validation
- Argument validation
- Python syntax check

## Original Shell Scripts

These are preserved in the `ghpr/` directory during the transition:
- `ghpr/ghpr-init.sh` - Initialize staging branch
- `ghpr/ghpr-stage.sh` - Stage PRs
- `ghpr/ghpr-push.sh` - Push and close
- `ghpr/README` - Original experimental warning

## Quick Command Reference

```bash
# Initialize
ghpr.py init

# Stage a PR
ghpr.py stage 1234

# Continue after conflicts
ghpr.py stage --continue 1234

# Remove a PR
ghpr.py unstage 1234

# Check status
ghpr.py status

# Push to FreeBSD
ghpr.py push

# Help
ghpr.py --help
ghpr.py <command> --help
```

## File Sizes

```
ghpr.py                25K  Main implementation
GHPR-README.md        6.3K  User guide
GHPR-CONTINUE.md      5.6K  Continue documentation
GHPR-STATUS.md        5.5K  Development status
GHPR-QUICK-REFERENCE  4.4K  Quick reference
GHPR-UNSTAGE.md       4.0K  Unstage documentation
test-ghpr.sh          1.4K  Smoke tests
```

## For Future Claude Code Instances

The main documentation has been added to **[CLAUDE.md](CLAUDE.md)** in the ghpr.py section.

Key points:
- ghpr.py replaces three shell scripts with unified Python tool
- Uses git config for state tracking
- Identifies commits by Pull-Request trailer
- Supports conflict resolution with --continue
- Can remove PRs with unstage command

## Testing Status

✅ Smoke tests pass
⏳ Manual testing with real PRs needed
⏳ Comparison with shell script behavior needed

See [GHPR-STATUS.md](GHPR-STATUS.md) for detailed testing checklist.

## Dependencies

- Python 3.6+ (standard library only)
- git command-line tool
- gh (GitHub CLI) - `pkg install gh`
- GitHub authentication - `gh auth login`
- FreeBSD src repository with 'freebsd' remote

## Support

If issues occur:
1. Check `ghpr.py --help` for command syntax
2. Check [GHPR-README.md](GHPR-README.md) troubleshooting section
3. Check [GHPR-STATUS.md](GHPR-STATUS.md) known limitations
4. Fallback to original shell scripts in `ghpr/` directory

## Version

Created: 2026-02-28
Status: Ready for testing
Python version: 3.6+
FreeBSD compatibility: Tested on FreeBSD 16.0-CURRENT
