#!/usr/bin/env python3
"""Validate a planning-ecommerce-image-sets JSON plan."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path


REQUIRED_TOP_LEVEL = {
    "version",
    "overall_status",
    "platform_decision",
    "language_decision",
    "input_assessment",
    "facts",
    "buyer_questions",
    "visual_system",
    "recommended_image_count",
    "count_reason",
    "shots",
    "deferred_modules",
    "ready_now",
    "needs_more_info",
    "overall_risks",
}

ALLOWED_PLATFORM_TYPES = {
    "amazon",
    "domestic_marketplace",
    "social_commerce",
    "brand_site",
    "portfolio",
    "custom",
}
ALLOWED_ACTIONS = {
    "reuse",
    "clean_up",
    "reference_generate",
    "scene_composite",
    "generate_then_layout",
}
ALLOWED_ROLES = {
    "hero_kv",
    "main_white",
    "editorial_cover",
    "selling_points",
    "specification",
    "feature_detail",
    "material_macro",
    "scale_capacity",
    "package_contents",
    "comparison",
    "usage_scene",
}
ALLOWED_PRIORITIES = {"required", "recommended", "optional"}
ALLOWED_RATIOS = {"1:1", "3:4", "4:5", "9:16", "4:3", "16:9"}
ALLOWED_TEXT_MODES = {"none", "direct", "post_layout"}
ALLOWED_OVERALL_STATUSES = {"ready", "partially_ready", "blocked"}
ALLOWED_BLOCKING_SCOPES = {"module", "whole_product"}
ALLOWED_DECISION_SOURCES = {"explicit", "inferred", "default"}
ALLOWED_CONFIDENCE_LEVELS = {"high", "medium", "low"}
ALLOWED_FIRST_IMAGE_RULES = {"main_white", "hero_kv", "editorial_cover", "custom"}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
POST_LAYOUT_NO_TEXT_RE = re.compile(
    r"(?:不|不要|不得|避免).{0,16}(?:新增)?(?:任何)?(?:文字|文案|数字|字样)|无字底图|不生字"
)
REQUIRED_FACT_FIELDS = {
    "visible_facts",
    "user_confirmed_facts",
    "official_confirmed_facts",
    "uncertain_observations",
    "missing_critical_info",
    "creative_assumptions",
}


def require_dict(value, path, errors):
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return {}
    return value


def require_list(value, path, errors):
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    return value


def require_non_empty_string(value, path, errors):
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")
        return False
    return True


def require_non_empty_string_list(value, path, errors):
    values = require_list(value, path, errors)
    if not values:
        errors.append(f"{path} must not be empty")
        return values
    for index, item in enumerate(values):
        require_non_empty_string(item, f"{path}[{index}]", errors)
    return values


def is_iso_date_or_datetime(value):
    try:
        if ISO_DATE_RE.match(value):
            date.fromisoformat(value)
        elif ISO_DATETIME_RE.match(value):
            datetime.fromisoformat(value)
        else:
            return False
    except ValueError:
        return False
    return True


def validate_multi_set_manifest(manifest):
    errors = []
    if manifest.get("output_kind") != "multi_set_manifest":
        errors.append("multi-set manifest requires output_kind=multi_set_manifest")
    if manifest.get("set_strategy") != "split":
        errors.append("multi-set manifest requires set_strategy=split")
    sets = manifest.get("sets")
    if not isinstance(sets, list) or len(sets) < 2:
        errors.append("multi-set manifest requires at least two independent sets")
        return errors

    platform_keys = []
    for index, set_plan in enumerate(sets):
        if not isinstance(set_plan, dict):
            errors.append(f"multi-set manifest sets[{index}] must be an object")
            continue
        for error in validate(set_plan):
            errors.append(f"sets[{index}]: {error}")
        platform = set_plan.get("platform_decision")
        if isinstance(platform, dict):
            platform_keys.append(
                (
                    platform.get("platform_type"),
                    platform.get("platform_name"),
                )
            )

    if len(platform_keys) == len(sets) and len(set(platform_keys)) != len(sets):
        errors.append(
            "multi-set manifest sets must target distinct platform contracts"
        )
    return errors


def validate(plan):
    errors = []
    if not isinstance(plan, dict):
        return ["root must be a JSON object"]

    if any(field in plan for field in ("output_kind", "set_strategy", "sets")):
        return validate_multi_set_manifest(plan)

    for field in sorted(REQUIRED_TOP_LEVEL - set(plan)):
        errors.append(f"missing required field: {field}")

    if plan.get("version") != "2.0":
        errors.append("version must be '2.0'")

    platform = require_dict(plan.get("platform_decision"), "platform_decision", errors)
    language = require_dict(plan.get("language_decision"), "language_decision", errors)
    facts = require_dict(plan.get("facts"), "facts", errors)
    shots = require_list(plan.get("shots"), "shots", errors)
    ready_now = require_list(plan.get("ready_now"), "ready_now", errors)
    needs_more_info = require_list(
        plan.get("needs_more_info"), "needs_more_info", errors
    )

    overall_status = plan.get("overall_status")
    if overall_status not in ALLOWED_OVERALL_STATUSES:
        errors.append(f"overall_status is invalid: {overall_status!r}")

    for field in sorted(REQUIRED_FACT_FIELDS):
        if field not in facts:
            errors.append(f"facts.{field} is required")
        else:
            require_list(facts.get(field), f"facts.{field}", errors)

    platform_type = platform.get("platform_type")
    if platform_type not in ALLOWED_PLATFORM_TYPES:
        errors.append(f"platform_decision.platform_type is invalid: {platform_type!r}")
    platform_ratio = platform.get("aspect_ratio")
    if platform_ratio not in ALLOWED_RATIOS:
        errors.append(f"platform_decision.aspect_ratio is invalid: {platform_ratio!r}")
    require_non_empty_string(
        platform.get("platform_name"), "platform_decision.platform_name", errors
    )
    decision_source = platform.get("decision_source")
    if decision_source not in ALLOWED_DECISION_SOURCES:
        errors.append(
            f"platform_decision.decision_source is invalid: {decision_source!r}"
        )
    confidence = platform.get("confidence")
    if confidence not in ALLOWED_CONFIDENCE_LEVELS:
        errors.append(f"platform_decision.confidence is invalid: {confidence!r}")
    first_image_rule = platform.get("first_image_rule")
    if first_image_rule not in ALLOWED_FIRST_IMAGE_RULES:
        errors.append(
            f"platform_decision.first_image_rule is invalid: {first_image_rule!r}"
        )

    rule_checked_at = platform.get("rule_checked_at")
    if require_non_empty_string(
        rule_checked_at, "platform_decision.rule_checked_at", errors
    ):
        if not is_iso_date_or_datetime(rule_checked_at):
            errors.append(
                "platform_decision.rule_checked_at must use an ISO 8601 date or datetime"
            )

    require_non_empty_string_list(
        platform.get("hard_rules"), "platform_decision.hard_rules", errors
    )
    require_non_empty_string_list(
        platform.get("creative_guidance"),
        "platform_decision.creative_guidance",
        errors,
    )
    rule_sources = require_list(
        platform.get("rule_sources"), "platform_decision.rule_sources", errors
    )
    if not rule_sources:
        errors.append("platform_decision.rule_sources must not be empty")
    for index, raw_source in enumerate(rule_sources):
        source_path = f"platform_decision.rule_sources[{index}]"
        source = require_dict(raw_source, source_path, errors)
        for field in ("title", "url", "source_type"):
            require_non_empty_string(source.get(field), f"{source_path}.{field}", errors)

    if decision_source == "default" and platform_type != "portfolio":
        errors.append(
            "default platform decisions must use platform_type=portfolio"
        )

    if language.get("planning_language") != "zh-CN":
        errors.append("language_decision.planning_language must be zh-CN")
    if language.get("prompt_language") != "zh-CN":
        errors.append("language_decision.prompt_language must be zh-CN")
    if not language.get("overlay_language"):
        errors.append("language_decision.overlay_language is required")
    if language.get("packaging_text_policy") != "preserve_original":
        errors.append("language_decision.packaging_text_policy must be preserve_original")

    count = plan.get("recommended_image_count")
    if not isinstance(count, int) or isinstance(count, bool):
        errors.append("recommended_image_count must be an integer")
    else:
        if overall_status == "blocked":
            if count != 0:
                errors.append(
                    "blocked plan requires recommended_image_count=0, shots=[], and ready_now=[]"
                )
        elif count < 1:
            errors.append(
                "recommended_image_count must be a positive integer for non-blocked plans"
            )
        if count != len(shots):
            errors.append(
                f"recommended_image_count={count} does not match shots={len(shots)}"
            )

    shot_ids = []
    ratios = set()
    for index, raw_shot in enumerate(shots):
        path = f"shots[{index}]"
        shot = require_dict(raw_shot, path, errors)
        image_id = shot.get("image_id")
        if not isinstance(image_id, str) or not image_id.strip():
            errors.append(f"{path}.image_id is required")
        else:
            shot_ids.append(image_id)

        action = shot.get("execution_action")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"{path}.execution_action is invalid: {action!r}")

        role = shot.get("role")
        if role not in ALLOWED_ROLES:
            errors.append(f"{path}.role is invalid: {role!r}")
        priority = shot.get("priority")
        if priority not in ALLOWED_PRIORITIES:
            errors.append(f"{path}.priority is invalid: {priority!r}")

        risk = shot.get("reference_risk")
        if risk == "blocked":
            errors.append(f"{path}.reference_risk blocked shots must be deferred")
        elif risk not in {"low", "medium"}:
            errors.append(f"{path}.reference_risk is invalid: {risk!r}")

        ratio = shot.get("aspect_ratio")
        if ratio not in ALLOWED_RATIOS:
            errors.append(f"{path}.aspect_ratio is invalid: {ratio!r}")
        else:
            ratios.add(ratio)

        reference_inputs = require_list(
            shot.get("reference_inputs"), f"{path}.reference_inputs", errors
        )
        if not reference_inputs:
            errors.append(f"{path}.reference_inputs must not be empty")
        for reference_index, raw_reference in enumerate(reference_inputs):
            reference_path = f"{path}.reference_inputs[{reference_index}]"
            reference = require_dict(raw_reference, reference_path, errors)
            for field in ("path", "purpose"):
                require_non_empty_string(
                    reference.get(field), f"{reference_path}.{field}", errors
                )

        prompt = shot.get("generation_prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"{path}.generation_prompt is required")
        elif not CHINESE_RE.search(prompt):
            errors.append(f"{path}.generation_prompt must contain Chinese instructions")

        text_strategy = require_dict(shot.get("text_strategy"), f"{path}.text_strategy", errors)
        mode = text_strategy.get("mode")
        if mode not in ALLOWED_TEXT_MODES:
            errors.append(f"{path}.text_strategy.mode is invalid: {mode!r}")
        if text_strategy.get("overlay_language") != language.get("overlay_language"):
            errors.append(
                f"{path}.text_strategy.overlay_language must match language_decision.overlay_language"
            )
        exact_copy = require_list(
            text_strategy.get("exact_copy"), f"{path}.text_strategy.exact_copy", errors
        )
        if mode == "none" and exact_copy:
            errors.append(f"{path}.text_strategy exact_copy must be empty when mode=none")
        if mode in {"direct", "post_layout"} and not exact_copy:
            errors.append(
                f"{path}.text_strategy.exact_copy must not be empty when mode={mode}"
            )
        if (
            mode == "post_layout"
            and isinstance(prompt, str)
            and prompt.strip()
            and not POST_LAYOUT_NO_TEXT_RE.search(prompt)
        ):
            errors.append(
                f"{path}.text_strategy mode=post_layout requires the generation_prompt "
                "to forbid generated overlay text and reserve a clean layout area"
            )

        for field in (
            "role",
            "priority",
            "content_message",
            "buyer_question_answered",
        ):
            if not shot.get(field):
                errors.append(f"{path}.{field} is required")
        for field in ("negative_constraints", "qa_checks"):
            values = require_list(shot.get(field), f"{path}.{field}", errors)
            if not values:
                errors.append(f"{path}.{field} must not be empty")

    if len(shot_ids) != len(set(shot_ids)):
        errors.append("shots contain duplicate image_id values")
    if len(ratios) > 1:
        errors.append(f"shots.aspect_ratio must be unified; found {sorted(ratios)}")
    if ratios and platform_ratio not in ratios:
        errors.append(
            "platform_decision.aspect_ratio must match every shots[].aspect_ratio"
        )
    if ready_now != shot_ids:
        errors.append("ready_now must exactly match shots image_id values in order")
    if isinstance(count, int) and count != len(ready_now):
        errors.append(
            f"recommended_image_count={count} does not match ready_now={len(ready_now)}"
        )

    deferred = require_list(plan.get("deferred_modules"), "deferred_modules", errors)
    deferred_ids = []
    blocking_scopes = []
    for index, module in enumerate(deferred):
        item = require_dict(module, f"deferred_modules[{index}]", errors)
        module_id = item.get("module_id")
        if not module_id:
            errors.append(f"deferred_modules[{index}].module_id is required")
        else:
            deferred_ids.append(module_id)
        if not item.get("why_deferred"):
            errors.append(f"deferred_modules[{index}].why_deferred is required")
        if not require_list(
            item.get("required_inputs"),
            f"deferred_modules[{index}].required_inputs",
            errors,
        ):
            errors.append(f"deferred_modules[{index}].required_inputs must not be empty")
        blocking_scope = item.get("blocking_scope")
        if blocking_scope is None:
            errors.append(f"deferred_modules[{index}].blocking_scope is required")
        elif blocking_scope not in ALLOWED_BLOCKING_SCOPES:
            errors.append(
                f"deferred_modules[{index}].blocking_scope is invalid: {blocking_scope!r}"
            )
        else:
            blocking_scopes.append(blocking_scope)
    overlap = set(deferred_ids) & set(ready_now)
    if overlap:
        errors.append(f"deferred_modules must not appear in ready_now: {sorted(overlap)}")

    has_module_blocker = "module" in blocking_scopes
    has_whole_product_blocker = "whole_product" in blocking_scopes
    if has_whole_product_blocker and shots:
        errors.append(
            "whole_product deferred modules cannot coexist with executable shots"
        )
    if overall_status == "ready":
        if (
            not isinstance(count, int)
            or isinstance(count, bool)
            or count < 1
            or not shots
            or not ready_now
        ):
            errors.append(
                "ready plan requires a positive executable subset in shots and ready_now"
            )
        if deferred:
            errors.append("ready plan cannot contain deferred_modules")
    elif overall_status == "partially_ready":
        if (
            not isinstance(count, int)
            or isinstance(count, bool)
            or count < 1
            or not shots
            or not ready_now
        ):
            errors.append(
                "partially_ready plan requires a positive executable subset in shots and ready_now"
            )
        if not has_module_blocker:
            errors.append(
                "partially_ready plan requires at least one module-scoped deferred module"
            )
        if has_whole_product_blocker:
            errors.append("partially_ready plan cannot contain whole_product blockers")
    elif overall_status == "blocked":
        if count != 0 or shots or ready_now:
            message = (
                "blocked plan requires recommended_image_count=0, shots=[], and ready_now=[]"
            )
            if message not in errors:
                errors.append(message)
        if not needs_more_info:
            errors.append("blocked plan requires non-empty needs_more_info")
        if not has_whole_product_blocker:
            errors.append(
                "blocked plan requires at least one explicit whole_product deferred module; "
                "module-scoped or missing-scope deferrals cannot block the whole product"
            )

    if shots:
        first = shots[0] if isinstance(shots[0], dict) else {}
        first_text = first.get("text_strategy", {})
        if first_image_rule != "custom" and first.get("role") != first_image_rule:
            errors.append(
                "first shot role must match platform_decision.first_image_rule"
            )
        if first_image_rule == "main_white" and (
            first_text.get("mode") != "none" or first_text.get("exact_copy")
        ):
            errors.append("main_white first shot must not contain overlay copy")

    return errors


def main(argv):
    if len(argv) != 2:
        print("Usage: validate_plan.py PLAN.json", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        plan = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}")
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
        return 1

    errors = validate(plan)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    if plan.get("output_kind") == "multi_set_manifest":
        print(f"VALID: {len(plan['sets'])} independent sets")
    else:
        print(
            f"VALID: {plan['recommended_image_count']} executable shots, "
            f"{len(plan['deferred_modules'])} deferred modules"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
