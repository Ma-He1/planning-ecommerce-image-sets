# 规划输出合同

## 可读摘要

在 JSON 前先向用户说明：

1. 目标平台、市场、画幅和判断依据
2. 当前参考图能可靠支持什么、不能支持什么
3. 推荐生成几张以及为什么不是固定六张
4. 每张图说什么、如何表达、使用哪些原始参考
5. 哪些页面暂缓以及需要补什么资料

## JSON 顶层结构

保存为 UTF-8 JSON，不写注释。单平台计划必须包含：

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

## 多平台拆套结构

同一商品同时面向两个或更多平台时，不得让一个单套计划同时承载多个画幅、首图规则或成品语言。顶层必须固定为：

```json
{
  "output_kind": "multi_set_manifest",
  "set_strategy": "split",
  "sets": [
    { "version": "2.0", "platform_decision": {}, "shots": [] },
    { "version": "2.0", "platform_decision": {}, "shots": [] }
  ]
}
```

- `output_kind` 只能为 `multi_set_manifest`
- `set_strategy` 只能为 `split`
- `sets` 至少包含两套完整的单平台计划；上方省略号只用于解释，实际每套必须包含本合同规定的全部单平台字段
- 每套的 `platform_name`、平台类型或画幅合同必须彼此可区分，并分别通过单平台验证
- 不允许使用 `plan_type`、`platform_plans` 或按平台名动态命名的对象替代 `sets[]`，避免下游解析器依赖不稳定键名
- 共享商品事实可以在各套中复用，但平台规则、首图角色、画幅、成品文案语言、张数和暂缓模块必须逐套判断

## 平台与语言字段

`platform_decision`：

- `platform_type`：`amazon | domestic_marketplace | social_commerce | brand_site | portfolio | custom`
- `platform_name`：具体名称，如“淘宝”“Amazon US”“小红书”
- `decision_source`：`explicit | inferred | default`
- `confidence`：`high | medium | low`
- `first_image_rule`：`main_white | hero_kv | editorial_cover | custom`
- `aspect_ratio`：`1:1 | 3:4 | 4:5 | 9:16 | 4:3 | 16:9`
- `rule_checked_at`：本次规则核验时间，必须为 ISO 8601 日期或日期时间，例如 `2026-07-22` 或 `2026-07-22T00:00:00+08:00`
- `hard_rules`：非空数组，只放平台、用户或项目的强制约束
- `creative_guidance`：非空数组，只放非强制的转化与视觉建议
- `rule_sources`：非空数组，每项必须包含非空 `title`、`url`、`source_type`

`rule_sources[].url` 通常使用当前官方 HTTP(S) 页面。默认“国内通用电商作品集”没有外部平台规则，可使用 Skill 本地定位符 `skill://planning-ecommerce-image-sets/references/platform-language-rules.md#品牌官网与作品集`，并将 `source_type` 写为 `skill_local`。无法联网时也要记录实际核验日期、当前可用来源和“发布前复核”这一强制约束，不得伪造已实时核验。平台事实可能变化，生产前应重新检查。

缺少平台时，默认合同固定为：`platform_type=portfolio`、`platform_name=国内通用电商作品集`、`decision_source=default`、`aspect_ratio=9:16`。不得把该默认作品集写成 `domestic_marketplace`。

`language_decision`：

- `planning_language`：固定 `zh-CN`
- `prompt_language`：固定 `zh-CN`
- `overlay_language`：目标市场语言代码
- `packaging_text_policy`：固定 `preserve_original`

## 事实账本

`facts` 至少分为：

- `visible_facts`
- `user_confirmed_facts`
- `official_confirmed_facts`
- `uncertain_observations`
- `missing_critical_info`
- `creative_assumptions`

只有 `visible_facts`、`user_confirmed_facts`、`official_confirmed_facts` 可支撑确定性卖点。若用户把愿望写成“突出降噪”，但没有官方规格，可表达“通勤更专注”的场景目标，不能改写成“深度降噪 XXdB”。

## 每张图字段

每个 `shots[]` 包含：

- `image_id`：两位序号＋英文角色，如 `01_hero_kv`
- `role`：`hero_kv | main_white | selling_points | specification | feature_detail | material_macro | scale_capacity | package_contents | comparison | usage_scene`
- `priority`：`required | recommended | optional`
- `execution_action`：见提示词与生成路由
- `reference_risk`：`low | medium`；`blocked` 只能进入暂缓模块
- `content_message`：本图唯一核心信息
- `buyer_question_answered`：本图回答的买家问题
- `aspect_ratio`：与整套完全一致
- `reference_inputs`：非空数组；每项包含非空 `path` 与 `purpose`
- `generation_prompt`：中文、具体、可执行
- `text_strategy`：`mode`、`exact_copy`、`overlay_language`
- `negative_constraints`：禁止生成或改动的内容
- `qa_checks`：本图的可观察验收标准

`execution_action` 只允许：

- `reuse`
- `clean_up`
- `reference_generate`
- `scene_composite`
- `generate_then_layout`

`text_strategy.mode` 只允许：`none | direct | post_layout`。

`reference_inputs` 示例：

```json
[
  {
    "path": "absolute-or-user-supplied-reference",
    "purpose": "产品身份、角度或细节依据"
  }
]
```

每个 `shots[]` 都是当前可执行页面，因此都必须分配至少一个真实可用引用。若素材不能支持所需身份、角度或细节，不得填入无关引用凑数；应把该模块移入 `deferred_modules`。

## 数量合同

必须满足：

```text
recommended_image_count == shots.length == ready_now.length
ready_now == shots[].image_id（顺序一致）
deferred_modules 与 ready_now 没有交集
所有 shots 使用同一 aspect_ratio
所有 shots 都有非空 reference_inputs，且每项 path、purpose 非空
```

暂缓模块字段：

- `module_id`
- `why_deferred`
- `required_inputs`
- `blocking_scope`：`module | whole_product`；每个暂缓模块都必须显式填写，缺失即验证失败

新计划固定使用 `version=2.0`。`version=1.0` 只用于读取本 Skill 升级前的历史非阻塞计划：validator 可把其中缺失的 `blocking_scope` 迁移解释为 `module`；`blocked` 历史计划仍必须有显式 `whole_product`。不得为新输出选择 1.0 来绕过必填字段。

不要用“总共计划 10 张，其中 3 张不能做”这种表达。应写“当前可执行 7 张，另有 3 个暂缓模块”。

## 状态机

- `partially_ready`：`recommended_image_count` 为正数，`shots` 与 `ready_now` 非空且数量一致；至少一个暂缓模块为 `blocking_scope=module`；不得存在 `whole_product` blocker。
- `blocked`：`recommended_image_count=0`、`shots=[]`、`ready_now=[]`、`needs_more_info` 非空；至少一个暂缓模块显式写为 `blocking_scope=whole_product`。
- 任何 `whole_product` blocker 与可执行 shots 同时存在都无效。
- `blocked` 只有 `module` 或缺失 `blocking_scope` 的暂缓项无效。
- `overall_status` 只允许 `ready | partially_ready | blocked`。

阻塞受冲突事实直接影响的最小范围。参考图可见 `480mL`、用户另提供 `500mL` 时，若现有参考仍能锁定商品身份，通常保留不新增容量事实的安全页面，输出 `partially_ready`，并把 `scale_capacity` 标为 `blocking_scope=module`。只有用户明确要求 `500mL` 目标 SKU、却没有匹配身份参考且不存在任何安全 shot 时，才允许整商品 `blocked`。

## 完整实例

读取 [耳机策划实例](example-earbuds-plan.json)。生成自己的 JSON 后，将 `<SKILL_DIR>` 替换为 Skill 目录的绝对路径运行：

```powershell
python <SKILL_DIR>/scripts/validate_plan.py <plan.json>
```
