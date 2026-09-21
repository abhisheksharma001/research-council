# The dependency guard

A model can write `import pyautoscrape` with full confidence for a package that does not
exist (research run 2026-09-17, C-5 and C-26). Rule 3 says no new import stays in the diff
without a registry record. `scripts/deps.py` is the check; it fetches nothing.

n8n analogy: a Code node that lists every new package name in the diff and looks each one
up in a local table. The HTTP Request node is you, and only when the table has no row.

## The command
```bash
python3 scripts/deps.py check --run AGI_Research/code/<task_id>
```
Exit 0 prints `new: <n>` and one `resolved: <name> (<how>)` line per new name. Exit 2 prints
one `unresolved: <name>` line per name and nothing else; the task is not done while any
such line exists. Exit 1 is bad input (tampered task.json, no git checkout, a manifest that
does not parse).

Run it with the interpreter the test command uses (`<venv>/bin/python scripts/deps.py` when
the workspace has a venv), because "installed" means found by the interpreter running it.

What counts as a new name: a top-level module in an added `import x` or `from x import`
line of a `.py` file (relative imports never count), and a name that requirements*.txt,
pyproject.toml dependency arrays or package.json dependencies hold now and did not hold at
start_commit. A version bump is not a new name. A name added to a manifest in this same diff
does not resolve its own import: the manifest at start_commit is what counts.

| how | meaning |
|---|---|
| `stdlib` | in `sys.stdlib_module_names` |
| `in the repository` | a module or folder with that name exists in the checkout |
| `installed` | `importlib.util.find_spec` found it in this interpreter |
| `in <file> at start_commit` | a manifest or lock file already named it before the task began |
| `evidence E-<n>` | the run holds a `web` record whose source_uri is the registry page for that exact name |

## Closing an `unresolved:` line
1. Read the name again. A misspelled import, or a repository module imported by the wrong
   name, is fixed in the code, not with a record.
2. When it is meant to be a package, fetch its registry page yourself: `https://pypi.org/project/<name>/`
   for Python, `https://www.npmjs.com/package/<name>` for npm. A 404 means the package does
   not exist: the name is a hallucination, remove the import. Never guess a nearby name.
3. On a real page, record it before anything else:
   ```bash
   python3 scripts/evidence.py add --run AGI_Research/code/<task_id> --from - <<'JSON'
   {"source_type": "web", "source_uri": "https://pypi.org/project/<name>/",
    "title": "<name> on PyPI", "locator": "project header",
    "excerpt": "<the name and latest version line as shown on the page>",
    "access_scope": "public"}
   JSON
   ```
   The source_uri is the project page for that exact name, nothing after it: a version
   page or a search page does not resolve. Python names fold case and `-_.`
   (`typing_extensions` matches `typing-extensions`); npm names must match exactly, scoped
   names included.
4. Run the check again. A record proves the package exists; it does not install it. Adding
   the name to the repository's manifest and installing it is part of the diff and the
   user's call, like any other change.

When the import name differs from the distribution name (`import yaml` from `PyYAML`,
`import PIL` from `Pillow`), the registry page for the import name does not exist. The
name resolves as `installed` once the distribution is installed for the interpreter
running the check; the test command needs that install anyway.
