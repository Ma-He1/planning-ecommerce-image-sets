#!/usr/bin/env python3
"""Validate the bundled ecommerce platform requirements registry."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ALLOWED_STATUSES = {
    "verified_public",
    "partial_public",
    "live_check_required",
}
ALLOWED_PLATFORM_TYPES = {
    "amazon",
    "global_marketplace",
    "domestic_marketplace",
    "social_commerce",
    "brand_site",
}
ALLOWED_FIRST_IMAGE_RULES = {
    "main_white",
    "main_product",
    "hero_kv",
    "editorial_cover",
    "custom",
}
ALLOWED_TEXT_MODES = {"none", "direct", "post_layout"}
ALLOWED_SOURCE_TYPES = {
    "official_public",
    "official_staff",
    "official_authenticated",
    "official_public_archive",
}
REQUIRED_PROFILE_FIELDS = {
    "id",
    "platform",
    "market",
    "platform_type",
    "verification_status",
    "scope",
    "first_image_rule",
    "overlay_language_default",
    "hard_rules",
    "recommendations",
    "conditional_rules",
    "publish_time_recheck",
    "sources",
    "official_hosts",
    "machine_constraints",
}
REQUIRED_MACHINE_CONSTRAINT_FIELDS = {
    "min_plan_images",
    "max_plan_images",
    "required_first_role",
    "first_image_allowed_text_modes",
    "all_images_allowed_text_modes",
    "source_rule_ids",
}
OPTIONAL_MACHINE_CONSTRAINT_FIELDS = {
    "required_first_slot",
    "slot_allowed_text_modes",
    "slot_count_constraints",
}


def non_empty_string(value, path, errors):
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")
        return False
    return True


def string_list(value, path, errors, *, allow_empty=True):
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    if not allow_empty and not value:
        errors.append(f"{path} must not be empty")
    for index, item in enumerate(value):
        non_empty_string(item, f"{path}[{index}]", errors)
    return value


def parse_iso_date(value, path, errors):
    if not non_empty_string(value, path, errors):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        errors.append(f"{path} must use YYYY-MM-DD")
        return None
    if parsed > date.today():
        errors.append(f"{path} cannot be in the future")
    return parsed


def host_is_allowed(hostname, official_hosts):
    if not isinstance(hostname, str):
        return False
    hostname = hostname.lower().rstrip(".")
    return any(
        hostname == allowed or hostname.endswith(f".{allowed}")
        for allowed in official_hosts
    )


def validate_source(source, path, official_hosts, errors):
    if not isinstance(source, dict):
        errors.append(f"{path} must be an object")
        return None
    for field in ("id", "title", "url", "source_type", "checked_on", "notes"):
        non_empty_string(source.get(field), f"{path}.{field}", errors)

    source_type = source.get("source_type")
    if source_type not in ALLOWED_SOURCE_TYPES:
        errors.append(f"{path}.source_type is invalid: {source_type!r}")

    url = source.get("url")
    if isinstance(url, str) and url.strip():
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{path}.url must be an absolute HTTPS URL")
        elif not host_is_allowed(parsed.hostname, official_hosts):
            errors.append(
                f"{path}.url host {parsed.hostname!r} is not listed in "
                "profile.official_hosts"
            )

    parse_iso_date(source.get("checked_on"), f"{path}.checked_on", errors)
    return source.get("id")


def validate_machine_constraints(
    constraints,
    path,
    *,
    first_image_rule,
    known_rule_ids,
    errors,
):
    if not isinstance(constraints, dict):
        errors.append(f"{path} must be an object")
        return
    missing = REQUIRED_MACHINE_CONSTRAINT_FIELDS - set(constraints)
    extra = set(constraints) - (
        REQUIRED_MACHINE_CONSTRAINT_FIELDS | OPTIONAL_MACHINE_CONSTRAINT_FIELDS
    )
    for field in sorted(missing):
        errors.append(f"{path}.{field} is required")
    if extra:
        errors.append(f"{path} contains unsupported fields: {sorted(extra)}")

    minimum = constraints.get("min_plan_images")
    maximum = constraints.get("max_plan_images")
    for field, value in (
        ("min_plan_images", minimum),
        ("max_plan_images", maximum),
    ):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 1
        ):
            errors.append(f"{path}.{field} must be null or a positive integer")
    if (
        isinstance(minimum, int)
        and not isinstance(minimum, bool)
        and isinstance(maximum, int)
        and not isinstance(maximum, bool)
        and minimum > maximum
    ):
        errors.append(f"{path}.min_plan_images cannot exceed max_plan_images")

    required_role = constraints.get("required_first_role")
    if required_role is not None and required_role not in ALLOWED_FIRST_IMAGE_RULES - {
        "custom"
    }:
        errors.append(
            f"{path}.required_first_role is invalid: {required_role!r}"
        )
    if first_image_rule != "custom" and required_role != first_image_rule:
        errors.append(
            f"{path}.required_first_role must match profile.first_image_rule"
        )

    for field in (
        "first_image_allowed_text_modes",
        "all_images_allowed_text_modes",
    ):
        modes = string_list(
            constraints.get(field), f"{path}.{field}", errors, allow_empty=False
        )
        unknown_modes = set(modes) - ALLOWED_TEXT_MODES
        if unknown_modes:
            errors.append(
                f"{path}.{field} contains invalid text modes: "
                f"{sorted(unknown_modes)}"
            )

    source_rule_ids = string_list(
        constraints.get("source_rule_ids"),
        f"{path}.source_rule_ids",
        errors,
        allow_empty=True,
    )
    unknown_rule_ids = set(source_rule_ids) - known_rule_ids
    if unknown_rule_ids:
        errors.append(
            f"{path}.source_rule_ids contains unknown rule IDs: "
            f"{sorted(unknown_rule_ids)}"
        )

    required_first_slot = constraints.get("required_first_slot")
    if required_first_slot is not None:
        non_empty_string(
            required_first_slot,
            f"{path}.required_first_slot",
            errors,
        )

    slot_modes = constraints.get("slot_allowed_text_modes")
    if slot_modes is not None:
        if not isinstance(slot_modes, dict):
            errors.append(f"{path}.slot_allowed_text_modes must be an object")
            slot_modes = {}
        for slot, modes in slot_modes.items():
            non_empty_string(
                slot,
                f"{path}.slot_allowed_text_modes key",
                errors,
            )
            checked_modes = string_list(
                modes,
                f"{path}.slot_allowed_text_modes[{slot!r}]",
                errors,
                allow_empty=False,
            )
            unknown_modes = set(checked_modes) - ALLOWED_TEXT_MODES
            if unknown_modes:
                errors.append(
                    f"{path}.slot_allowed_text_modes[{slot!r}] contains invalid "
                    f"text modes: {sorted(unknown_modes)}"
                )

    slot_counts = constraints.get("slot_count_constraints")
    if slot_counts is not None:
        if not isinstance(slot_counts, dict):
            errors.append(f"{path}.slot_count_constraints must be an object")
            slot_counts = {}
        for slot, limits in slot_counts.items():
            non_empty_string(
                slot,
                f"{path}.slot_count_constraints key",
                errors,
            )
            if not isinstance(limits, dict):
                errors.append(
                    f"{path}.slot_count_constraints[{slot!r}] must be an object"
                )
                continue
            if set(limits) != {"min", "max"}:
                errors.append(
                    f"{path}.slot_count_constraints[{slot!r}] must contain "
                    "exactly min and max"
                )
            minimum = limits.get("min")
            maximum = limits.get("max")
            for field, value in (("min", minimum), ("max", maximum)):
                if value is not None and (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value < 1
                ):
                    errors.append(
                        f"{path}.slot_count_constraints[{slot!r}].{field} "
                        "must be null or a positive integer"
                    )
            if (
                isinstance(minimum, int)
                and not isinstance(minimum, bool)
                and isinstance(maximum, int)
                and not isinstance(maximum, bool)
                and minimum > maximum
            ):
                errors.append(
                    f"{path}.slot_count_constraints[{slot!r}].min cannot "
                    "exceed max"
                )

    if isinstance(required_first_slot, str):
        known_slots = set(slot_modes or {}) | set(slot_counts or {})
        if required_first_slot not in known_slots:
            errors.append(
                f"{path}.required_first_slot must appear in a slot constraint"
            )


def validate_rule(rule, path, source_ids, errors, *, conditional=False):
    if not isinstance(rule, dict):
        errors.append(f"{path} must be an object")
        return None
    for field in ("id", "applies_to", "claim"):
        non_empty_string(rule.get(field), f"{path}.{field}", errors)
    if conditional:
        non_empty_string(rule.get("condition"), f"{path}.condition", errors)

    linked_sources = string_list(
        rule.get("source_ids"), f"{path}.source_ids", errors, allow_empty=False
    )
    unknown = set(linked_sources) - source_ids
    if unknown:
        errors.append(f"{path}.source_ids contains unknown IDs: {sorted(unknown)}")
    return rule.get("id")


def validate_profile(profile, index, errors):
    path = f"profiles[{index}]"
    if not isinstance(profile, dict):
        errors.append(f"{path} must be an object")
        return None
    for field in sorted(REQUIRED_PROFILE_FIELDS - set(profile)):
        errors.append(f"{path}.{field} is required")

    for field in (
        "id",
        "platform",
        "market",
        "scope",
        "overlay_language_default",
    ):
        non_empty_string(profile.get(field), f"{path}.{field}", errors)

    platform_type = profile.get("platform_type")
    if platform_type not in ALLOWED_PLATFORM_TYPES:
        errors.append(f"{path}.platform_type is invalid: {platform_type!r}")

    status = profile.get("verification_status")
    if status not in ALLOWED_STATUSES:
        errors.append(f"{path}.verification_status is invalid: {status!r}")

    first_rule = profile.get("first_image_rule")
    if first_rule not in ALLOWED_FIRST_IMAGE_RULES:
        errors.append(f"{path}.first_image_rule is invalid: {first_rule!r}")

    official_hosts = string_list(
        profile.get("official_hosts"),
        f"{path}.official_hosts",
        errors,
        allow_empty=False,
    )
    normalized_hosts = []
    for host_index, host in enumerate(official_hosts):
        if not isinstance(host, str):
            continue
        normalized = host.lower().rstrip(".")
        if (
            "://" in normalized
            or "/" in normalized
            or not normalized
            or normalized.startswith(".")
        ):
            errors.append(
                f"{path}.official_hosts[{host_index}] must be a hostname only"
            )
        normalized_hosts.append(normalized)
    if len(normalized_hosts) != len(set(normalized_hosts)):
        errors.append(f"{path}.official_hosts contains duplicates")

    sources = profile.get("sources")
    if not isinstance(sources, list):
        errors.append(f"{path}.sources must be an array")
        sources = []
    if not sources:
        errors.append(f"{path}.sources must not be empty")

    source_ids = []
    source_types = set()
    source_type_by_id = {}
    for source_index, source in enumerate(sources):
        source_id = validate_source(
            source,
            f"{path}.sources[{source_index}]",
            normalized_hosts,
            errors,
        )
        if source_id:
            source_ids.append(source_id)
        if isinstance(source, dict):
            source_types.add(source.get("source_type"))
            if source_id:
                source_type_by_id[source_id] = source.get("source_type")
    if len(source_ids) != len(set(source_ids)):
        errors.append(f"{path}.sources contains duplicate IDs")
    source_id_set = set(source_ids)

    rule_ids = []
    for field, conditional in (
        ("hard_rules", False),
        ("recommendations", False),
        ("conditional_rules", True),
    ):
        rules = profile.get(field)
        if not isinstance(rules, list):
            errors.append(f"{path}.{field} must be an array")
            continue
        for rule_index, rule in enumerate(rules):
            rule_id = validate_rule(
                rule,
                f"{path}.{field}[{rule_index}]",
                source_id_set,
                errors,
                conditional=conditional,
            )
            if rule_id:
                rule_ids.append(rule_id)
    if len(rule_ids) != len(set(rule_ids)):
        errors.append(f"{path} contains duplicate rule IDs")

    validate_machine_constraints(
        profile.get("machine_constraints"),
        f"{path}.machine_constraints",
        first_image_rule=first_rule,
        known_rule_ids=set(rule_ids),
        errors=errors,
    )

    hard_rules = profile.get("hard_rules")
    if isinstance(hard_rules, list):
        for rule_index, rule in enumerate(hard_rules):
            if not isinstance(rule, dict):
                continue
            linked_types = {
                source_type_by_id.get(source_id)
                for source_id in rule.get("source_ids", [])
            }
            if not linked_types & {"official_public", "official_staff"}:
                errors.append(
                    f"{path}.hard_rules[{rule_index}] hard rule requires current "
                    "public or official staff evidence"
                )
    recheck = string_list(
        profile.get("publish_time_recheck"),
        f"{path}.publish_time_recheck",
        errors,
        allow_empty=False,
    )
    if status == "verified_public":
        if not isinstance(hard_rules, list) or not hard_rules:
            errors.append(f"{path}.hard_rules must not be empty for verified_public")
        if not source_types & {"official_public", "official_staff"}:
            errors.append(
                f"{path} verified_public requires an official public or staff source"
            )
    elif status == "partial_public":
        if not recheck:
            errors.append(
                f"{path}.publish_time_recheck must not be empty for partial_public"
            )
    elif status == "live_check_required":
        if hard_rules != []:
            errors.append(
                f"{path}.hard_rules must be empty for live_check_required"
            )
        if not recheck:
            errors.append(
                f"{path}.publish_time_recheck must not be empty for live_check_required"
            )
        if "official_authenticated" not in source_types:
            errors.append(
                f"{path} live_check_required needs an official_authenticated source"
            )

    return profile.get("id")


def validate_registry(registry):
    errors = []
    if not isinstance(registry, dict):
        return ["root must be a JSON object"]
    if registry.get("schema_version") != "2.0":
        errors.append("schema_version must be '2.0'")
    parse_iso_date(registry.get("verified_on"), "verified_on", errors)

    policy = registry.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")

    profiles = registry.get("profiles")
    if not isinstance(profiles, list):
        errors.append("profiles must be an array")
        return errors
    if not profiles:
        errors.append("profiles must not be empty")
        return errors

    profile_ids = []
    for index, profile in enumerate(profiles):
        profile_id = validate_profile(profile, index, errors)
        if profile_id:
            profile_ids.append(profile_id)
    if len(profile_ids) != len(set(profile_ids)):
        errors.append("profiles contains duplicate IDs")
    return errors


def main(argv):
    if len(argv) != 2:
        print("Usage: validate_platform_rules.py REGISTRY.json", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        registry = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}")
        return 2
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        )
        return 1

    errors = validate_registry(registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"VALID: {len(registry['profiles'])} platform profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
