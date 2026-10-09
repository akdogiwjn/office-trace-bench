#!/usr/bin/env python3
"""Extract case-specific key operations from an ATIF-v1.7 trajectory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


class ExtractionError(ValueError):
    """Raised when a trajectory cannot be analyzed safely."""


OPERATION_METADATA: dict[str, dict[str, tuple[str, str]]] = {
    "xlsx": {
        "read_task_guidance": ("读取任务规范", "读取 XLSX Skill、输入说明和严格验收器。"),
        "inspect_input_workbook": ("检查源工作簿", "检查工作表、公式、图表及模板结构。"),
        "inspect_recalc_tooling": ("检查重算工具", "读取并理解 LibreOffice 公式重算脚本。"),
        "prepare_workbook_copy": ("准备工作簿副本", "复制输入模板作为后续增强的工作副本。"),
        "author_workbook_helper": ("编写工作簿增强 helper", "创建用于增强现有工作簿的 helper。"),
        "execute_workbook_helper": ("执行工作簿增强", "运行 helper 生成或更新增强工作簿。"),
        "recalculate_formulas": ("重算公式", "使用 LibreOffice 对最终工作簿执行公式重算。"),
        "write_recalc_report": ("写入重算报告", "显式写入或保存公式重算结果报告。"),
        "inspect_generated_workbook": ("检查增强结果", "检查公式、缓存值、布局和重算报告。"),
        "repair_workbook_helper": ("修复增强 helper", "根据检查结果修改 helper 并重新生成。"),
        "publish_csv_outputs": ("发布 CSV 输出", "把稳定参考 CSV 发布为最终交付文件。"),
        "run_business_verifier": ("运行 XLSX 严格验收", "运行独立业务 verifier 并写入验收报告。"),
        "write_execution_summary": ("写入 XLSX 执行摘要", "记录功能、尝试次数、重算次数和验收状态。"),
        "validate_deliverables": ("核对 XLSX 交付物", "检查最终文件清单和业务验收状态。"),
    },
    "pdf": {
        "read_task_guidance": ("读取任务规范", "读取 PDF Skill、表单指南、数据和严格验收器。"),
        "inspect_pdf_tooling": ("检查 PDF 工具", "读取表单检查、字段提取、填表和渲染脚本。"),
        "prepare_output_layout": ("准备批处理目录", "创建字段值、填写结果和渲染输出目录。"),
        "check_fillable_fields": ("检查可填写字段", "确认源 PDF 的 AcroForm 可填写字段。"),
        "extract_form_fields": ("提取表单字段", "提取字段 ID、页码、类型、坐标和选项。"),
        "render_template": ("渲染 PDF 模板", "把空白模板渲染为图片，并在失败后重试。"),
        "inspect_rendered_template": ("检查模板渲染结果", "检查模板图片目录和生成结果。"),
        "inspect_form_fields": ("检查字段结构", "读取字段清单并确认后续映射依据。"),
        "author_field_mapping_helper": ("编写字段映射 helper", "创建申请人数据到 PDF 字段的映射程序。"),
        "generate_field_values": ("生成字段值", "为每个申请人生成独立字段值 JSON。"),
        "validate_field_mapping": ("校验字段映射", "确认生成的字段 ID 均存在于表单字段清单。"),
        "author_batch_processing_helper": ("编写批处理 helper", "创建批量填表和渲染程序。"),
        "fill_and_render_batch": ("批量填表与渲染", "生成填写后的 PDF 并渲染各页用于检查。"),
        "write_batch_summary": ("写入 PDF 批处理摘要", "记录调用次数和批量产物数量。"),
        "run_business_verifier": ("运行 PDF 严格验收", "运行独立业务 verifier 并写入验收报告。"),
        "validate_deliverables": ("核对 PDF 交付物", "检查最终文件清单、数量和业务验收状态。"),
    },
}


MANUAL_REFERENCE: dict[str, list[str]] = {
    "xlsx": [
        "read_task_guidance",
        "inspect_input_workbook",
        "inspect_recalc_tooling",
        "author_workbook_helper",
        "execute_workbook_helper",
        "recalculate_formulas",
        "inspect_generated_workbook",
        "repair_workbook_helper",
        "publish_csv_outputs",
        "run_business_verifier",
        "write_execution_summary",
        "validate_deliverables",
    ],
    "pdf": [
        "read_task_guidance",
        "inspect_pdf_tooling",
        "prepare_output_layout",
        "check_fillable_fields",
        "extract_form_fields",
        "render_template",
        "inspect_rendered_template",
        "inspect_form_fields",
        "author_field_mapping_helper",
        "generate_field_values",
        "validate_field_mapping",
        "author_batch_processing_helper",
        "fill_and_render_batch",
        "write_batch_summary",
        "run_business_verifier",
        "validate_deliverables",
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"{path}: invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ExtractionError(f"{path}: trajectory must be a JSON object")
    return value


def argument_text(arguments: Any) -> str:
    if not isinstance(arguments, dict):
        return ""
    return "\n".join(str(value) for value in arguments.values())


def classify_xlsx(function_name: str, text: str, state: dict[str, Any]) -> str | None:
    lowered = text.lower()
    if function_name == "process":
        return None

    if function_name in {"write", "edit"}:
        if "xlsx_enhancement_summary.json" in lowered:
            return "write_execution_summary"
        if "enhance_workbook.py" in lowered:
            if state.get("workbook_helper_seen"):
                return "repair_workbook_helper"
            state["workbook_helper_seen"] = True
            return "author_workbook_helper"

    if function_name == "read":
        if "/xlsx/scripts/recalc.py" in lowered:
            return "inspect_recalc_tooling"
        return "read_task_guidance"

    if function_name != "exec":
        return None

    # An agent may use an inline Python snippet instead of the write tool.  Match
    # the artifact being written, but do not confuse later `cat` inspection with
    # artifact creation.
    if "xlsx_enhancement_summary.json" in lowered and (
        "write_text" in lowered or re.search(r"json\.dump\s*\(", lowered)
    ):
        return "write_execution_summary"
    if "formula_recalc.json" in lowered and "recalc.py" not in lowered and (
        "write_text" in lowered or re.search(r"json\.dump\s*\(", lowered)
    ):
        return "write_recalc_report"
    if "verify_xlsx_enhanced.py" in lowered and re.search(
        r"python3\s+(?:\S+/)?verify_xlsx_enhanced\.py", lowered
    ):
        return "run_business_verifier"
    if "verify_xlsx_enhanced.py" in lowered and re.search(r"\bcat\b", lowered):
        return "read_task_guidance"
    if "recalc.py" in lowered and "monthly_operations_report.xlsx" in lowered:
        return "recalculate_formulas"
    if re.search(r"python3\s+enhance_workbook\.py", lowered):
        return "execute_workbook_helper"
    if "prepared_monthly_operations_summary.csv" in lowered and re.search(r"\bcp\b", lowered):
        return "publish_csv_outputs"
    if "monthly_operations_template.xlsx" in lowered and re.search(
        r"\bcp\b", lowered
    ):
        return "prepare_workbook_copy"
    if (
        "business_verification.json" in lowered
        and ("ls -la" in lowered or "final output" in lowered or "summary json" in lowered)
    ) or (
        re.search(r"\bls\s+-la\s+\S*/?output/?(?:\s|$)", lowered)
        and "output dir not found" not in lowered
    ):
        return "validate_deliverables"
    if "monthly_operations_template.xlsx" in lowered and "load_workbook" in lowered:
        return "inspect_input_workbook"
    if (
        "monthly_operations_report.xlsx" in lowered
        or "formula_recalc.json" in lowered
    ) and ("load_workbook" in lowered or re.search(r"\bcat\b", lowered)):
        return "inspect_generated_workbook"
    if re.search(r"\bcat\b", lowered) and ("/input/" in lowered or " input/" in lowered):
        return "read_task_guidance"
    if re.search(r"(^|[;&|]\s*)ls\s", lowered):
        return "read_task_guidance"
    return None


def classify_pdf(function_name: str, text: str, state: dict[str, Any]) -> str | None:
    del state
    lowered = text.lower()
    if function_name == "process":
        return None

    if function_name in {"write", "edit"}:
        if "batch_summary.json" in lowered:
            return "write_batch_summary"
        if "generate_field_values.py" in lowered or "generate_and_run_batch.py" in lowered:
            return "author_field_mapping_helper"
        if "batch_fill_render.py" in lowered or "run_batch_fill_render.py" in lowered:
            return "author_batch_processing_helper"

    if function_name == "read":
        if "/output/form_field_info.json" in lowered:
            return "inspect_form_fields"
        if "/pdf/scripts/" in lowered:
            return "inspect_pdf_tooling"
        return "read_task_guidance"

    if function_name != "exec":
        return None
    if "verify_pdf_batch.py" in lowered and re.search(
        r"python3\s+(?:\S+/)?verify_pdf_batch\.py", lowered
    ):
        return "run_business_verifier"
    if re.search(r"python3\s+(?:batch_fill_render|run_batch_fill_render)\.py", lowered):
        return "fill_and_render_batch"
    if re.search(r"python3\s+(?:generate_field_values|generate_and_run_batch)\.py", lowered):
        return "generate_field_values"
    if "verify all field ids" in lowered or (
        "valid_ids" in lowered and "field_info" in lowered
    ):
        return "validate_field_mapping"
    if "check_fillable_fields.py" in lowered:
        return "check_fillable_fields"
    if "check_fillable_fields.log" in lowered and re.search(r"\bcat\b", lowered):
        return "check_fillable_fields"
    if "extract_form_field_info.py" in lowered:
        return "extract_form_fields"
    if "convert_pdf_to_images.py" in lowered:
        return "render_template"
    if re.search(r"\bmkdir\b", lowered):
        return "prepare_output_layout"
    if re.search(r"\bfind\b", lowered) and (
        "output inventory" in lowered
        or "business_verification.json" in lowered
        or "filled pdf count" in lowered
        or "field values count" in lowered
    ):
        return "validate_deliverables"
    if "output/rendered" in lowered and re.search(r"\bls\b", lowered):
        return "inspect_rendered_template"
    if re.search(r"(^|[;&|]\s*)ls\s", lowered):
        return "read_task_guidance"
    return None


CLASSIFIERS = {"xlsx": classify_xlsx, "pdf": classify_pdf}


def summarize_value(key: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    encoded = value.encode("utf-8")
    limit = 4000 if key in {"command", "path"} else 800
    if len(encoded) <= limit:
        return value
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "excerpt": value[:limit],
        "truncated": True,
    }


def summarize_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        return {}
    return {key: summarize_value(key, value) for key, value in arguments.items()}


def extract_paths(arguments: Any) -> list[str]:
    if not isinstance(arguments, dict):
        return []
    text = argument_text(arguments)
    paths = set(
        re.findall(
            r"/(?:[A-Za-z0-9._@+~-]+/)*[A-Za-z0-9._@+~-]+", text
        )
    )
    for key in ("path", "file"):
        value = arguments.get(key)
        if isinstance(value, str) and value:
            paths.add(value)
    return sorted(paths)


def result_for_call(step: dict[str, Any], call_id: str) -> dict[str, Any] | None:
    observation = step.get("observation")
    if not isinstance(observation, dict):
        return None
    results = observation.get("results")
    if not isinstance(results, list):
        return None
    return next(
        (
            result
            for result in results
            if isinstance(result, dict) and result.get("source_call_id") == call_id
        ),
        None,
    )


def summarize_result(result: dict[str, Any] | None) -> dict[str, Any]:
    if result is None:
        return {"status": "unknown"}
    extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
    details = extra.get("details") if isinstance(extra.get("details"), dict) else {}
    exit_code = details.get("exitCode")
    is_error = bool(extra.get("is_error", False))
    status = "error" if is_error or (isinstance(exit_code, int) and exit_code != 0) else "success"
    content = result.get("content")
    content_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    summary: dict[str, Any] = {
        "status": status,
        "is_error": is_error,
        "content_excerpt": content_text[:500],
    }
    if isinstance(exit_code, int):
        summary["exit_code"] = exit_code
    if isinstance(details.get("durationMs"), (int, float)):
        summary["duration_ms"] = details["durationMs"]
    return summary


def extract_events(
    trajectory: dict[str, Any], case_kind: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    steps = trajectory.get("steps")
    if not isinstance(steps, list):
        raise ExtractionError("trajectory.steps must be an array")
    classifier = CLASSIFIERS[case_kind]
    state: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    counters = {"total_tool_calls": 0, "ignored_wait_calls": 0, "unclassified_calls": 0}

    for step in steps:
        if not isinstance(step, dict) or step.get("source") != "agent":
            continue
        calls = step.get("tool_calls", [])
        if not isinstance(calls, list):
            continue
        for call_index, call in enumerate(calls):
            if not isinstance(call, dict):
                continue
            counters["total_tool_calls"] += 1
            function_name = str(call.get("function_name") or "")
            arguments = call.get("arguments")
            operation = classifier(function_name, argument_text(arguments), state)
            if operation is None:
                if function_name == "process":
                    counters["ignored_wait_calls"] += 1
                else:
                    counters["unclassified_calls"] += 1
                continue
            label, description = OPERATION_METADATA[case_kind][operation]
            call_id = str(call.get("tool_call_id") or "")
            events.append(
                {
                    "event_id": len(events) + 1,
                    "operation": operation,
                    "label": label,
                    "description": description,
                    "source": {
                        "step_id": step.get("step_id"),
                        "tool_call_index": call_index,
                        "tool_call_id": call_id,
                        "timestamp": step.get("timestamp"),
                    },
                    "tool": {
                        "function_name": function_name,
                        "arguments": summarize_arguments(arguments),
                        "target_paths": extract_paths(arguments),
                    },
                    "result": summarize_result(result_for_call(step, call_id)),
                }
            )
    if not events:
        raise ExtractionError("no case-specific key operations were recognized")
    return events, counters


def group_operations(
    events: list[dict[str, Any]], case_kind: str
) -> list[dict[str, Any]]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for event in events:
        grouped.setdefault(event["operation"], []).append(event)

    operations: list[dict[str, Any]] = []
    for operation, occurrences in grouped.items():
        label, description = OPERATION_METADATA[case_kind][operation]
        statuses = [item["result"]["status"] for item in occurrences]
        operations.append(
            {
                "operation_id": len(operations) + 1,
                "operation": operation,
                "label": label,
                "description": description,
                "occurrence_count": len(occurrences),
                "successful_occurrences": statuses.count("success"),
                "failed_occurrences": statuses.count("error"),
                "first_step_id": occurrences[0]["source"]["step_id"],
                "last_step_id": occurrences[-1]["source"]["step_id"],
                "tools": sorted(
                    {item["tool"]["function_name"] for item in occurrences}
                ),
                "target_paths": sorted(
                    {
                        path
                        for item in occurrences
                        for path in item["tool"]["target_paths"]
                    }
                ),
                "source_refs": [item["source"] for item in occurrences],
            }
        )
    return operations


def condensed_sequence(events: list[dict[str, Any]]) -> list[str]:
    sequence: list[str] = []
    for event in events:
        operation = event["operation"]
        if not sequence or sequence[-1] != operation:
            sequence.append(operation)
    return sequence


def compare_reference(
    operations: list[dict[str, Any]], case_kind: str
) -> dict[str, Any]:
    expected = MANUAL_REFERENCE[case_kind]
    found = [operation["operation"] for operation in operations]
    missing = [operation for operation in expected if operation not in found]
    unexpected = [operation for operation in found if operation not in expected]
    coverage = (len(expected) - len(missing)) / len(expected)
    return {
        "reference_method": "manual review of the current case trajectory",
        "reference_operations": expected,
        "extracted_operations": found,
        "missing_operations": missing,
        "unexpected_operations": unexpected,
        "coverage": round(coverage, 4),
        "status": "matched" if not missing and not unexpected else "review",
        "note": "This comparison checks extraction quality; it is not a fixed workflow requirement for future agent runs.",
    }


def validate_output(output: dict[str, Any], trajectory: dict[str, Any]) -> None:
    if output.get("schema_version") != "key-operations-v1":
        raise ExtractionError("unexpected key-operation schema version")
    if output.get("session_id") != trajectory.get("session_id"):
        raise ExtractionError("session id differs from source trajectory")
    call_ids = {
        call.get("tool_call_id")
        for step in trajectory.get("steps", [])
        if isinstance(step, dict)
        for call in step.get("tool_calls", [])
        if isinstance(call, dict)
    }
    event_ids: set[int] = set()
    for event in output.get("operation_events", []):
        event_id = event.get("event_id")
        if event_id in event_ids:
            raise ExtractionError(f"duplicate key operation event id {event_id}")
        event_ids.add(event_id)
        if event.get("source", {}).get("tool_call_id") not in call_ids:
            raise ExtractionError(
                f"key operation event {event_id} references an unknown tool call"
            )
    if event_ids != set(range(1, len(event_ids) + 1)):
        raise ExtractionError("key operation event ids are not sequential")


def build_output(
    source: Path, trajectory: dict[str, Any], case_id: str, case_kind: str
) -> dict[str, Any]:
    if trajectory.get("schema_version") != "ATIF-v1.7":
        raise ExtractionError("source must be an ATIF-v1.7 trajectory")
    events, counters = extract_events(trajectory, case_kind)
    operations = group_operations(events, case_kind)
    source_bytes = source.read_bytes()
    output = {
        "schema_version": "key-operations-v1",
        "case_id": case_id,
        "case_kind": case_kind,
        "session_id": trajectory.get("session_id"),
        "source_trajectory": {
            "filename": source.name,
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "bytes": len(source_bytes),
            "schema_version": trajectory.get("schema_version"),
        },
        "extraction_method": {
            "name": "case-specific semantic rule extraction",
            "version": 2,
            "description": "Classifies ATIF tool calls by XLSX/PDF domain semantics, ignores process polling, preserves retries and groups repeated operations.",
        },
        "summary": {
            "trajectory_steps": len(trajectory.get("steps", [])),
            **counters,
            "key_operation_events": len(events),
            "key_operation_types": len(operations),
        },
        "key_operations": operations,
        "workflow": {
            "event_sequence": [event["operation"] for event in events],
            "condensed_sequence": condensed_sequence(events),
        },
        "operation_events": events,
        "manual_reference_comparison": compare_reference(operations, case_kind),
    }
    validate_output(output, trajectory)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="ATIF trajectory JSON")
    parser.add_argument("target", type=Path, help="key operation output JSON")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--case-kind", choices=sorted(CLASSIFIERS), required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        trajectory = load_json(args.source)
        output = build_output(
            args.source, trajectory, args.case_id, args.case_kind
        )
        args.target.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.target.with_name(args.target.name + ".tmp")
        temporary.write_text(
            json.dumps(output, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(args.target)
    except (ExtractionError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": output["manual_reference_comparison"]["status"],
                "case_id": output["case_id"],
                "session_id": output["session_id"],
                "target": str(args.target),
                "key_operation_types": output["summary"]["key_operation_types"],
                "key_operation_events": output["summary"]["key_operation_events"],
                "reference_coverage": output["manual_reference_comparison"]["coverage"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
