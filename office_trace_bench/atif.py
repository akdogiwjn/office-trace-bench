#!/usr/bin/env python3
"""Convert one OpenClaw session JSONL file to an ATIF-v1.7 trajectory."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class ExportError(ValueError):
    """Raised when an OpenClaw session cannot be converted safely."""


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ExportError(
                    f"{path}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(record, dict):
                raise ExportError(
                    f"{path}:{line_number}: each JSONL record must be an object"
                )
            records.append(record)
    if not records:
        raise ExportError(f"{path}: session is empty")
    return records


def joined_content(parts: Any, field: str) -> str:
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return "" if parts is None else json.dumps(parts, ensure_ascii=False)

    values: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get(field), str):
            values.append(part[field])
        elif field == "text" and isinstance(part, dict):
            part_type = part.get("type", "unknown")
            if part_type not in {"thinking", "toolCall"}:
                values.append(json.dumps(part, ensure_ascii=False))
    return "\n\n".join(value for value in values if value)


def tool_arguments(value: Any, call_id: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            return decoded
    raise ExportError(f"tool call {call_id!r} has non-object arguments")


def model_name(provider: Any, model: Any, include_provider: bool) -> str | None:
    if not isinstance(model, str) or not model:
        return None
    if include_provider and isinstance(provider, str) and provider:
        prefix = f"{provider}/"
        return model if model.startswith(prefix) else prefix + model
    return model


def usage_metrics(usage: Any) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None

    uncached = int(usage.get("input") or 0)
    cached = int(usage.get("cacheRead") or 0)
    completion = int(usage.get("output") or 0)
    metrics: dict[str, Any] = {
        # ATIF prompt_tokens includes cached and non-cached input tokens.
        "prompt_tokens": uncached + cached,
        "completion_tokens": completion,
        "cached_tokens": cached,
    }

    cost = usage.get("cost")
    if isinstance(cost, dict) and isinstance(cost.get("total"), (int, float)):
        metrics["cost_usd"] = cost["total"]

    extra: dict[str, Any] = {"non_cached_prompt_tokens": uncached}
    for source, target in (
        ("cacheWrite", "cache_write_tokens"),
        ("reasoningTokens", "reasoning_tokens"),
        ("totalTokens", "openclaw_total_tokens"),
    ):
        if isinstance(usage.get(source), (int, float)):
            extra[target] = usage[source]
    metrics["extra"] = extra
    return metrics


def observation_extra(message: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "tool_name": message.get("toolName"),
        "is_error": bool(message.get("isError", False)),
        "openclaw_message_id": record.get("id"),
    }
    details = message.get("details")
    if isinstance(details, dict):
        # `aggregated` duplicates the observation text and can be very large.
        compact_details = {
            key: value for key, value in details.items() if key != "aggregated"
        }
        if compact_details:
            extra["details"] = compact_details
    return {key: value for key, value in extra.items() if value is not None}


def convert(
    records: list[dict[str, Any]], agent_name: str, agent_version: str
) -> dict[str, Any]:
    session_record = next(
        (record for record in records if record.get("type") == "session"), None
    )
    if session_record is None or not isinstance(session_record.get("id"), str):
        raise ExportError("missing OpenClaw session record or session id")

    provider: str | None = None
    default_model: str | None = None
    thinking_level: str | None = None
    for record in records:
        if record.get("type") == "model_change":
            provider = record.get("provider") or provider
            default_model = record.get("modelId") or default_model
        elif record.get("type") == "custom" and record.get("customType") == "model-snapshot":
            data = record.get("data")
            if isinstance(data, dict):
                provider = data.get("provider") or provider
                default_model = data.get("modelId") or default_model
        elif record.get("type") == "thinking_level_change":
            thinking_level = record.get("thinkingLevel") or thinking_level

    steps: list[dict[str, Any]] = []
    pending_calls: dict[str, dict[str, Any]] = {}
    seen_call_ids: set[str] = set()

    for record in records:
        if record.get("type") != "message":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            raise ExportError(f"message record {record.get('id')!r} has no message object")
        role = message.get("role")

        if role in {"user", "system"}:
            extra = {
                "openclaw_message_id": record.get("id"),
                "openclaw_parent_id": record.get("parentId"),
            }
            steps.append(
                {
                    "step_id": len(steps) + 1,
                    "timestamp": record.get("timestamp"),
                    "source": role,
                    "message": joined_content(message.get("content"), "text"),
                    "extra": {
                        key: value for key, value in extra.items() if value is not None
                    },
                }
            )
            continue

        if role == "assistant":
            content = message.get("content")
            if not isinstance(content, list):
                raise ExportError(
                    f"assistant message {record.get('id')!r} has non-array content"
                )

            calls: list[dict[str, Any]] = []
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "toolCall":
                    continue
                call_id = part.get("id")
                name = part.get("name")
                if not isinstance(call_id, str) or not call_id:
                    raise ExportError("tool call is missing a string id")
                if not isinstance(name, str) or not name:
                    raise ExportError(f"tool call {call_id!r} is missing a function name")
                if call_id in seen_call_ids:
                    raise ExportError(f"duplicate tool call id {call_id!r}")
                call: dict[str, Any] = {
                    "tool_call_id": call_id,
                    "function_name": name,
                    "arguments": tool_arguments(part.get("arguments"), call_id),
                }
                calls.append(call)
                seen_call_ids.add(call_id)

            step: dict[str, Any] = {
                "step_id": len(steps) + 1,
                "timestamp": record.get("timestamp"),
                "source": "agent",
                "model_name": model_name(
                    message.get("provider"), message.get("model"), False
                )
                or default_model,
                "message": joined_content(content, "text"),
                "llm_call_count": 1,
                "extra": {
                    "openclaw_message_id": record.get("id"),
                    "openclaw_parent_id": record.get("parentId"),
                    "api": message.get("api"),
                    "response_id": message.get("responseId"),
                    "stop_reason": message.get("stopReason"),
                },
            }
            reasoning = joined_content(content, "thinking")
            if reasoning:
                step["reasoning_content"] = reasoning
            if calls:
                step["tool_calls"] = calls
                step["observation"] = {"results": []}
            metrics = usage_metrics(message.get("usage"))
            if metrics is not None:
                step["metrics"] = metrics
            step["extra"] = {
                key: value for key, value in step["extra"].items() if value is not None
            }
            steps.append(step)
            for call in calls:
                pending_calls[call["tool_call_id"]] = step
            continue

        if role == "toolResult":
            call_id = message.get("toolCallId")
            if not isinstance(call_id, str) or call_id not in pending_calls:
                raise ExportError(
                    f"tool result {record.get('id')!r} references unknown call {call_id!r}"
                )
            step = pending_calls.pop(call_id)
            step["observation"]["results"].append(
                {
                    "source_call_id": call_id,
                    "content": joined_content(message.get("content"), "text"),
                    "extra": observation_extra(message, record),
                }
            )
            continue

        raise ExportError(f"unsupported OpenClaw message role {role!r}")

    if pending_calls:
        missing = ", ".join(sorted(pending_calls))
        raise ExportError(f"missing tool results for: {missing}")
    if not steps:
        raise ExportError("session contains no user, system, or agent steps")

    agent_steps = [step for step in steps if step["source"] == "agent"]
    final_metrics = {
        "total_prompt_tokens": sum(
            step.get("metrics", {}).get("prompt_tokens", 0) for step in agent_steps
        ),
        "total_completion_tokens": sum(
            step.get("metrics", {}).get("completion_tokens", 0) for step in agent_steps
        ),
        "total_cached_tokens": sum(
            step.get("metrics", {}).get("cached_tokens", 0) for step in agent_steps
        ),
        "total_cost_usd": sum(
            step.get("metrics", {}).get("cost_usd", 0.0) for step in agent_steps
        ),
        "total_steps": len(steps),
    }

    agent_extra: dict[str, Any] = {
        "parser": "openclaw-session-jsonl",
        "provider": provider,
        "session_schema_version": session_record.get("version"),
    }
    if thinking_level is not None:
        agent_extra["thinking_level"] = thinking_level

    return {
        "schema_version": "ATIF-v1.7",
        "session_id": session_record["id"],
        "agent": {
            "name": agent_name,
            "version": agent_version,
            "model_name": model_name(provider, default_model, True),
            "extra": {
                key: value for key, value in agent_extra.items() if value is not None
            },
        },
        "steps": steps,
        "final_metrics": final_metrics,
        "extra": {
            "source_format": "openclaw-session-jsonl",
            "source_session_filename": "openclaw_session.jsonl",
        },
    }


def validate(trajectory: dict[str, Any]) -> None:
    if trajectory.get("schema_version") != "ATIF-v1.7":
        raise ExportError("unexpected ATIF schema version")
    agent = trajectory.get("agent")
    if not isinstance(agent, dict) or not agent.get("name") or not agent.get("version"):
        raise ExportError("ATIF agent name and version are required")

    steps = trajectory.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ExportError("ATIF trajectory must contain steps")
    for expected_id, step in enumerate(steps, 1):
        if step.get("step_id") != expected_id:
            raise ExportError(f"non-sequential step id at position {expected_id}")
        if step.get("source") not in {"system", "user", "agent"}:
            raise ExportError(f"step {expected_id} has invalid source")
        if "message" not in step or not isinstance(step["message"], str):
            raise ExportError(f"step {expected_id} has invalid message")
        timestamp = step.get("timestamp")
        if timestamp is not None:
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (AttributeError, ValueError) as exc:
                raise ExportError(
                    f"step {expected_id} has invalid ISO 8601 timestamp"
                ) from exc

        calls = step.get("tool_calls", [])
        call_ids = {call["tool_call_id"] for call in calls}
        results = step.get("observation", {}).get("results", [])
        result_ids = {result.get("source_call_id") for result in results}
        if call_ids != result_ids:
            raise ExportError(
                f"step {expected_id} tool calls and observation results differ"
            )
        metrics = step.get("metrics")
        if isinstance(metrics, dict):
            if metrics.get("cached_tokens", 0) > metrics.get("prompt_tokens", 0):
                raise ExportError(f"step {expected_id} cached tokens exceed prompt tokens")

    expected_metrics = {
        "total_prompt_tokens": sum(
            step.get("metrics", {}).get("prompt_tokens", 0)
            for step in steps
            if step["source"] == "agent"
        ),
        "total_completion_tokens": sum(
            step.get("metrics", {}).get("completion_tokens", 0)
            for step in steps
            if step["source"] == "agent"
        ),
        "total_cached_tokens": sum(
            step.get("metrics", {}).get("cached_tokens", 0)
            for step in steps
            if step["source"] == "agent"
        ),
        "total_cost_usd": sum(
            step.get("metrics", {}).get("cost_usd", 0.0)
            for step in steps
            if step["source"] == "agent"
        ),
        "total_steps": len(steps),
    }
    if trajectory.get("final_metrics") != expected_metrics:
        raise ExportError("final metrics do not equal the per-step sums")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="OpenClaw session JSONL")
    parser.add_argument("target", type=Path, help="ATIF trajectory JSON")
    parser.add_argument("--agent-name", default="openclaw")
    parser.add_argument(
        "--agent-version", default=os.environ.get("OPENCLAW_VERSION", "unknown")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        trajectory = convert(
            load_records(args.source), args.agent_name, args.agent_version
        )
        validate(trajectory)
        args.target.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.target.with_name(args.target.name + ".tmp")
        temporary.write_text(
            json.dumps(trajectory, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(args.target)
    except (ExportError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "success",
                "source": str(args.source),
                "target": str(args.target),
                "session_id": trajectory["session_id"],
                "steps": len(trajectory["steps"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
