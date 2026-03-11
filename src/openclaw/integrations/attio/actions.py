"""
Attio actions for OpenClaw.

Actions exposed:
  attio_search   <companies|people> <query>        – full-text record search
  attio_note     <object> <record_id> <title> | <body>  – attach a note to a record
  attio_task     <content> [linked:<object>:<record_id>] – create a task
  attio_tasks    [open|done]                        – list tasks
  attio_upsert   <companies|people> <email_or_domain> <json_values>  – create/update record

All actions respect dry_run mode: they log intent and return a stub result
without hitting the Attio API.
"""

from __future__ import annotations

import json

from openclaw.actions.base import ActionResult, BaseAction
from openclaw.integrations.attio.client import AttioClient
from openclaw.logging import get_logger

logger = get_logger(__name__)


def _make_client(api_key: str) -> AttioClient:
    return AttioClient(api_key=api_key)


# ── attio_search ──────────────────────────────────────────────────────────

class AttioSearchAction(BaseAction):
    """
    Search Attio records.

    Usage:  attio_search <companies|people> <query>
    Example: attio_search companies Acme
    """

    name = "attio_search"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        parts = args.split(None, 1)
        if len(parts) < 2:
            return ActionResult(
                success=False,
                error="Usage: attio_search <companies|people> <query>",
            )
        object_type, query = parts[0].lower(), parts[1]

        if dry_run:
            logger.info("DRY RUN attio_search", extra={"object": object_type, "query": query})
            return ActionResult(
                success=True,
                output=f"[dry_run] would search {object_type} for: {query}",
            )

        client = _make_client(self._api_key)
        try:
            records = await client.search_records(object_type, query)
            if not records:
                return ActionResult(success=True, output=f"No {object_type} found for '{query}'.")
            lines = [f"Found {len(records)} {object_type}:"]
            for r in records:
                record_id = r.get("id", {}).get("record_id", "?")
                # Try to get a display name
                vals = r.get("values", {})
                name_val = (
                    vals.get("name", [{}])[0].get("full_name")
                    or vals.get("name", [{}])[0].get("value")
                    or record_id
                )
                lines.append(f"  [{record_id}] {name_val}")
            return ActionResult(success=True, output="\n".join(lines))
        except Exception as exc:
            return ActionResult(success=False, error=str(exc))
        finally:
            await client.close()


# ── attio_note ────────────────────────────────────────────────────────────

class AttioNoteAction(BaseAction):
    """
    Attach a note to an Attio record.

    Usage:  attio_note <object> <record_id> <title> | <body>
    Example: attio_note companies abc-123 Call summary | Discussed pricing.
    The pipe | separates the title from the body.
    """

    name = "attio_note"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        # Split: object record_id title | body
        parts = args.split(None, 2)
        if len(parts) < 3 or "|" not in parts[2]:
            return ActionResult(
                success=False,
                error="Usage: attio_note <object> <record_id> <title> | <body>",
            )
        object_type = parts[0].lower()
        record_id = parts[1]
        title_body = parts[2].split("|", 1)
        title = title_body[0].strip()
        body = title_body[1].strip()

        if dry_run:
            logger.info(
                "DRY RUN attio_note",
                extra={"object": object_type, "record_id": record_id, "title": title},
            )
            return ActionResult(
                success=True,
                output=f"[dry_run] would create note '{title}' on {object_type}/{record_id}",
            )

        client = _make_client(self._api_key)
        try:
            note = await client.create_note(object_type, record_id, title, body)
            note_id = note.get("id", {}).get("note_id", "?")
            return ActionResult(success=True, output=f"Note created: {note_id}")
        except Exception as exc:
            return ActionResult(success=False, error=str(exc))
        finally:
            await client.close()


# ── attio_task ────────────────────────────────────────────────────────────

class AttioTaskAction(BaseAction):
    """
    Create a task in Attio.

    Usage:  attio_task <content> [linked:<object>:<record_id>] [due:<ISO8601>]
    Example: attio_task Follow up on quote linked:companies:abc-123 due:2026-03-20T00:00:00Z
    """

    name = "attio_task"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        if not args.strip():
            return ActionResult(success=False, error="Usage: attio_task <content> [linked:<obj>:<id>] [due:<ISO>]")

        tokens = args.split()
        content_parts = []
        linked_object = None
        linked_record_id = None
        deadline_at = None

        for tok in tokens:
            if tok.startswith("linked:"):
                _, obj, rid = tok.split(":", 2)
                linked_object = obj
                linked_record_id = rid
            elif tok.startswith("due:"):
                deadline_at = tok[4:]
            else:
                content_parts.append(tok)

        content = " ".join(content_parts)

        if dry_run:
            logger.info("DRY RUN attio_task", extra={"content": content})
            return ActionResult(success=True, output=f"[dry_run] would create task: {content}")

        client = _make_client(self._api_key)
        try:
            task = await client.create_task(content, linked_object, linked_record_id, deadline_at)
            task_id = task.get("id", {}).get("task_id", "?")
            return ActionResult(success=True, output=f"Task created: {task_id} — {content}")
        except Exception as exc:
            return ActionResult(success=False, error=str(exc))
        finally:
            await client.close()


# ── attio_tasks ───────────────────────────────────────────────────────────

class AttioTasksAction(BaseAction):
    """
    List open or completed tasks.

    Usage:  attio_tasks [open|done]
    Default: open
    """

    name = "attio_tasks"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        completed = args.strip().lower() == "done"

        if dry_run:
            return ActionResult(
                success=True,
                output=f"[dry_run] would list {'done' if completed else 'open'} tasks",
            )

        client = _make_client(self._api_key)
        try:
            tasks = await client.list_tasks(is_completed=completed)
            if not tasks:
                label = "done" if completed else "open"
                return ActionResult(success=True, output=f"No {label} tasks found.")
            lines = [f"{'Done' if completed else 'Open'} tasks ({len(tasks)}):"]
            for t in tasks:
                task_id = t.get("id", {}).get("task_id", "?")
                content = t.get("content", "?")
                deadline = t.get("deadline_at") or "no deadline"
                lines.append(f"  [{task_id}] {content} — {deadline}")
            return ActionResult(success=True, output="\n".join(lines))
        except Exception as exc:
            return ActionResult(success=False, error=str(exc))
        finally:
            await client.close()


# ── attio_upsert ──────────────────────────────────────────────────────────

class AttioUpsertAction(BaseAction):
    """
    Create or update an Attio record.

    Usage:  attio_upsert <companies|people> <matching_value> <json_values>
    Example: attio_upsert companies acme.com {"name":[{"value":"Acme Corp"}]}

    The matching attribute is inferred:
      companies → domains
      people    → email_addresses
    """

    name = "attio_upsert"

    _MATCHING = {"companies": "domains", "people": "email_addresses"}

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        parts = args.split(None, 2)
        if len(parts) < 3:
            return ActionResult(
                success=False,
                error="Usage: attio_upsert <companies|people> <matching_value> <json_values>",
            )
        object_type = parts[0].lower()
        matching_value = parts[1]
        json_str = parts[2]

        matching_attr = self._MATCHING.get(object_type)
        if not matching_attr:
            return ActionResult(
                success=False,
                error=f"Unsupported object type '{object_type}'. Use 'companies' or 'people'.",
            )

        try:
            values = json.loads(json_str)
        except json.JSONDecodeError as exc:
            return ActionResult(success=False, error=f"Invalid JSON values: {exc}")

        # Inject the matching value if not already present
        if matching_attr not in values:
            values[matching_attr] = [{"value": matching_value}]

        if dry_run:
            logger.info(
                "DRY RUN attio_upsert",
                extra={"object": object_type, "matching_value": matching_value},
            )
            return ActionResult(
                success=True,
                output=f"[dry_run] would upsert {object_type} matching {matching_value}",
            )

        client = _make_client(self._api_key)
        try:
            record = await client.upsert_record(object_type, matching_attr, values)
            record_id = record.get("id", {}).get("record_id", "?")
            return ActionResult(success=True, output=f"Record upserted: {object_type}/{record_id}")
        except Exception as exc:
            return ActionResult(success=False, error=str(exc))
        finally:
            await client.close()


# ── Factory ───────────────────────────────────────────────────────────────

def build_attio_actions(api_key: str) -> list[BaseAction]:
    """Return all Attio actions, ready to register."""
    return [
        AttioSearchAction(api_key),
        AttioNoteAction(api_key),
        AttioTaskAction(api_key),
        AttioTasksAction(api_key),
        AttioUpsertAction(api_key),
    ]
