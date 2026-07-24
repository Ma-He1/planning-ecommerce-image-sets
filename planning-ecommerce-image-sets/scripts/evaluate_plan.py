#!/usr/bin/env python3
"""Evaluate ecommerce image-set plans against versioned validation cases."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


WEIGHTS = {"structure": 20, "platform_language": 15, "fact_safety": 20, "dynamic_planning": 15, "prompt_text_route": 15, "reference_execution": 10, "qa_recovery": 5}
LOCALE_EQUIVALENTS = {
    "zh-tw": {"zh-tw", "zh-hant", "zh-hant-tw"},
    "zh-cn": {"zh-cn", "zh-hans", "zh-hans-cn"},
}
DEFERRED_TOPIC_SYNONYMS = {
    "identity_reference": (
        "目标sku身份",
        "sku身份",
        "锁定商品身份",
        "正面商品图",
        "正面全件商品图",
    ),
    "packaging_reference": ("包装图", "吊牌", "成分标", "洗护标"),
    "wearing_view": (
        "fit_wearing",
        "fit wearing",
        "佩戴参考",
        "真实佩戴",
        "佩戴关系",
        "耳内贴合",
    ),
    "medical_efficacy": (
        "dermatitis_medical_claim",
        "dermatitis medical claim",
        "皮炎适应症",
        "疾病治疗",
        "治疗或治愈承诺",
    ),
    "charging_port": (
        "type_c_port",
        "type c port",
        "接口类型",
        "接口特写",
        "接口规格",
    ),
}
LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
ALLOWED_FIRST_IMAGE_RULES = {"main_white", "hero_kv", "editorial_cover", "custom"}
CHINESE_NEGATION_CUES = (
    "不得", "禁止", "不要", "避免", "不应", "不可", "不能", "严禁", "勿",
    "不暗示", "不出现", "不加入", "不使用",
)
ENGLISH_NEGATION_CUES = ("donot", "dont", "never", "avoid", "noclaim")
PROMPT_REFERENCE_CUES = (
    "参考图", "官方图", "开盒图", "原始图", "原图", "原始照片", "原始参考", "身份锚点",
    "商品依据", "产品依据", "身份依据", "商品身份", "商品图", "事实依据",
    "identity reference", "reference image", "source image", "product reference", "product identity",
)
PROMPT_COMPOSITION_CUES = (
    "居中", "偏左", "偏右", "左侧", "右侧", "上方", "下方", "左上", "右上", "左下", "右下", "占画面", "占高",
    "构图", "镜头", "主体", "前景", "后景", "近景", "画面",
    "center", "left", "right", "top", "bottom", "composition", "framing", "subject",
)
PROMPT_SPATIAL_CUES = (
    "居中", "偏左", "偏右", "左侧", "右侧", "上方", "下方", "左上", "右上", "左下", "右下",
    "占画面", "占高", "三分线", "前景", "后景", "近景",
    "center", "left", "right", "top", "bottom", "foreground", "background",
)
PROMPT_CONSTRAINT_CUES = (
    "不", "禁止", "避免", "保留", "不得", "不能", "勿",
    "do not", "don't", "never", "avoid", "preserve", "keep",
)


def _load_base_validator_module():
    path = Path(__file__).with_name("validate_plan.py")
    spec = importlib.util.spec_from_file_location("ecommerce_plan_base_validator", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load base validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE_VALIDATOR = _load_base_validator_module()
BASE_VALIDATE = BASE_VALIDATOR.validate


def _validate_common_expectations(expectations: Any) -> None:
    if not isinstance(expectations, dict):
        raise ValueError("expectations must be an object")
    required_strings = ("platform", "platform_type", "language", "ratio")
    for field in required_strings:
        if not isinstance(expectations.get(field), str) or not expectations[field].strip():
            raise ValueError(f"expectations.{field} must be a non-empty string")
    if not LOCALE_RE.fullmatch(expectations["language"]):
        raise ValueError("expectations.language must be a locale such as zh-TW")
    if expectations["platform_type"] not in BASE_VALIDATOR.ALLOWED_PLATFORM_TYPES:
        raise ValueError("expectations.platform_type is invalid")
    if expectations["ratio"] not in BASE_VALIDATOR.ALLOWED_RATIOS:
        raise ValueError("expectations.ratio is invalid")
    allowed_ratios = expectations.get("allowed_ratios", [expectations["ratio"]])
    if (
        not isinstance(allowed_ratios, list)
        or not allowed_ratios
        or any(ratio not in BASE_VALIDATOR.ALLOWED_RATIOS for ratio in allowed_ratios)
        or len(allowed_ratios) != len(set(allowed_ratios))
        or expectations["ratio"] not in allowed_ratios
    ):
        raise ValueError("expectations.allowed_ratios contains an invalid aspect ratio")
    for field in ("required_concepts", "forbidden_claims"):
        if not isinstance(expectations.get(field), list) or not all(isinstance(value, str) and value for value in expectations[field]):
            raise ValueError(f"expectations.{field} must be a string array")
    deferred_topics = expectations.get("deferred_topics")
    if not isinstance(deferred_topics, list):
        raise ValueError("expectations.deferred_topics must be an array")
    for topic in deferred_topics:
        if (
            not isinstance(topic, dict)
            or set(topic) != {"id", "terms"}
            or not isinstance(topic.get("id"), str)
            or not topic["id"].strip()
            or not isinstance(topic.get("terms"), list)
            or not topic["terms"]
            or not all(isinstance(term, str) and term.strip() for term in topic["terms"])
        ):
            raise ValueError("every deferred topic must contain only a non-empty id and non-empty string terms")
    topic_ids = [topic["id"] for topic in deferred_topics]
    if len(topic_ids) != len(set(topic_ids)):
        raise ValueError("expectations.deferred_topics ids must be unique")
    for field in ("require_reference_inputs", "require_platform_rule_provenance"):
        if not isinstance(expectations.get(field), bool):
            raise ValueError(f"expectations.{field} must be boolean")
    for field in ("ready_count_range", "prompt_length_range"):
        value = expectations.get(field)
        if not isinstance(value, dict) or not all(isinstance(value.get(key), int) and not isinstance(value[key], bool) for key in ("min", "max")) or value["min"] > value["max"]:
            raise ValueError(f"expectations.{field} must be an ordered integer range")
    if expectations.get("first_shot_role") not in BASE_VALIDATOR.ALLOWED_ROLES:
        raise ValueError("expectations.first_shot_role is invalid")
    if expectations.get("first_image_rule") not in ALLOWED_FIRST_IMAGE_RULES:
        raise ValueError("expectations.first_image_rule is invalid")
    allowed_first_image_rules = expectations.get("allowed_first_image_rules")
    if (
        not isinstance(allowed_first_image_rules, list)
        or not allowed_first_image_rules
        or any(rule not in ALLOWED_FIRST_IMAGE_RULES for rule in allowed_first_image_rules)
        or len(allowed_first_image_rules) != len(set(allowed_first_image_rules))
        or expectations["first_image_rule"] not in allowed_first_image_rules
    ):
        raise ValueError("expectations.allowed_first_image_rules contains an invalid first-image rule")
    if "platform_name_terms" in expectations:
        raise ValueError("expectations.platform_name_terms is obsolete; use platform_name_term_groups")
    platform_name_term_groups = expectations.get("platform_name_term_groups")
    if expectations["platform_type"] == "brand_site":
        if not isinstance(platform_name_term_groups, list) or not platform_name_term_groups:
            raise ValueError("brand-site expectations require platform_name_term_groups")
        group_ids = []
        for group in platform_name_term_groups:
            if (
                not isinstance(group, dict)
                or set(group) != {"id", "terms"}
                or not isinstance(group.get("id"), str)
                or not group["id"].strip()
                or not isinstance(group.get("terms"), list)
                or not group["terms"]
                or not all(isinstance(term, str) and term.strip() for term in group["terms"])
            ):
                raise ValueError("every platform-name term group must contain only a non-empty id and non-empty string terms")
            group_ids.append(group["id"])
        if len(group_ids) != len(set(group_ids)) or set(group_ids) != {"brand", "official_site"}:
            raise ValueError("brand-site platform-name term groups must be unique brand and official_site groups")
    elif platform_name_term_groups is not None:
        raise ValueError("platform_name_term_groups is only valid for brand-site expectations")
    text_modes = expectations.get("allowed_text_modes")
    if not isinstance(text_modes, list) or not text_modes or any(mode not in BASE_VALIDATOR.ALLOWED_TEXT_MODES for mode in text_modes):
        raise ValueError("expectations.allowed_text_modes contains an invalid text mode")
    if expectations["platform_type"] == "amazon" and (
        expectations["ratio"] != "1:1"
        or expectations["first_shot_role"] != "main_white"
        or expectations["first_image_rule"] != "main_white"
        or set(allowed_first_image_rules) != {"main_white"}
        or set(text_modes) != {"none"}
    ):
        raise ValueError("Amazon expectations require a 1:1 main_white first image with text mode none")
    if set(expectations["required_concepts"]) & set(topic_ids):
        raise ValueError("required_concepts and deferred_topics must not overlap")
    forbidden_count = expectations.get("forbid_exact_user_count")
    if forbidden_count is not None and (not isinstance(forbidden_count, int) or isinstance(forbidden_count, bool) or forbidden_count < 1):
        raise ValueError("expectations.forbid_exact_user_count must be a positive integer")
    ready_range = expectations["ready_count_range"]
    if forbidden_count is not None and ready_range["min"] <= forbidden_count <= ready_range["max"]:
        raise ValueError("forbid_exact_user_count must be outside ready_count_range")


def _validate_case(case: Any) -> None:
    if not isinstance(case, dict):
        raise ValueError("every fixture case must be an object")
    for field in ("id", "title", "product_category", "brief"):
        if not isinstance(case.get(field), str) or not case[field].strip():
            raise ValueError(f"case.{field} must be a non-empty string")
    if not isinstance(case.get("image_paths"), list) or not all(isinstance(path, str) and path for path in case["image_paths"]):
        raise ValueError("case.image_paths must be a string array")
    if not isinstance(case.get("pressure_tags"), list) or not case["pressure_tags"] or not all(isinstance(tag, str) and tag for tag in case["pressure_tags"]):
        raise ValueError("case.pressure_tags must be a non-empty string array")
    expectations = case.get("expectations")
    if not isinstance(expectations, dict):
        raise ValueError("case.expectations must be an object")
    if expectations.get("output_kind") == "multi_set_manifest":
        if expectations.get("set_strategy") != "split" or not isinstance(expectations.get("sets"), list) or len(expectations["sets"]) < 2:
            raise ValueError("multi_set_manifest expectations must contain two split sets")
        for expected_set in expectations["sets"]:
            _validate_common_expectations(expected_set)
            if not expected_set["require_reference_inputs"]:
                raise ValueError("multi-set executable cases must require reference inputs")
        return
    _validate_common_expectations(expectations)
    if expectations.get("expect_blocked"):
        if case["image_paths"]:
            raise ValueError("blocked case must not provide usable image paths")
        requirements = expectations.get("blocked_requirements")
        if not isinstance(requirements, list) or not requirements or not all(isinstance(value, str) and value for value in requirements):
            raise ValueError("blocked case must define blocked_requirements")
    reference_exception_ok = (
        expectations.get("expect_blocked") is True
        and case["image_paths"] == []
        and expectations["ready_count_range"] == {"min": 0, "max": 0}
    )
    if not expectations["require_reference_inputs"] and not reference_exception_ok:
        raise ValueError("require_reference_inputs=false is only valid for a zero-count no-image blocked case")


def load_cases(path: Path) -> dict[str, dict]:
    """Load and validate a versioned fixture, indexed by stable case ID."""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("version"), str) or not isinstance(payload.get("cases"), list):
        raise ValueError("fixture must be an object with version and cases")
    indexed: dict[str, dict] = {}
    for case in payload["cases"]:
        _validate_case(case)
        if case["id"] in indexed:
            raise ValueError(f"duplicate fixture case id: {case['id']}")
        indexed[case["id"]] = case
    return indexed


def _append_error(errors: list[str], message: str) -> None:
    if message not in errors:
        errors.append(message)


def _result(case_id: str, category_scores: dict[str, int], errors: list[str], fatal_errors: list[str]) -> dict:
    for fatal in fatal_errors:
        _append_error(errors, fatal)
    score = sum(category_scores.values())
    return {"case_id": case_id, "score": score, "passed": score >= 90 and not fatal_errors, "fatal_errors": fatal_errors, "errors": errors, "category_scores": category_scores}


def _shot_text(shot: dict[str, Any]) -> str:
    strategy = shot.get("text_strategy") if isinstance(shot.get("text_strategy"), dict) else {}
    exact_copy = strategy.get("exact_copy") if isinstance(strategy.get("exact_copy"), list) else []
    values = [shot.get("content_message"), shot.get("buyer_question_answered"), shot.get("generation_prompt"), *exact_copy]
    return " ".join(value for value in values if isinstance(value, str))


def _normalize_claim_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _claim_in_positive_context(value: str, claim: str) -> bool:
    """Return true when a claim occurs outside a nearby safety-negation cue."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    compact_chars: list[str] = []
    source_offsets: list[int] = []
    for index, character in enumerate(normalized):
        if character.isalnum():
            compact_chars.append(character)
            source_offsets.append(index)
    compact = "".join(compact_chars)
    target = _normalize_claim_text(claim)
    if not target:
        return False
    start = compact.find(target)
    while start >= 0:
        raw_start = source_offsets[start]
        statement_prefix = re.split(
            r"[。！？!?；;\n\r]|但是|然而|但|却|并且|并|同时|以及|\bbut\b|\bhowever\b|\band\b",
            normalized[:raw_start],
        )[-1]
        compact_prefix = _normalize_claim_text(statement_prefix)
        chinese_negated = any(cue in compact_prefix for cue in CHINESE_NEGATION_CUES)
        english_negated = any(cue in compact_prefix for cue in ENGLISH_NEGATION_CUES)
        if not chinese_negated and not english_negated:
            return True
        start = compact.find(target, start + 1)
    return False


def _platform_name_matches(expectations: dict[str, Any], actual_name: Any) -> bool:
    if not isinstance(actual_name, str) or not actual_name.strip():
        return False
    actual = _normalize_claim_text(actual_name)
    known_other_platforms = {"amazonus", "amazonde", "tiktokus", "淘宝", "小红书"}
    expected = _normalize_claim_text(expectations["platform"])
    if actual in known_other_platforms and actual != expected:
        return False
    groups = expectations.get("platform_name_term_groups")
    if isinstance(groups, list):
        return all(any(_normalize_claim_text(term) in actual for term in group["terms"]) for group in groups)
    return actual == expected


def _has_platform_provenance(platform: dict[str, Any]) -> bool:
    if not platform.get("rule_checked_at"):
        return False
    for field in ("hard_rules", "creative_guidance", "rule_sources"):
        if not isinstance(platform.get(field), list) or not platform[field]:
            return False
    return all(isinstance(source, dict) and all(source.get(field) for field in ("title", "url", "source_type")) for source in platform["rule_sources"])


def _prompt_has_minimum_execution_cues(prompt: str) -> bool:
    normalized = unicodedata.normalize("NFKC", prompt).casefold()
    has_reference = any(cue in normalized for cue in PROMPT_REFERENCE_CUES) or bool(
        re.search(r"\.(?:png|jpe?g|webp)\b", normalized)
    )
    has_composition = any(cue in normalized for cue in PROMPT_SPATIAL_CUES)
    has_constraint = any(cue in normalized for cue in PROMPT_CONSTRAINT_CUES)
    chinese_chars = re.findall(r"[\u3400-\u9fff]", normalized)
    unique_chinese = len(set(chinese_chars))
    dominant_ratio = (
        max((chinese_chars.count(character) for character in set(chinese_chars)), default=0)
        / len(chinese_chars)
        if chinese_chars
        else 1.0
    )
    clause_marks = len(re.findall(r"[，。；;]", normalized))
    has_information_density = (
        len(prompt.strip()) >= 100
        and len(chinese_chars) >= 60
        and unique_chinese >= 30
        and dominant_ratio <= 0.20
        and clause_marks >= 3
    )
    return (
        has_reference
        and has_composition
        and has_constraint
        and has_information_density
    )


def _required_concept_covered(concept: str, shots: list[Any]) -> bool:
    valid_shots = [shot for shot in shots if isinstance(shot, dict)]
    if concept == "product_identity":
        return any(shot.get("role") in {"hero_kv", "main_white"} and shot.get("content_message") and shot.get("buyer_question_answered") for shot in valid_shots)
    if concept == "usage_scene":
        return any(shot.get("role") == "usage_scene" for shot in valid_shots)
    keywords = {"top_fill": ("top fill", "top-fill", "顶注水", "顶部加水", "从顶部加水", "上方加水")}
    expected_keywords = keywords.get(concept, (concept.replace("_", " "), concept))
    return any(any(keyword.lower() in _shot_text(shot).lower() for keyword in expected_keywords) for shot in valid_shots)


def _topic_terms(topic: dict[str, Any]) -> list[str]:
    terms = topic.get("terms") if isinstance(topic.get("terms"), list) else []
    topic_id = topic.get("id") if isinstance(topic.get("id"), str) else ""
    return [*terms, *DEFERRED_TOPIC_SYNONYMS.get(topic_id, ())]


def _deferred_topic_covered(topic: dict[str, Any], modules: list[Any]) -> bool:
    terms = _topic_terms(topic)
    for module in modules:
        if not isinstance(module, dict):
            continue
        module_id = module.get("module_id")
        why_deferred = module.get("why_deferred")
        required_inputs = module.get("required_inputs")
        if (
            not isinstance(module_id, str)
            or not module_id.strip()
            or not isinstance(why_deferred, str)
            or not why_deferred.strip()
            or not isinstance(required_inputs, list)
            or not required_inputs
            or not all(isinstance(value, str) and value.strip() for value in required_inputs)
        ):
            continue
        combined = _normalize_claim_text(" ".join([module_id, why_deferred, *required_inputs]))
        if any(_normalize_claim_text(term) in combined for term in terms):
            return True
    return False


def _text_covers_topic(topic: dict[str, Any], values: list[Any]) -> bool:
    combined = _normalize_claim_text(
        " ".join(value for value in values if isinstance(value, str))
    )
    return any(
        _normalize_claim_text(term) in combined
        for term in _topic_terms(topic)
        if isinstance(term, str) and term.strip()
    )


def _locale_matches(expected: Any, actual: Any) -> bool:
    if not isinstance(expected, str) or not isinstance(actual, str):
        return False
    expected_key = expected.replace("_", "-").casefold()
    actual_key = actual.replace("_", "-").casefold()
    if expected_key == actual_key:
        return True
    return actual_key in LOCALE_EQUIVALENTS.get(expected_key, {expected_key})


def _ratio_matches(expectations: dict[str, Any], actual: Any) -> bool:
    allowed = expectations.get("allowed_ratios", [expectations.get("ratio")])
    return isinstance(actual, str) and actual in allowed


def _topic_for_requirement(expectations: dict[str, Any], requirement: str) -> dict[str, Any]:
    normalized_requirement = _normalize_claim_text(requirement)
    for topic in expectations.get("deferred_topics", []):
        candidates = [topic.get("id", ""), *topic.get("terms", [])]
        if any(normalized_requirement in _normalize_claim_text(candidate) or _normalize_claim_text(candidate) in normalized_requirement for candidate in candidates):
            return topic
    return {"id": requirement.replace(" ", "_"), "terms": [requirement, requirement.replace(" ", "_")]}


def _blocked_contract_errors(expectations: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    errors = []
    if plan.get("overall_status") != "blocked" or plan.get("shots") != [] or plan.get("ready_now") != [] or plan.get("recommended_image_count") != 0:
        errors.append("blocked plan must use status=blocked, zero count, and empty shots/ready_now")
    needs = plan.get("needs_more_info") if isinstance(plan.get("needs_more_info"), list) else []
    modules = plan.get("deferred_modules") if isinstance(plan.get("deferred_modules"), list) else []
    for requirement in expectations.get("blocked_requirements", []):
        topic = _topic_for_requirement(expectations, requirement)
        if not _text_covers_topic(topic, needs) or not _deferred_topic_covered(topic, modules):
            errors.append(f"blocked plan must defer and request {requirement}")
    return errors


def _evaluate_single(case: dict[str, Any], plan: Any) -> dict:
    case_id = case.get("id", "")
    category_scores = {name: 0 for name in WEIGHTS}
    errors: list[str] = []
    fatal_errors: list[str] = []
    if not isinstance(plan, dict):
        return _result(case_id, category_scores, ["plan must be an object"], ["plan must be an object"])
    expectations = case["expectations"]
    blocked_expected = bool(expectations.get("expect_blocked"))
    base_errors = BASE_VALIDATE(plan)
    blocked_errors = _blocked_contract_errors(expectations, plan) if blocked_expected else []
    if base_errors:
        for error in base_errors:
            _append_error(errors, f"base validator: {error}")
    else:
        category_scores["structure"] = WEIGHTS["structure"]
    for error in base_errors:
        if "Amazon first shot" in error or "shots.aspect_ratio must be unified" in error:
            fatal_errors.append(error)

    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    modules = plan.get("deferred_modules") if isinstance(plan.get("deferred_modules"), list) else []
    platform = plan.get("platform_decision") if isinstance(plan.get("platform_decision"), dict) else {}
    language = plan.get("language_decision") if isinstance(plan.get("language_decision"), dict) else {}
    if language.get("packaging_text_policy") != "preserve_original":
        fatal_errors.append("packaging_text_policy must be preserve_original")

    platform_ok = (
        platform.get("platform_type") == expectations["platform_type"]
        and _platform_name_matches(expectations, platform.get("platform_name"))
        and bool(platform.get("decision_source"))
        and _ratio_matches(expectations, platform.get("aspect_ratio"))
        and _locale_matches(expectations["language"], language.get("overlay_language"))
    )
    if platform_ok and (not expectations["require_platform_rule_provenance"] or _has_platform_provenance(platform)):
        category_scores["platform_language"] = WEIGHTS["platform_language"]
    else:
        _append_error(errors, "platform/language decision or platform-rule provenance is incomplete")

    for shot in shots:
        if isinstance(shot, dict):
            strategy = shot.get("text_strategy") if isinstance(shot.get("text_strategy"), dict) else {}
            exact_copy = strategy.get("exact_copy") if isinstance(strategy.get("exact_copy"), list) else []
            for claim in expectations["forbidden_claims"]:
                instruction_claim = any(
                    isinstance(shot.get(field), str) and _claim_in_positive_context(shot[field], claim)
                    for field in ("content_message", "buyer_question_answered", "generation_prompt")
                )
                consumer_copy_claim = any(
                    isinstance(value, str) and _normalize_claim_text(claim) in _normalize_claim_text(value)
                    for value in exact_copy
                )
                if instruction_claim or consumer_copy_claim:
                    _append_error(fatal_errors, f"forbidden unverified claim in executable shot: {claim}")
    if not any("forbidden unverified claim" in error for error in fatal_errors):
        category_scores["fact_safety"] = WEIGHTS["fact_safety"]

    ready = plan.get("ready_now") if isinstance(plan.get("ready_now"), list) else []
    range_spec = expectations["ready_count_range"]
    count_ok = range_spec["min"] <= len(ready) <= range_spec["max"]
    forbidden_count = expectations.get("forbid_exact_user_count")
    if forbidden_count is not None and plan.get("recommended_image_count") == forbidden_count:
        fatal_errors.append(f"fixed user count {forbidden_count} was accepted instead of evidence-based dynamic planning")
    first = shots[0] if shots and isinstance(shots[0], dict) else {}
    strategy = first.get("text_strategy") if isinstance(first.get("text_strategy"), dict) else {}
    first_ok = (
        first.get("role") == expectations["first_shot_role"]
        and strategy.get("mode") in expectations["allowed_text_modes"]
        and platform.get("first_image_rule") in expectations["allowed_first_image_rules"]
    )
    coverage_ok = all(_required_concept_covered(concept, shots) for concept in expectations["required_concepts"]) and all(
        _deferred_topic_covered(topic, modules) for topic in expectations["deferred_topics"]
    )
    blocked_contract_valid = blocked_expected and not blocked_errors and not base_errors
    if blocked_expected:
        if blocked_contract_valid:
            category_scores["dynamic_planning"] = WEIGHTS["dynamic_planning"]
        else:
            errors.extend(blocked_errors)
    elif count_ok and first_ok and coverage_ok:
        category_scores["dynamic_planning"] = WEIGHTS["dynamic_planning"]
    else:
        _append_error(errors, "ready-count, first-shot rule, or required/deferred contract coverage does not match the case")

    prompt_range = expectations["prompt_length_range"]
    prompts_ok = bool(shots) and all(
        isinstance(shot, dict)
        and isinstance(shot.get("generation_prompt"), str)
        and prompt_range["min"] <= len(shot["generation_prompt"]) <= prompt_range["max"]
        and _prompt_has_minimum_execution_cues(shot["generation_prompt"])
        for shot in shots
    )
    if blocked_contract_valid or prompts_ok:
        category_scores["prompt_text_route"] = WEIGHTS["prompt_text_route"]
    else:
        _append_error(errors, "one or more executable prompts are outside the case prompt length range or lack minimum execution cues")

    references_ok = bool(shots) and all(isinstance(shot, dict) and isinstance(shot.get("reference_inputs"), list) and shot["reference_inputs"] and all(isinstance(reference, dict) and reference.get("path") and reference.get("purpose") for reference in shot["reference_inputs"]) for shot in shots)
    if blocked_expected:
        if blocked_contract_valid:
            category_scores["reference_execution"] = WEIGHTS["reference_execution"]
    elif not expectations["require_reference_inputs"] or references_ok:
        category_scores["reference_execution"] = WEIGHTS["reference_execution"]
    else:
        fatal_errors.append("executable shots require non-empty reference_inputs with path and purpose")

    qa_ok = all(isinstance(shot, dict) and isinstance(shot.get("qa_checks"), list) and shot["qa_checks"] and isinstance(shot.get("negative_constraints"), list) and shot["negative_constraints"] for shot in shots) and isinstance(plan.get("needs_more_info"), list) and isinstance(plan.get("overall_risks"), list)
    if blocked_contract_valid or (bool(shots) and qa_ok):
        category_scores["qa_recovery"] = WEIGHTS["qa_recovery"]
    else:
        _append_error(errors, "qa/recovery fields are incomplete")
    return _result(case_id, category_scores, errors, fatal_errors)


def _evaluate_multi(case: dict[str, Any], plan: Any) -> dict:
    category_scores = {name: 0 for name in WEIGHTS}
    errors: list[str] = []
    fatal_errors: list[str] = []
    expectations = case["expectations"]
    if not isinstance(plan, dict) or plan.get("output_kind") != "multi_set_manifest" or plan.get("set_strategy") != "split" or not isinstance(plan.get("sets"), list) or len(plan["sets"]) != len(expectations["sets"]):
        return _result(case["id"], category_scores, ["multi-set manifest must contain the required split sets"], ["multi-set manifest must contain the required split sets"])
    manifest_errors = BASE_VALIDATE(plan)
    if manifest_errors:
        messages = [f"base validator: {error}" for error in manifest_errors]
        return _result(case["id"], category_scores, messages, messages)

    results = []
    unmatched = list(plan["sets"])
    for index, expected_set in enumerate(expectations["sets"]):
        matching = []
        for actual_set in unmatched:
            platform = actual_set.get("platform_decision") if isinstance(actual_set, dict) else None
            if (
                isinstance(platform, dict)
                and platform.get("platform_type") == expected_set["platform_type"]
                and _platform_name_matches(expected_set, platform.get("platform_name"))
            ):
                matching.append(actual_set)
        if len(matching) != 1:
            message = "multi-set manifest must contain exactly one set for each expected platform"
            return _result(case["id"], category_scores, [message], [message])
        actual_set = matching[0]
        unmatched.remove(actual_set)
        subcase = {**case, "id": f"{case['id']}:{index + 1}", "expectations": expected_set}
        results.append(_evaluate_single(subcase, actual_set))
    for result in results:
        errors.extend(result["errors"])
        fatal_errors.extend(result["fatal_errors"])
    for category in WEIGHTS:
        category_scores[category] = min(result["category_scores"][category] for result in results)
    return _result(case["id"], category_scores, errors, fatal_errors)


def evaluate(case: dict, plan: dict) -> dict:
    """Return the required score contract for a single plan or multi-set manifest."""
    if not isinstance(case, dict) or not isinstance(case.get("expectations"), dict):
        raise ValueError("case must be a validated fixture object")
    if case["expectations"].get("output_kind") == "multi_set_manifest":
        return _evaluate_multi(case, plan)
    return _evaluate_single(case, plan)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate an ecommerce image-set plan")
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.cases)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: unable to load cases: {exc}", file=sys.stderr)
        return 2
    if args.case_id not in cases:
        print(f"ERROR: unknown case id: {args.case_id}", file=sys.stderr)
        return 2
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        print(f"ERROR: plan file not found: {exc.filename}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"invalid plan JSON: {exc}"}, ensure_ascii=False, sort_keys=True))
        return 1
    result = evaluate(cases[args.case_id], plan)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if args.output:
        try:
            args.output.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: unable to write output: {exc}", file=sys.stderr)
            return 2
    print(payload)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
