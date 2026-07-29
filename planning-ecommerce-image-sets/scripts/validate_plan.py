#!/usr/bin/env python3
"""Validate a planning-ecommerce-image-sets JSON plan."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse


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
    "global_marketplace",
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
    "main_product",
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
ALLOWED_TEXT_MODES = {"none", "direct", "post_layout"}
ALLOWED_OVERALL_STATUSES = {"ready", "partially_ready", "blocked"}
ALLOWED_BLOCKING_SCOPES = {"module", "whole_product"}
ALLOWED_DECISION_SOURCES = {"explicit", "inferred", "default"}
ALLOWED_CONFIDENCE_LEVELS = {"high", "medium", "low"}
ALLOWED_FIRST_IMAGE_RULES = {
    "main_white",
    "main_product",
    "hero_kv",
    "editorial_cover",
    "custom",
}
ALLOWED_PLATFORM_VERIFICATION_STATUSES = {
    "verified_current",
    "partially_verified",
    "live_check_required",
    "not_applicable",
}
ALLOWED_RULE_SOURCE_TYPES = {
    "official_public",
    "official_staff",
    "official_authenticated",
    "official_public_archive",
    "live_platform_ui",
    "user_contract",
    "project_contract",
    "skill_local",
}
CURRENT_PLATFORM_SOURCE_TYPES = {
    "official_public",
    "official_staff",
    "official_authenticated",
    "live_platform_ui",
}
PLATFORM_EVIDENCE_SOURCE_TYPES = (
    CURRENT_PLATFORM_SOURCE_TYPES | {"official_public_archive"}
)
MARKETPLACE_PLATFORM_TYPES = {
    "amazon",
    "global_marketplace",
    "domestic_marketplace",
    "social_commerce",
}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
ASPECT_RATIO_RE = re.compile(r"^([1-9]\d*):([1-9]\d*)$")
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
PLATFORM_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "platform-requirements.json"
)
PROFILE_TO_PLAN_STATUS = {
    "verified_public": {
        "verified_current",
        "partially_verified",
        "live_check_required",
    },
    "partial_public": {
        "partially_verified",
        "live_check_required",
    },
    "live_check_required": {
        "live_check_required",
    },
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
            parsed_date = date.fromisoformat(value)
        elif ISO_DATETIME_RE.match(value):
            parsed_date = datetime.fromisoformat(value).date()
        else:
            return None
    except ValueError:
        return None
    return parsed_date


def is_aspect_ratio(value, *, allow_mixed=False):
    if allow_mixed and value == "mixed":
        return True
    return isinstance(value, str) and ASPECT_RATIO_RE.match(value) is not None


def host_is_allowed(hostname, official_hosts):
    if not isinstance(hostname, str):
        return False
    hostname = hostname.lower().rstrip(".")
    return any(
        hostname == allowed or hostname.endswith(f".{allowed}")
        for allowed in official_hosts
        if isinstance(allowed, str) and allowed
    )


def normalize_platform_name(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).casefold()


def load_platform_profiles(errors):
    try:
        registry = json.loads(PLATFORM_REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"bundled platform registry is unavailable: {exc}")
        return {}
    profiles = registry.get("profiles")
    if not isinstance(profiles, list):
        errors.append("bundled platform registry profiles must be an array")
        return {}
    return {
        profile.get("id"): profile
        for profile in profiles
        if isinstance(profile, dict) and isinstance(profile.get("id"), str)
    }


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

    if plan.get("version") != "3.0":
        errors.append(
            "version must be '3.0'; migrate legacy 2.0 plans by adding the "
            "platform profile, verification status, hard_rule_ids, source, "
            "and recheck fields"
        )

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
    if not is_aspect_ratio(platform_ratio, allow_mixed=True):
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
    require_non_empty_string(
        platform.get("platform_profile_id"),
        "platform_decision.platform_profile_id",
        errors,
    )
    verification_status = platform.get("verification_status")
    if verification_status not in ALLOWED_PLATFORM_VERIFICATION_STATUSES:
        errors.append(
            "platform_decision.verification_status is invalid: "
            f"{verification_status!r}"
        )

    platform_profile_id = platform.get("platform_profile_id")
    profiles = (
        load_platform_profiles(errors)
        if isinstance(platform_profile_id, str) and platform_profile_id.strip()
        else {}
    )
    profile = profiles.get(platform_profile_id)
    declared_source_types = {
        source.get("source_type")
        for source in platform.get("rule_sources", [])
        if isinstance(source, dict)
    }
    if profile is None:
        if platform_type in MARKETPLACE_PLATFORM_TYPES:
            errors.append(
                "platform_decision.platform_profile_id is not present in the "
                f"bundled registry: {platform_profile_id!r}"
            )
        elif platform_type == "brand_site":
            has_project_contract = bool(
                declared_source_types & {"project_contract", "user_contract"}
            )
            normalized_name = normalize_platform_name(
                platform.get("platform_name")
            )
            known_brand_names = {
                normalize_platform_name(item.get("platform"))
                for item in profiles.values()
                if item.get("platform_type") == "brand_site"
            }
            names_a_known_brand = any(
                known_name and known_name in normalized_name
                for known_name in known_brand_names
            )
            if (
                names_a_known_brand
                or
                verification_status != "not_applicable"
                or not has_project_contract
            ):
                errors.append(
                    "known brand_site profile must be selected for that platform; "
                    "other brand sites require an explicit project/user contract "
                    "with verification_status=not_applicable"
                )
    else:
        if profile.get("platform_type") != platform_type:
            errors.append(
                "platform_decision.platform_type does not match the bundled "
                f"profile: {platform_type!r} != {profile.get('platform_type')!r}"
            )
        allowed_plan_statuses = PROFILE_TO_PLAN_STATUS.get(
            profile.get("verification_status"), set()
        )
        if verification_status not in allowed_plan_statuses:
            errors.append(
                "platform_decision.verification_status cannot be more certain "
                "than bundled profile "
                f"{profile.get('verification_status')!r}; live platform evidence "
                "must be reviewed into the registry before it can raise certainty"
            )
        profile_first_image_rule = profile.get("first_image_rule")
        if (
            profile_first_image_rule != "custom"
            and first_image_rule != profile_first_image_rule
        ):
            errors.append(
                "platform_decision.first_image_rule does not match the bundled "
                "profile; live or user evidence cannot automatically relax it, "
                "so update and re-review the registry first"
            )

    rule_checked_at = platform.get("rule_checked_at")
    if require_non_empty_string(
        rule_checked_at, "platform_decision.rule_checked_at", errors
    ):
        checked_date = is_iso_date_or_datetime(rule_checked_at)
        if checked_date is None:
            errors.append(
                "platform_decision.rule_checked_at must use an ISO 8601 date or datetime"
            )
        elif checked_date > date.today():
            errors.append(
                "platform_decision.rule_checked_at cannot be in the future"
            )

    hard_rules = require_list(
        platform.get("hard_rules"), "platform_decision.hard_rules", errors
    )
    for index, item in enumerate(hard_rules):
        require_non_empty_string(
            item, f"platform_decision.hard_rules[{index}]", errors
        )
    hard_rule_ids = require_list(
        platform.get("hard_rule_ids"),
        "platform_decision.hard_rule_ids",
        errors,
    )
    for index, item in enumerate(hard_rule_ids):
        require_non_empty_string(
            item, f"platform_decision.hard_rule_ids[{index}]", errors
        )
    if len(hard_rule_ids) != len(hard_rules):
        errors.append(
            "platform_decision.hard_rule_ids must align one-to-one with hard_rules"
        )
    if len(hard_rule_ids) != len(set(hard_rule_ids)):
        errors.append("platform_decision.hard_rule_ids contains duplicates")
    if profile is not None:
        profile_hard_rules = {
            rule.get("id"): rule.get("claim")
            for rule in profile.get("hard_rules", [])
            if isinstance(rule, dict)
        }
        for index, (rule_id, rule_claim) in enumerate(
            zip(hard_rule_ids, hard_rules)
        ):
            expected_claim = profile_hard_rules.get(rule_id)
            if expected_claim is None:
                errors.append(
                    "platform_decision.hard_rule_ids contains a rule not present "
                    f"in the bundled profile: {rule_id!r}"
                )
            elif rule_claim != expected_claim:
                errors.append(
                    f"platform_decision.hard_rules[{index}] does not match bundled "
                    f"hard rule {rule_id!r}"
                )
        if verification_status == "verified_current":
            missing_profile_rule_ids = (
                set(profile_hard_rules) - set(hard_rule_ids)
            )
            if missing_profile_rule_ids:
                errors.append(
                    "verified_current plans must inherit every bundled hard rule; "
                    f"missing IDs: {sorted(missing_profile_rule_ids)}"
                )
    if verification_status == "verified_current" and not hard_rules:
        errors.append("verified platform decisions require hard_rules")
    if verification_status == "live_check_required" and hard_rules:
        errors.append(
            "platform_decision.hard_rules must be empty when verification_status="
            f"{verification_status}"
        )
    require_non_empty_string_list(
        platform.get("creative_guidance"),
        "platform_decision.creative_guidance",
        errors,
    )
    publish_time_recheck = require_list(
        platform.get("publish_time_recheck"),
        "platform_decision.publish_time_recheck",
        errors,
    )
    for index, item in enumerate(publish_time_recheck):
        require_non_empty_string(
            item, f"platform_decision.publish_time_recheck[{index}]", errors
        )
    if (
        verification_status in {"partially_verified", "live_check_required"}
        and not publish_time_recheck
    ):
        errors.append(
            "platform_decision.publish_time_recheck must not be empty when "
            f"verification_status={verification_status}"
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
        source_type = source.get("source_type")
        if source_type not in ALLOWED_RULE_SOURCE_TYPES:
            errors.append(f"{source_path}.source_type is invalid: {source_type!r}")
        source_url = source.get("url")
        if (
            source_type
            in {
                "official_public",
                "official_staff",
                "official_authenticated",
                "official_public_archive",
                "live_platform_ui",
            }
            and isinstance(source_url, str)
            and source_url.strip()
        ):
            parsed_url = urlparse(source_url)
            if parsed_url.scheme != "https" or not parsed_url.netloc:
                errors.append(f"{source_path} official source URL must use HTTPS")
            elif profile is not None and not host_is_allowed(
                parsed_url.hostname,
                profile.get("official_hosts", []),
            ):
                errors.append(
                    f"{source_path} host {parsed_url.hostname!r} is not recognized "
                    "by the bundled profile official_hosts"
                )

    platform_evidence_sources = {
        source.get("source_type")
        for source in rule_sources
        if isinstance(source, dict)
    } & PLATFORM_EVIDENCE_SOURCE_TYPES
    current_platform_sources = (
        platform_evidence_sources & CURRENT_PLATFORM_SOURCE_TYPES
    )
    if profile is not None or platform_type in MARKETPLACE_PLATFORM_TYPES:
        if verification_status == "verified_current" and not current_platform_sources:
            errors.append(
                "verified marketplace decisions require at least one current "
                "official platform source"
            )
        elif (
            verification_status == "partially_verified"
            and not platform_evidence_sources
        ):
            errors.append(
                "partially verified marketplace decisions require at least one "
                "official current or archive source"
            )
        elif (
            verification_status == "live_check_required"
            and not current_platform_sources
        ):
            errors.append(
                "live-check marketplace decisions require at least one current "
                "official platform source or live platform UI"
            )

    if verification_status == "not_applicable" and platform_type in MARKETPLACE_PLATFORM_TYPES:
        errors.append(
            "marketplace platform decisions cannot use verification_status=not_applicable"
        )

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
        if not is_aspect_ratio(ratio):
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

    if profile is not None and overall_status != "blocked":
        constraints = profile.get("machine_constraints")
        if isinstance(constraints, dict):
            minimum = constraints.get("min_plan_images")
            maximum = constraints.get("max_plan_images")
            if (
                isinstance(count, int)
                and not isinstance(count, bool)
                and isinstance(minimum, int)
                and count < minimum
            ):
                errors.append(
                    "platform machine constraint failed: "
                    f"min_plan_images={minimum}, got {count}"
                )
            if (
                isinstance(count, int)
                and not isinstance(count, bool)
                and isinstance(maximum, int)
                and count > maximum
            ):
                errors.append(
                    "platform machine constraint failed: "
                    f"max_plan_images={maximum}, got {count}"
                )

            if shots and isinstance(shots[0], dict):
                first_shot = shots[0]
                required_role = constraints.get("required_first_role")
                if (
                    isinstance(required_role, str)
                    and first_shot.get("role") != required_role
                ):
                    errors.append(
                        "platform machine constraint failed: first shot role must "
                        f"be {required_role!r}"
                    )
                first_modes = constraints.get("first_image_allowed_text_modes")
                first_mode = (
                    first_shot.get("text_strategy", {}).get("mode")
                    if isinstance(first_shot.get("text_strategy"), dict)
                    else None
                )
                if isinstance(first_modes, list) and first_mode not in first_modes:
                    errors.append(
                        "platform machine constraint failed: "
                        "first_image_allowed_text_modes="
                        f"{first_modes!r}, got {first_mode!r}"
                    )

            all_modes = constraints.get("all_images_allowed_text_modes")
            if isinstance(all_modes, list):
                for index, shot in enumerate(shots):
                    if not isinstance(shot, dict):
                        continue
                    text_strategy = shot.get("text_strategy")
                    mode = (
                        text_strategy.get("mode")
                        if isinstance(text_strategy, dict)
                        else None
                    )
                    if mode not in all_modes:
                        errors.append(
                            "platform machine constraint failed: "
                            "all_images_allowed_text_modes="
                            f"{all_modes!r}; shots[{index}] uses {mode!r}"
                        )

            required_first_slot = constraints.get("required_first_slot")
            slot_modes = constraints.get("slot_allowed_text_modes")
            slot_counts = constraints.get("slot_count_constraints")
            uses_slot_constraints = (
                isinstance(required_first_slot, str)
                or isinstance(slot_modes, dict)
                or isinstance(slot_counts, dict)
            )
            if uses_slot_constraints:
                observed_slots = []
                for index, shot in enumerate(shots):
                    if not isinstance(shot, dict):
                        continue
                    platform_slot = shot.get("platform_slot")
                    if not isinstance(platform_slot, str) or not platform_slot.strip():
                        errors.append(
                            f"shots[{index}].platform_slot is required by the "
                            "bundled profile's slot constraints"
                        )
                        continue
                    observed_slots.append(platform_slot)
                    if (
                        isinstance(slot_modes, dict)
                        and platform_slot in slot_modes
                    ):
                        text_strategy = shot.get("text_strategy")
                        mode = (
                            text_strategy.get("mode")
                            if isinstance(text_strategy, dict)
                            else None
                        )
                        allowed_modes = slot_modes[platform_slot]
                        if mode not in allowed_modes:
                            errors.append(
                                "platform slot machine constraint failed: "
                                f"slot_allowed_text_modes[{platform_slot!r}]="
                                f"{allowed_modes!r}; shots[{index}] uses {mode!r}"
                            )

                if (
                    isinstance(required_first_slot, str)
                    and shots
                    and isinstance(shots[0], dict)
                    and shots[0].get("platform_slot") != required_first_slot
                ):
                    errors.append(
                        "platform slot machine constraint failed: first shot "
                        f"platform_slot must be {required_first_slot!r}"
                    )

                if isinstance(slot_counts, dict):
                    for slot, limits in slot_counts.items():
                        if not isinstance(limits, dict):
                            continue
                        observed_count = observed_slots.count(slot)
                        minimum = limits.get("min")
                        maximum = limits.get("max")
                        if (
                            isinstance(minimum, int)
                            and observed_count < minimum
                        ):
                            errors.append(
                                "platform slot machine constraint failed: "
                                f"slot {slot!r} requires at least {minimum} images; "
                                f"got {observed_count}"
                            )
                        if (
                            isinstance(maximum, int)
                            and observed_count > maximum
                        ):
                            errors.append(
                                "platform slot machine constraint failed: "
                                f"slot {slot!r} allows at most {maximum} images; "
                                f"got {observed_count}"
                            )

    if len(shot_ids) != len(set(shot_ids)):
        errors.append("shots contain duplicate image_id values")
    if platform_ratio != "mixed" and len(ratios) > 1:
        errors.append(
            "shots.aspect_ratio contains multiple ratios; use "
            f"aspect_ratio='mixed' for a per-slot contract: {sorted(ratios)}"
        )
    if platform_ratio != "mixed" and ratios and platform_ratio not in ratios:
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
