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
  "version": "3.0",
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

所有新计划使用 `version: "3.0"`。这是平台规则合同升级后的新主版本；旧 `2.0` 计划需补齐 `platform_profile_id`、`verification_status`、与 `hard_rules` 一一对应的 `hard_rule_ids`、`publish_time_recheck` 与可追溯来源后再验证。

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

- `platform_type`：`amazon | global_marketplace | domestic_marketplace | social_commerce | brand_site | portfolio | custom`
- `platform_name`：目标平台或展示环境
- `decision_source`：`explicit | inferred | default`
- `confidence`：`high | medium | low`
- `first_image_rule`：`main_white | main_product | hero_kv | editorial_cover | custom`
- `aspect_ratio`：统一套图填写正整数比例（如 `1:1`、`4:5`、`9:16`、`5:4`）；发布槽位确实需要不同比例时填写 `mixed`
- `rule_checked_at`：实际核验时间，使用 ISO 8601 日期或日期时间
- `platform_profile_id`：来自 `platform-requirements.json` 的画像 ID；作品集或自定义合同使用清楚的项目 ID
- `verification_status`：`verified_current | partially_verified | live_check_required | not_applicable`
- `hard_rules`：当前来源确认的强制约束
- `hard_rule_ids`：与 `hard_rules` 一一对应且不重复的稳定规则 ID；内置画像必须使用 `platform-requirements.json` 中的 ID 与原始声明，`verified_current` 计划必须完整继承该画像全部通用硬规则；自定义项目使用项目内唯一 ID
- `creative_guidance`：非强制的转化与视觉建议
- `publish_time_recheck`：发布前仍需在站点、类目、账号或模板中复核的事项
- `rule_sources`：每项包含 `title`、`url`、`source_type`
- `profile_override_reason`：可选审计说明，仅用于提出规则库更新，不会在计划验证阶段自动覆盖内置状态、硬规则或首图合同

`source_type` 允许：

- `official_public`：平台当前公开规则、帮助中心或开发者文档
- `official_public_archive`：平台官方历史页面、旧课件或归档文档；只能支持部分或历史证据，不能单独证明当前通用硬规则
- `official_staff`：可确认身份的平台官方员工公告
- `official_authenticated`：需要登录的官方规则中心或商家后台
- `live_platform_ui`：本次实际查看的当前发布界面
- `user_contract`：用户提供的平台合同、模板或书面要求
- `project_contract`：品牌官网、作品集或内部项目的明确合同
- `skill_local`：Skill 本地路由说明；只能辅助查找，不能单独证明市场平台硬规则

市场平台以及已知品牌官网画像的 `verified_current`、`partially_verified` 和 `live_check_required` 至少需要可追溯的平台官方来源。`verified_current` 必须有非空且逐项绑定的 `hard_rules` 与 `hard_rule_ids`；`partially_verified` 与 `live_check_required` 必须有非空 `publish_time_recheck`；`live_check_required` 在完成后台核验前保持 `hard_rules: []` 和 `hard_rule_ids: []`。`official_public_archive` 只能用于 `partially_verified` 的历史或局部证据，并强制保留发布前复核，不能单独支撑 `verified_current`。

已知市场平台和已知品牌官网画像的 `platform_profile_id` 必须存在于内置规则库，且 `platform_type` 与画像一致；例如把 Shopify 改写成任意自定义官网画像会被拒绝。计划可以比内置画像更保守。`user_contract` 可以增加项目要求，但不能删除、放宽或覆盖平台官方硬规则，也不能把计划提升为比内置画像更确定的状态。`live_platform_ui` 也是审计来源，不是自动覆盖权限；平台确有变化时，先更新并复核规则库。若内置画像的 `first_image_rule` 不是 `custom`，计划必须继承该角色。

规则库的 `machine_constraints` 是验证器能够结构化检查的最小子集，可约束计划总张数、发布槽位张数、首图角色、首图或特定槽位的文字模式，并通过 `source_rule_ids` 关联来源规则。验证器通过不等于全部平台规则通过：商品与文案的语义真实性、条件是否成立、类目规则、视觉质量和发布后台状态仍需人工或发布前 QA；Amazon 逼真 AI 生成人物所需的 XMP 元数据也不在当前计划验证器的自动检查范围内。

默认作品集使用 `platform_type: "portfolio"`、`decision_source: "default"`、`verification_status: "not_applicable"`；画幅根据商品形态与展示用途选择，规则来源写入项目合同，不冒充平台要求。`not_applicable` 表示“不适用市场平台核验”，不表示项目没有硬约束；作品集或自定义项目可以在 `hard_rules` 中记录模板、安全区和交付格式，并在 `hard_rule_ids` 中给出一一对应的项目内稳定 ID。

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
- `role`：`hero_kv | main_white | main_product | editorial_cover | selling_points | specification | feature_detail | material_macro | scale_capacity | package_contents | comparison | usage_scene`
- `priority`：`required | recommended | optional`
- `execution_action`：见提示词与生成路由
- `reference_risk`：`low | medium`
- `content_message`：本图唯一核心信息
- `buyer_question_answered`：本图回答的问题
- `aspect_ratio`：正整数比例；当平台合同为 `mixed` 时按当前图片槽位填写
- `platform_slot`：画像定义槽位约束时必填，例如 `main_carousel`、`main_image` 或 `detail_image`；用来确保主图禁文案与主图张数不会被详情图绕过
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
platform_decision.aspect_ratio 不是 mixed 时，同一套 shots 使用统一 aspect_ratio
platform_decision.aspect_ratio 是 mixed 时，各 shot 按真实发布槽位填写比例
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
python <SKILL_DIR>/scripts/validate_platform_rules.py <SKILL_DIR>/references/platform-requirements.json
python <SKILL_DIR>/scripts/validate_plan.py <plan.json>
```
