# smart-bookmark

A tiny CLI bookmark manager, stdlib-only.

## Install

```bash
pip install -e .
```

## Usage

```bash
bookmark add https://example.com --tag news --title "Example"
bookmark list
bookmark list --tag news
bookmark list --search example
bookmark remove 1
bookmark open 2
```

Or run as module:

```bash
python -m smart_bookmark list
```

Data is stored at `~/.smart-bookmark/bookmarks.json`.

## Run tests

```bash
pytest -v
```
