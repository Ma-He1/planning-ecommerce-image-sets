#!/usr/bin/env python3
"""Validate an auditable planning-ecommerce-image-sets run directory."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path, PureWindowsPath

try:
    from PIL import Image, ImageChops, UnidentifiedImageError
except ImportError:  # pragma: no cover - exercised only in runtimes without Pillow
    Image = None
    ImageChops = None
    UnidentifiedImageError = OSError


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PASS_VERDICTS = {"pass", "passed"}
TIMING_TOLERANCE_MS = 1
RATIO_TOLERANCE = 1e-6
AMAZON_MAIN_MIN_LONGEST_SIDE_PX = 1000
AMAZON_MAIN_CORNER_SAMPLE_RATIO = 0.1
AMAZON_MAIN_MIN_CORNER_STRICT_WHITE_RATIO = 0.99
AMAZON_MAIN_MIN_PRODUCT_FILL_HEIGHT_RATIO = 0.85
AMAZON_MAIN_FOREGROUND_THRESHOLD = 245
REQUIRED_QA_CHECKS = {"identity", "facts", "platform", "text", "composition"}
ALLOWED_QA_CHECK_RESULTS = {"pass", "not_applicable"}
ALLOWED_ATTEMPT_STATUSES = {"success", "failed"}
REQUIRED_ALL = {
    "brief.json": "file",
    "inputs": "directory",
    "content_plan.md": "file",
    "image_set_plan.json": "file",
    "prompts.md": "file",
    "run_manifest.json": "file",
}
REQUIRED_GENERATION = {
    "qa_report.json": "file",
    "outputs": "directory",
    "contact_sheet.jpg": "file",
}


def add_type_error(errors, path, expected):
    errors.append(f"{path} must be {expected}")


def as_dict(value, path, errors):
    if not isinstance(value, dict):
        add_type_error(errors, path, "an object")
        return {}
    return value


def as_list(value, path, errors):
    if not isinstance(value, list):
        add_type_error(errors, path, "an array")
        return []
    return value


def non_negative_int(value, path, errors):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        errors.append(f"{path} must be a non-negative integer")
        return None
    return value


def read_json(path, label, errors):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        errors.append(f"missing required file: {label}")
        return {}
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read {label}: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(
            f"{label} contains invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        )
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must contain a JSON object")
        return {}
    return value


def safe_path(run_root, value, label, errors, expected=None):
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty relative path")
        return None
    value = value.strip()
    windows_path = PureWindowsPath(value)
    if (
        Path(value).is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
    ):
        errors.append(f"{label} must be relative to the run root")
        return None

    root = run_root.resolve()
    candidate = (root / Path(value)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        errors.append(f"{label} escapes the run root: {value}")
        return None

    if not candidate.exists():
        errors.append(f"{label} does not exist: {value}")
        return candidate
    if expected == "file" and not candidate.is_file():
        errors.append(f"{label} must point to a regular file: {value}")
    elif expected == "directory" and not candidate.is_dir():
        errors.append(f"{label} must point to a directory: {value}")
    elif expected is None and not (candidate.is_file() or candidate.is_dir()):
        errors.append(f"{label} must point to a regular file or directory: {value}")
    return candidate


def require_under(path, parent, label, errors):
    if path is None:
        return
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        errors.append(f"{label} must stay inside {parent.name}/")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite_number(value, label, errors):
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
    ):
        errors.append(f"{label} must be a finite number")
        return None
    return float(value)


def inspect_amazon_main_white(path, label, errors):
    if Image is None or ImageChops is None:
        errors.append(
            f"{label} requires Pillow to verify Amazon main_white platform evidence"
        )
        return None
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        errors.append(f"{label} cannot be inspected as an image with Pillow: {exc}")
        return None

    width, height = image.size
    if width < 1 or height < 1:
        errors.append(f"{label} must have positive pixel dimensions")
        return None

    exact_white_table = [255 if value == 255 else 0 for value in range(256)]
    below_foreground_table = [
        255 if value < AMAZON_MAIN_FOREGROUND_THRESHOLD else 0
        for value in range(256)
    ]
    red, green, blue = image.split()
    strict_white = ImageChops.multiply(
        ImageChops.multiply(
            red.point(exact_white_table),
            green.point(exact_white_table),
        ),
        blue.point(exact_white_table),
    )
    foreground = ImageChops.lighter(
        ImageChops.lighter(
            red.point(below_foreground_table),
            green.point(below_foreground_table),
        ),
        blue.point(below_foreground_table),
    )

    total_pixels = width * height
    overall_strict_white_ratio = (
        strict_white.histogram()[255] / total_pixels
    )

    corner_width = max(
        1, math.ceil(width * AMAZON_MAIN_CORNER_SAMPLE_RATIO)
    )
    corner_height = max(
        1, math.ceil(height * AMAZON_MAIN_CORNER_SAMPLE_RATIO)
    )
    corner_boxes = (
        (0, 0, corner_width, corner_height),
        (width - corner_width, 0, width, corner_height),
        (0, height - corner_height, corner_width, height),
        (
            width - corner_width,
            height - corner_height,
            width,
            height,
        ),
    )
    corner_ratios = []
    corner_pixels = corner_width * corner_height
    for box in corner_boxes:
        corner_ratios.append(
            strict_white.crop(box).histogram()[255] / corner_pixels
        )

    foreground_bbox = foreground.getbbox()
    product_fill_height_ratio = (
        0.0
        if foreground_bbox is None
        else (foreground_bbox[3] - foreground_bbox[1]) / height
    )
    return {
        "longest_side_px": max(width, height),
        "corner_sample_ratio": AMAZON_MAIN_CORNER_SAMPLE_RATIO,
        "corner_strict_white_ratio": min(corner_ratios),
        "overall_strict_white_ratio": overall_strict_white_ratio,
        "product_fill_height_ratio": product_fill_height_ratio,
    }


def validate_amazon_main_white_evidence(path, qa_shot, label, errors):
    actual = inspect_amazon_main_white(path, label, errors)
    if actual is None:
        return

    evidence_label = f"{label}.platform_evidence"
    evidence = as_dict(qa_shot.get("platform_evidence"), evidence_label, errors)

    longest_side = evidence.get("longest_side_px")
    if (
        not isinstance(longest_side, int)
        or isinstance(longest_side, bool)
        or longest_side < 0
    ):
        errors.append(f"{evidence_label}.longest_side_px must be a non-negative integer")
        longest_side = None

    ratio_fields = (
        "corner_sample_ratio",
        "corner_strict_white_ratio",
        "overall_strict_white_ratio",
        "product_fill_height_ratio",
    )
    recorded_ratios = {
        field: finite_number(
            evidence.get(field),
            f"{evidence_label}.{field}",
            errors,
        )
        for field in ratio_fields
    }

    actual_longest_side = actual["longest_side_px"]
    if actual_longest_side < AMAZON_MAIN_MIN_LONGEST_SIDE_PX:
        errors.append(
            f"{label} Amazon main_white longest side must be at least "
            f"{AMAZON_MAIN_MIN_LONGEST_SIDE_PX} px; got {actual_longest_side}"
        )
    if longest_side is not None and longest_side != actual_longest_side:
        errors.append(
            f"{evidence_label}.longest_side_px does not match recomputed "
            f"value {actual_longest_side}"
        )

    for field in ratio_fields:
        recorded = recorded_ratios[field]
        recomputed = actual[field]
        if recorded is not None and abs(recorded - recomputed) > RATIO_TOLERANCE:
            errors.append(
                f"{evidence_label}.{field} does not match recomputed "
                f"value {recomputed:.12f}"
            )

    recorded_sample = recorded_ratios["corner_sample_ratio"]
    if (
        recorded_sample is not None
        and abs(recorded_sample - AMAZON_MAIN_CORNER_SAMPLE_RATIO)
        > RATIO_TOLERANCE
    ):
        errors.append(
            f"{evidence_label}.corner_sample_ratio must be "
            f"{AMAZON_MAIN_CORNER_SAMPLE_RATIO}"
        )

    corner_ratio = actual["corner_strict_white_ratio"]
    if corner_ratio < AMAZON_MAIN_MIN_CORNER_STRICT_WHITE_RATIO:
        errors.append(
            f"{label} Amazon main_white corner strict RGB255 ratio "
            f"{corner_ratio:.6f} must be at least "
            f"{AMAZON_MAIN_MIN_CORNER_STRICT_WHITE_RATIO}"
        )

    fill_ratio = actual["product_fill_height_ratio"]
    if not AMAZON_MAIN_MIN_PRODUCT_FILL_HEIGHT_RATIO <= fill_ratio <= 1.0:
        errors.append(
            f"{label} Amazon main_white product_fill_height_ratio "
            f"{fill_ratio:.6f} must be between "
            f"{AMAZON_MAIN_MIN_PRODUCT_FILL_HEIGHT_RATIO} and 1.0"
        )


def verify_file_hash(run_root, record, label, errors, expected_parent=None):
    record = as_dict(record, label, errors)
    path = safe_path(run_root, record.get("path"), f"{label}.path", errors, "file")
    if expected_parent is not None:
        require_under(path, expected_parent, f"{label}.path", errors)

    digest = record.get("sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        errors.append(
            f"{label}.sha256 must be lowercase 64-character hexadecimal SHA256"
        )
    elif path is not None and path.is_file():
        actual = sha256(path)
        if actual != digest:
            errors.append(
                f"{label}.sha256 SHA256 mismatch: expected {digest}, got {actual}"
            )
    return path


def parse_timestamp(value, label, errors):
    if not isinstance(value, str) or "T" not in value:
        errors.append(f"{label} must be an ISO 8601 datetime with timezone")
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} must be an ISO 8601 datetime with timezone")
        return None
    if timestamp.tzinfo is None:
        errors.append(f"{label} must include an ISO 8601 timezone")
        return None
    return timestamp


def elapsed_between(started, finished):
    return round((finished - started).total_seconds() * 1000)


def validate_duration(started, finished, elapsed, label, errors):
    if started is None or finished is None or elapsed is None:
        return
    if finished < started:
        errors.append(f"{label} finished_at precedes started_at")
        return
    measured = elapsed_between(started, finished)
    if abs(measured - elapsed) > TIMING_TOLERANCE_MS:
        errors.append(
            f"{label} elapsed mismatch: timestamps give {measured} ms, "
            f"record says {elapsed} ms"
        )


def audit_manifest_paths(run_root, value, label, errors):
    """Apply the run-root boundary to every path-shaped manifest field."""
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{label}.{key}"
            if key == "path" or key.endswith("_path"):
                if item not in (None, ""):
                    safe_path(run_root, item, child, errors)
            else:
                audit_manifest_paths(run_root, item, child, errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            audit_manifest_paths(run_root, item, f"{label}[{index}]", errors)


def shot_ids(records, label, errors):
    result = []
    for index, raw_record in enumerate(records):
        record = as_dict(raw_record, f"{label}[{index}]", errors)
        image_id = record.get("image_id")
        if not isinstance(image_id, str) or not image_id.strip():
            errors.append(f"{label}[{index}].image_id must be a non-empty string")
        else:
            result.append(image_id)
    if len(result) != len(set(result)):
        errors.append(f"{label} contains duplicate image_id values")
    return result


def validate_attempts(
    shot,
    label,
    mode,
    run_root,
    inputs_dir,
    manifest_input_hashes,
    run_started,
    run_finished,
    errors,
):
    attempt_count = non_negative_int(
        shot.get("attempt_count"), f"{label}.attempt_count", errors
    )
    elapsed = non_negative_int(shot.get("elapsed_ms"), f"{label}.elapsed_ms", errors)
    if attempt_count is not None:
        if attempt_count > 3:
            errors.append(f"{label}.attempt_count exceeds the maximum of 3 attempts")
        if mode == "generation" and attempt_count < 1:
            errors.append(f"{label} requires at least one attempt in generation mode")
        if mode == "planning_only" and attempt_count != 0:
            errors.append(f"plan-only {label}.attempt_count must be 0")
    if mode == "planning_only" and elapsed not in (None, 0):
        errors.append(f"plan-only {label}.elapsed_ms must be 0")

    if "attempts" not in shot:
        if mode == "generation":
            errors.append(f"{label}.attempts is required in generation mode")
        return attempt_count, elapsed, []

    attempts = as_list(shot.get("attempts"), f"{label}.attempts", errors)
    if mode == "generation" and not attempts:
        errors.append(f"{label}.attempts must not be empty in generation mode")
    if attempt_count is not None and len(attempts) != attempt_count:
        errors.append(
            f"{label}.attempt_count={attempt_count} does not match "
            f"attempt records={len(attempts)}"
        )
    attempt_elapsed = 0
    previous_finished = None
    statuses = []
    for index, raw_attempt in enumerate(attempts):
        attempt_label = f"{label}.attempts[{index}]"
        attempt = as_dict(raw_attempt, attempt_label, errors)
        if attempt.get("attempt_index") != index + 1:
            errors.append(
                f"{attempt_label}.attempt_index must be contiguous and start at 1"
            )
        started = parse_timestamp(
            attempt.get("started_at"), f"{attempt_label}.started_at", errors
        )
        finished = parse_timestamp(
            attempt.get("finished_at"), f"{attempt_label}.finished_at", errors
        )
        item_elapsed = non_negative_int(
            attempt.get("elapsed_ms"), f"{attempt_label}.elapsed_ms", errors
        )
        validate_duration(
            started, finished, item_elapsed, f"{attempt_label} timing", errors
        )
        if (
            previous_finished is not None
            and started is not None
            and started < previous_finished
        ):
            errors.append(f"{attempt_label}.started_at overlaps the previous attempt")
        if (
            run_started is not None
            and started is not None
            and started < run_started
        ):
            errors.append(f"{attempt_label}.started_at precedes the run")
        if (
            run_finished is not None
            and finished is not None
            and finished > run_finished
        ):
            errors.append(f"{attempt_label}.finished_at exceeds the run")
        if finished is not None:
            previous_finished = finished
        if item_elapsed is not None:
            attempt_elapsed += item_elapsed

        tool_route = attempt.get("tool_route")
        if mode == "generation" and tool_route != "imagegen":
            errors.append(f"{attempt_label}.tool_route must be imagegen")

        prompt = attempt.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"{attempt_label}.prompt must be a non-empty exact prompt")
        prompt_digest = attempt.get("prompt_sha256")
        if not isinstance(prompt_digest, str) or not SHA256_RE.fullmatch(prompt_digest):
            errors.append(
                f"{attempt_label}.prompt_sha256 must be lowercase 64-character "
                "hexadecimal prompt SHA256"
            )
        elif isinstance(prompt, str):
            actual_prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            if prompt_digest != actual_prompt_digest:
                errors.append(
                    f"{attempt_label} prompt SHA256 mismatch: expected "
                    f"{prompt_digest}, got {actual_prompt_digest}"
                )

        references = as_list(
            attempt.get("reference_inputs"),
            f"{attempt_label}.reference_inputs",
            errors,
        )
        if mode == "generation" and not references:
            errors.append(f"{attempt_label}.reference_inputs must not be empty")
        for reference_index, raw_reference in enumerate(references):
            reference_label = (
                f"{attempt_label}.reference_inputs[{reference_index}]"
            )
            reference = as_dict(raw_reference, reference_label, errors)
            reference_path = safe_path(
                run_root,
                reference.get("path"),
                f"{reference_label}.path",
                errors,
                "file",
            )
            require_under(
                reference_path,
                inputs_dir,
                f"{reference_label}.path",
                errors,
            )
            reference_digest = reference.get("sha256")
            if (
                not isinstance(reference_digest, str)
                or not SHA256_RE.fullmatch(reference_digest)
            ):
                errors.append(
                    f"{reference_label}.sha256 must be lowercase "
                    "64-character hexadecimal attempt reference SHA256"
                )
            elif reference_path is not None:
                manifest_digest = manifest_input_hashes.get(reference_path.resolve())
                if manifest_digest != reference_digest:
                    errors.append(
                        f"{reference_label} attempt reference path/hash must "
                        "match manifest inputs"
                    )

        status = attempt.get("status")
        if status not in ALLOWED_ATTEMPT_STATUSES:
            errors.append(
                f"{attempt_label}.status must be success or failed"
            )
        else:
            statuses.append(status)

        raw_path_value = attempt.get("raw_result_path")
        raw_digest = attempt.get("raw_result_sha256")
        if status == "success" or raw_path_value not in (None, ""):
            raw_path = safe_path(
                run_root,
                raw_path_value,
                f"{attempt_label}.raw_result_path",
                errors,
                "file",
            )
            require_under(
                raw_path,
                run_root / "outputs",
                f"{attempt_label}.raw_result_path",
                errors,
            )
            if not isinstance(raw_digest, str) or not SHA256_RE.fullmatch(raw_digest):
                errors.append(
                    f"{attempt_label}.raw_result_sha256 must be lowercase "
                    "64-character hexadecimal SHA256"
                )
            elif raw_path is not None and raw_path.is_file():
                actual_raw_digest = sha256(raw_path)
                if actual_raw_digest != raw_digest:
                    errors.append(
                        f"{attempt_label}.raw_result_sha256 SHA256 mismatch: "
                        f"expected {raw_digest}, got {actual_raw_digest}"
                    )
        elif raw_digest not in (None, ""):
            errors.append(
                f"{attempt_label}.raw_result_path is required when "
                "raw_result_sha256 is present"
            )
    if elapsed is not None and attempt_elapsed != elapsed:
        errors.append(
            f"{label}.elapsed_ms={elapsed} does not match attempt elapsed="
            f"{attempt_elapsed}"
        )
    return attempt_count, elapsed, statuses


def validate(run_root):
    errors = []
    if not run_root.exists():
        return [f"run root does not exist: {run_root}"]
    if not run_root.is_dir():
        return [f"run root must be a directory: {run_root}"]
    run_root = run_root.resolve()

    for relative, expected in REQUIRED_ALL.items():
        path = run_root / relative
        if expected == "file" and not path.is_file():
            errors.append(f"missing required file: {relative}")
        elif expected == "directory" and not path.is_dir():
            errors.append(f"missing required directory: {relative}/")

    brief = read_json(run_root / "brief.json", "brief.json", errors)
    plan = read_json(run_root / "image_set_plan.json", "image_set_plan.json", errors)
    manifest = read_json(run_root / "run_manifest.json", "run_manifest.json", errors)

    mode = manifest.get("mode")
    if mode == "plan_only":
        errors.append("plan-only mode name is invalid; use planning_only")
        effective_mode = "planning_only"
    elif mode in {"planning_only", "generation"}:
        effective_mode = mode
    else:
        errors.append("run_manifest.json mode must be planning_only or generation")
        effective_mode = mode

    brief_mode = brief.get("mode")
    if brief_mode is not None and brief_mode != mode:
        errors.append("brief.json mode must match run_manifest.json mode")

    if effective_mode == "generation":
        for relative, expected in REQUIRED_GENERATION.items():
            path = run_root / relative
            if expected == "file" and not path.is_file():
                errors.append(f"missing required generation file: {relative}")
            elif expected == "directory" and not path.is_dir():
                errors.append(f"missing required generation directory: {relative}/")
        qa = read_json(run_root / "qa_report.json", "qa_report.json", errors)
    else:
        qa = {}

    if manifest.get("schema_version") != "1.0":
        errors.append("run_manifest.json schema_version must be '1.0'")
    if not isinstance(manifest.get("run_id"), str) or not manifest["run_id"].strip():
        errors.append("run_manifest.json run_id must be a non-empty string")

    tool_route = manifest.get("tool_route")
    if effective_mode == "generation" and tool_route != "imagegen":
        errors.append("generation tool_route must be Codex built-in imagegen")
    elif effective_mode == "planning_only" and tool_route != "none":
        errors.append("plan-only tool_route must be none")

    run_started = parse_timestamp(
        manifest.get("started_at"), "run_manifest.json started_at", errors
    )
    run_finished = parse_timestamp(
        manifest.get("finished_at"), "run_manifest.json finished_at", errors
    )
    total_elapsed = non_negative_int(
        manifest.get("total_elapsed_ms"),
        "run_manifest.json total_elapsed_ms",
        errors,
    )
    validate_duration(
        run_started,
        run_finished,
        total_elapsed,
        "run_manifest.json timing",
        errors,
    )
    audit_manifest_paths(run_root, manifest, "run_manifest.json", errors)

    inputs_dir = run_root / "inputs"
    manifest_inputs = as_list(
        manifest.get("inputs"), "run_manifest.json inputs", errors
    )
    input_paths = []
    manifest_input_hashes = {}
    for index, record in enumerate(manifest_inputs):
        path = verify_file_hash(
            run_root,
            record,
            f"run_manifest.json inputs[{index}]",
            errors,
            inputs_dir,
        )
        if path is not None:
            input_paths.append(path.resolve())
            if isinstance(record, dict):
                manifest_input_hashes[path.resolve()] = record.get("sha256")
    if len(input_paths) != len(set(input_paths)):
        errors.append("run_manifest.json inputs contains duplicate paths")

    plan_record = manifest.get("plan")
    plan_path = verify_file_hash(
        run_root, plan_record, "run_manifest.json plan", errors
    )
    if plan_path is not None and plan_path.resolve() != (
        run_root / "image_set_plan.json"
    ).resolve():
        errors.append("run_manifest.json plan.path must be image_set_plan.json")

    prompts_record = manifest.get("prompts")
    prompts_path = verify_file_hash(
        run_root, prompts_record, "run_manifest.json prompts", errors
    )
    if prompts_path is not None and prompts_path.resolve() != (
        run_root / "prompts.md"
    ).resolve():
        errors.append("run_manifest.json prompts.path must be prompts.md")

    required_evidence = [
        ("brief", "brief.json"),
        ("content_plan", "content_plan.md"),
    ]
    if effective_mode == "generation":
        required_evidence.extend(
            [
                ("qa_report", "qa_report.json"),
                ("contact_sheet", "contact_sheet.jpg"),
            ]
        )
    for evidence_name, expected_path in required_evidence:
        if evidence_name not in manifest:
            errors.append(
                f"run_manifest.json required evidence {evidence_name} is missing"
            )
            continue
        evidence_path = verify_file_hash(
            run_root,
            manifest.get(evidence_name),
            f"run_manifest.json required evidence {evidence_name}",
            errors,
        )
        if evidence_path is not None and evidence_path.resolve() != (
            run_root / expected_path
        ).resolve():
            errors.append(
                f"run_manifest.json required evidence {evidence_name}.path "
                f"must be {expected_path}"
            )

    for optional_name, expected_path in (
        ("qa_report", "qa_report.json"),
        ("contact_sheet", "contact_sheet.jpg"),
    ):
        if (
            effective_mode != "generation"
            and optional_name in manifest
            and manifest[optional_name] not in (None, {})
        ):
            optional_path = verify_file_hash(
                run_root,
                manifest[optional_name],
                f"run_manifest.json {optional_name}",
                errors,
            )
            if optional_path is not None and optional_path.resolve() != (
                run_root / expected_path
            ).resolve():
                errors.append(
                    f"run_manifest.json {optional_name}.path must be {expected_path}"
                )

    plan_shots = as_list(plan.get("shots"), "image_set_plan.json shots", errors)
    manifest_shots = as_list(
        manifest.get("shots"), "run_manifest.json shots", errors
    )
    plan_ids = shot_ids(plan_shots, "image_set_plan.json shots", errors)
    manifest_ids = shot_ids(manifest_shots, "run_manifest.json shots", errors)
    recommended_count = plan.get("recommended_image_count")
    if (
        not isinstance(recommended_count, int)
        or isinstance(recommended_count, bool)
        or recommended_count != len(plan_shots)
    ):
        errors.append(
            "image_set_plan.json recommended_image_count does not match shot count"
        )

    qa_shots = []
    qa_ids = []
    if effective_mode == "generation":
        qa_shots = as_list(qa.get("shots"), "qa_report.json shots", errors)
        qa_ids = shot_ids(qa_shots, "qa_report.json shots", errors)
        all_qa_passed = bool(qa_shots)
        for qa_index, raw_qa_shot in enumerate(qa_shots):
            qa_label = f"qa_report.json shots[{qa_index}]"
            qa_shot = as_dict(raw_qa_shot, qa_label, errors)
            if qa_shot.get("verdict") != "pass":
                all_qa_passed = False

            reviewed_at = parse_timestamp(
                qa_shot.get("reviewed_at"),
                f"{qa_label}.reviewed_at",
                errors,
            )
            if (
                reviewed_at is not None
                and run_started is not None
                and reviewed_at < run_started
            ):
                errors.append(f"{qa_label}.reviewed_at precedes the run")
            if (
                reviewed_at is not None
                and run_finished is not None
                and reviewed_at > run_finished
            ):
                errors.append(f"{qa_label}.reviewed_at exceeds the run")

            reviewer = qa_shot.get("reviewer")
            if not isinstance(reviewer, str) or not reviewer.strip():
                errors.append(f"{qa_label}.reviewer must be a non-empty string")

            checks = as_dict(qa_shot.get("checks"), f"{qa_label}.checks", errors)
            for check_name in sorted(REQUIRED_QA_CHECKS):
                if check_name not in checks:
                    errors.append(
                        f"{qa_label}.checks.{check_name} is required"
                    )
                    continue
                result = checks.get(check_name)
                if result not in ALLOWED_QA_CHECK_RESULTS:
                    errors.append(
                        f"{qa_label}.checks.{check_name} must be pass or "
                        "not_applicable"
                    )

            issues = qa_shot.get("issues")
            if not isinstance(issues, list):
                errors.append(f"{qa_label}.issues must be an array")
            elif any(not isinstance(issue, str) for issue in issues):
                errors.append(f"{qa_label}.issues entries must be strings")

            if not isinstance(qa_shot.get("recovery"), str):
                errors.append(f"{qa_label}.recovery must be a string")

        if qa.get("overall_verdict") != "pass" or not all_qa_passed:
            errors.append(
                "generation delivery is incomplete: overall and all planned "
                "shots must pass"
            )

    if len(plan_shots) != len(manifest_shots):
        errors.append("plan and manifest shot count mismatch")
    if effective_mode == "generation" and len(plan_shots) != len(qa_shots):
        errors.append("plan, manifest, and qa shot count mismatch")
    if set(plan_ids) != set(manifest_ids):
        errors.append("plan and manifest shots must map one-to-one by image_id")
    if effective_mode == "generation" and set(plan_ids) != set(qa_ids):
        errors.append("plan, manifest, and qa shots must map one-to-one by image_id")

    input_path_set = set(input_paths)
    for shot_index, raw_shot in enumerate(plan_shots):
        shot = as_dict(raw_shot, f"image_set_plan.json shots[{shot_index}]", errors)
        references = as_list(
            shot.get("reference_inputs"),
            f"image_set_plan.json shots[{shot_index}].reference_inputs",
            errors,
        )
        for reference_index, raw_reference in enumerate(references):
            reference = as_dict(
                raw_reference,
                f"image_set_plan.json shots[{shot_index}]."
                f"reference_inputs[{reference_index}]",
                errors,
            )
            label = (
                f"plan reference shots[{shot_index}]."
                f"reference_inputs[{reference_index}].path"
            )
            path = safe_path(run_root, reference.get("path"), label, errors, "file")
            require_under(path, inputs_dir, label, errors)
            if path is not None and path.resolve() not in input_path_set:
                errors.append(f"{label} is not recorded in manifest inputs")

    qa_by_id = {
        item.get("image_id"): item
        for item in qa_shots
        if isinstance(item, dict) and isinstance(item.get("image_id"), str)
    }
    plan_by_id = {
        item.get("image_id"): item
        for item in plan_shots
        if isinstance(item, dict) and isinstance(item.get("image_id"), str)
    }
    platform_decision = as_dict(
        plan.get("platform_decision", {}),
        "image_set_plan.json platform_decision",
        errors,
    )
    platform_type = platform_decision.get("platform_type")
    is_amazon = (
        isinstance(platform_type, str)
        and platform_type.strip().lower() == "amazon"
    )
    total_attempts = 0
    total_shot_elapsed = 0
    accepted_count = 0
    output_paths = []
    for shot_index, raw_shot in enumerate(manifest_shots):
        label = f"run_manifest.json shots[{shot_index}]"
        shot = as_dict(raw_shot, label, errors)
        attempt_count, shot_elapsed, attempt_statuses = validate_attempts(
            shot,
            label,
            effective_mode,
            run_root,
            inputs_dir,
            manifest_input_hashes,
            run_started,
            run_finished,
            errors,
        )
        if attempt_count is not None:
            total_attempts += attempt_count
        if shot_elapsed is not None:
            total_shot_elapsed += shot_elapsed

        verdict = shot.get("qa_verdict")
        qa_shot = qa_by_id.get(shot.get("image_id"), {})
        qa_verdict = qa_shot.get("verdict")
        passed = verdict == "pass"
        if effective_mode == "generation":
            if verdict != "pass":
                errors.append(f"{label}.qa_verdict must be pass")
            if qa_verdict != "pass":
                errors.append(
                    f"qa record for {shot.get('image_id')!r} verdict must be pass"
                )
            if verdict != qa_verdict:
                errors.append(
                    f"{label} qa verdict does not match qa_report.json"
                )
            if passed and "success" not in attempt_statuses:
                errors.append(
                    f"{label} passed shot requires a successful audited attempt"
                )

        output_path_value = shot.get("output_path")
        output_hash = shot.get("output_sha256")
        if passed:
            accepted_count += 1
            path = verify_file_hash(
                run_root,
                {"path": output_path_value, "sha256": output_hash},
                f"{label} accepted output",
                errors,
                run_root / "outputs",
            )
            if path is not None:
                output_paths.append(path.resolve())
                plan_shot = plan_by_id.get(shot.get("image_id"), {})
                if is_amazon and plan_shot.get("role") == "main_white":
                    validate_amazon_main_white_evidence(
                        path,
                        qa_shot,
                        f"qa record for {shot.get('image_id')!r}",
                        errors,
                    )
            if qa_shot.get("output_path") != output_path_value:
                errors.append(
                    f"qa output path for {shot.get('image_id')!r} must match "
                    "the accepted manifest output"
                )
        elif output_path_value not in (None, "") or output_hash not in (None, ""):
            errors.append(f"{label} may claim a final output only when qa verdict is pass")

        if effective_mode == "planning_only":
            if verdict not in (None, "", "not_generated"):
                errors.append(f"plan-only {label}.qa_verdict must be empty")
            for field in ("output_path", "output_sha256"):
                if shot.get(field) not in (None, ""):
                    errors.append(f"plan-only {label}.{field} must be empty")

    if len(output_paths) != len(set(output_paths)):
        errors.append("accepted outputs must use distinct files")

    metrics = as_dict(
        manifest.get("aggregate_metrics"),
        "run_manifest.json aggregate_metrics",
        errors,
    )
    expected_metrics = {
        "shot_count": len(manifest_shots),
        "attempt_count": total_attempts,
        "elapsed_ms": total_shot_elapsed,
        "accepted_count": accepted_count,
    }
    for field, expected in expected_metrics.items():
        actual = non_negative_int(
            metrics.get(field), f"aggregate_metrics.{field}", errors
        )
        if actual is not None and actual != expected:
            errors.append(
                f"aggregate_metrics.{field}={actual} does not match "
                f"recomputed {field}={expected}"
            )

    if effective_mode == "generation":
        output_dir = run_root / "outputs"
        if output_dir.is_dir() and not any(
            child.is_file() for child in output_dir.rglob("*")
        ):
            errors.append("generation outputs/ must contain saved output files")
        if accepted_count == 0:
            errors.append("generation requires at least one verified accepted output")
        if accepted_count != len(plan_shots):
            errors.append(
                "generation delivery is incomplete: all planned shots must pass"
            )
    elif effective_mode == "planning_only":
        output_dir = run_root / "outputs"
        if output_dir.exists() and any(
            child.is_file() for child in output_dir.rglob("*")
        ):
            errors.append("plan-only run must not contain generated output files")
        for forbidden in ("qa_report.json", "contact_sheet.jpg"):
            if (run_root / forbidden).exists():
                errors.append(f"plan-only run must not claim generated file {forbidden}")
        for field in ("qa_report", "contact_sheet", "outputs"):
            if manifest.get(field) not in (None, {}, [], ""):
                errors.append(f"plan-only run_manifest.json {field} must be empty")
        if accepted_count:
            errors.append("plan-only run must not claim successful generated outputs")

    return errors


def main(argv):
    if len(argv) != 2:
        print("Usage: validate_delivery.py RUN_DIR", file=sys.stderr)
        return 2

    errors = validate(Path(argv[1]))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("VALID: auditable ecommerce delivery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
