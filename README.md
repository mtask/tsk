# tsk

A minimal **command-line task manager** backed by any **CalDAV server** (Nextcloud, iCloud, Radicale, etc.). Taskwarrior-style subcommands, colored table output, persistent active project.

---

## Features

- Subcommand CLI (`add`, `list`, `next`, `show`, `done`, `del`, `edit`, `move`, `project`)
- Persistent active project — set once with `use`, omit project on every command
- `@project` prefix on `add` to override active project inline
- Flags and task text can appear in any order on `add`
- Sorted output — due date ascending (nulls last), then priority high-first
- Rich colored table (red=overdue, yellow=due today, bold=high priority)
- Filter by priority, overdue, or due today; `--all` to include completed tasks
- Notes/description field per task (`--note`)
- Full task detail view with `show`
- Move tasks between projects with `move`
- Edit summary, priority, due date, or notes in place
- Create new CalDAV calendars and config entries with `project add`
- Auto-discovers config at `~/.config/tasker/conf.yaml`
- Compatible with Apple Reminders and other CalDAV clients

---

## Installation

```bash
git clone <repo>
cd tsk
python3 -m venv venv
source venv/bin/activate
pip install caldav pyyaml rich

# Install the command to ~/.local/bin (no root needed)
ln -s "$PWD/tsk" ~/.local/bin/tsk
```

Make sure `~/.local/bin` is on your `PATH`. On most modern Linux distros it is by default. If not, add to `~/.bashrc` or `~/.profile`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Requires Python 3.8+.

---

## Configuration

Place `conf.yaml` at `~/.config/tasker/conf.yaml` (auto-discovered) or pass with `-c`:

```yaml
projects:
  inbox:
    url: https://radicale.example.com/user/inbox/
    username: user
    password: secret
  work:
    url: https://radicale.example.com/user/work/
    username: user
    password: secret
```

```bash
tsk -c /path/to/conf.yaml <command>
# or
export TASK_CONFIG_PATH=~/path/to/conf.yaml
```

---

## Usage

### Set active project

```bash
tsk use inbox
```

The active project is stored in `~/.local/share/tasker/state.json` and used by all subsequent commands.

### Add a task

```bash
tsk add "Buy milk"
tsk add -p high --due tomorrow "Fix bug"
tsk add @work "Prepare slides"        # override active project
tsk add --note "Check expiry" "Buy milk"  # with notes
```

Flags and text can appear in any order:

```bash
tsk add @koti -p high --due 2026-03-31 "Pyydä vakuutustarjous"
```

### List tasks

```bash
tsk list                  # active project, sorted by due then priority
tsk list work             # specific project
tsk list -p high          # filter by priority
tsk list --overdue        # overdue only
tsk list --today          # due today only
tsk list --all            # include completed tasks
```

Output is a colored table, sorted by due date (soonest first), then priority:

```
         Project: inbox
 #  Summary          Pri     Due
 1  Fix bug          high    tomorrow
 2  Submit report    medium  in 3d
 3  Buy milk
```

### Show full task details

```bash
tsk show 1
```

```
Summary:  Fix bug
Priority: high
Due:      2026-03-15  (tomorrow)
Status:   NEEDS-ACTION
Note:     Affects login flow
```

### Show urgent tasks

```bash
tsk next
```

Shows overdue + due today + high priority tasks.

### Complete a task

```bash
tsk done 2
```

### Delete a task

```bash
tsk del 2
```

### Edit a task

```bash
tsk edit 1 --summary "Updated text"
tsk edit 1 -p medium
tsk edit 1 --due tomorrow
tsk edit 1 --due none         # clear due date
tsk edit 1 --note "New note"
tsk edit 1 --note none        # clear note
```

### Move a task to another project

```bash
tsk move 1 work
tsk move 1 @work              # @ prefix accepted too
```

### Manage projects

```bash
tsk project list              # list configured projects (* = active)
tsk project add newproject    # create CalDAV calendar + add to conf.yaml
```

---

## Priority Mapping

| CLI Option | iCalendar `PRIORITY` |
|-----------|---------------------|
| `high`    | 1                   |
| `medium`  | 5                   |
| `low`     | 9                   |

---

## Due Date Formats

| Format       | Description             |
|--------------|-------------------------|
| `10m`        | 10 minutes from now     |
| `2h`         | 2 hours from now        |
| `3d`         | 3 days from now         |
| `tomorrow`   | Tomorrow at 9:00 AM     |
| `tomorrow 9` | Tomorrow at 9:00 AM     |
| `YYYY-MM-DD` | Specific date           |

---

## Testing

```bash
# Unit tests (no CalDAV needed)
venv/bin/python -m pytest test_tsk.py -m "not integration"

# Integration tests (requires TASK_CONFIG_PATH and a live CalDAV server)
# Uses a calendar named TEST, created and cleaned up automatically
TASK_CONFIG_PATH=~/.config/tasker/conf.yaml \
  venv/bin/python -m pytest test_tsk.py -m integration -v
```

---

## License

MIT License — free to use, modify, and distribute.
