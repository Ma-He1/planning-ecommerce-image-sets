# 规划输出合同

## 可读摘要

在 JSON 前向用户说明：

1. 目标平台、市场、画幅和判断依据
2. 原始素材能够可靠支持与不能支持的内容
3. 当前可执行图片数量及选择理由
4. 每张图的任务、表达方法和参考图分配
5. 暂缓模块及其所需补充资料

## 单平台顶层结构

保存为 UTF-8 JSON，不写注释：

```json
{
  "version": "2.0",
  "overall_status": "ready | partially_ready | blocked",
  "platform_decision": {},
  "language_decision": {},
  "input_assessment": {},
  "facts": {},
  "buyer_questions": [],
  "visual_system": {},
  "recommended_image_count": 0,
  "count_reason": "",
  "shots": [],
  "deferred_modules": [],
  "ready_now": [],
  "needs_more_info": [],
  "overall_risks": []
}
```

所有新计划使用 `version: "2.0"`。

## 多平台结构

同一商品面向多个平台时，使用：

```json
{
  "output_kind": "multi_set_manifest",
  "set_strategy": "split",
  "sets": []
}
```

- `sets` 至少包含两套完整单平台计划。
- 每套独立记录平台、市场、语言、画幅、首图、文案、图片数量、风险和暂缓项。
- 各套可以复用商品事实，但不能共用一个混合的 `shots`。

## 平台字段

`platform_decision` 包含：

- `platform_type`：`amazon | domestic_marketplace | social_commerce | brand_site | portfolio | custom`
- `platform_name`：目标平台或展示环境
- `decision_source`：`explicit | inferred | default`
- `confidence`：`high | medium | low`
- `first_image_rule`：`main_white | hero_kv | editorial_cover | custom`
- `aspect_ratio`：`1:1 | 3:4 | 4:5 | 9:16 | 4:3 | 16:9`
- `rule_checked_at`：实际核验时间，使用 ISO 8601 日期或日期时间
- `hard_rules`：当前来源确认的强制约束
- `creative_guidance`：非强制的转化与视觉建议
- `rule_sources`：每项包含 `title`、`url`、`source_type`

默认作品集使用 `platform_type: "portfolio"` 和 `decision_source: "default"`；画幅根据商品形态与展示用途选择。

## 语言字段

`language_decision` 包含：

- `planning_language`：`zh-CN`
- `prompt_language`：`zh-CN`
- `overlay_language`：目标市场语言代码
- `packaging_text_policy`：`preserve_original`

## 事实账本

`facts` 包含：

- `visible_facts`
- `user_confirmed_facts`
- `official_confirmed_facts`
- `uncertain_observations`
- `missing_critical_info`
- `creative_assumptions`

前三类可以支撑确定性卖点。其余内容只能用于风险、补资料要求或不改变产品事实的创意方向。

## 每张图字段

每个 `shots[]` 包含：

- `image_id`：两位序号加角色标识
- `role`：`hero_kv | main_white | editorial_cover | selling_points | specification | feature_detail | material_macro | scale_capacity | package_contents | comparison | usage_scene`
- `priority`：`required | recommended | optional`
- `execution_action`：见提示词与生成路由
- `reference_risk`：`low | medium`
- `content_message`：本图唯一核心信息
- `buyer_question_answered`：本图回答的问题
- `aspect_ratio`：与本套合同一致
- `reference_inputs`：原始参考路径及用途
- `generation_prompt`：中文可执行提示词
- `text_strategy`：文字生成或后期排版策略
- `negative_constraints`：禁止生成或改动的内容
- `qa_checks`：可观察验收标准

`execution_action` 允许：

- `reuse`
- `clean_up`
- `reference_generate`
- `scene_composite`
- `generate_then_layout`

`text_strategy.mode` 允许：

- `none`：不新增图内文字，`exact_copy` 为空
- `direct`：直接生成极短文字，`exact_copy` 非空
- `post_layout`：生成无字底图后排版，`exact_copy` 非空

每项 `reference_inputs[]` 必须包含非空 `path` 与 `purpose`。无法支持本图身份、角度或细节的参考不能用于凑字段。

## 数量与状态

必须满足：

```text
recommended_image_count == shots.length == ready_now.length
ready_now == shots[].image_id（顺序一致）
deferred_modules 与 ready_now 无交集
同一套 shots 使用统一 aspect_ratio
```

`deferred_modules[]` 包含：

- `module_id`
- `why_deferred`
- `required_inputs`
- `blocking_scope`：`module | whole_product`

状态规则：

- `ready`：存在可执行图片，没有暂缓模块。
- `partially_ready`：存在可执行图片，且至少有一个 `module` 暂缓项。
- `blocked`：没有可执行图片，至少有一个 `whole_product` 暂缓项，并提供 `needs_more_info`。
- `whole_product` 暂缓项不能与可执行图片并存。

## 验证

将 `<SKILL_DIR>` 替换为 Skill 目录：

```powershell
python <SKILL_DIR>/scripts/validate_plan.py <plan.json>
```
