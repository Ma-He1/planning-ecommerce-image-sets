---
name: planning-ecommerce-image-sets
description: Use when a user provides product photos or a short product brief and asks for ecommerce image-set planning, platform or language adaptation, per-image Chinese prompts, listing visuals, Amazon/Taobao/TikTok carousel images, portfolio image sets, or batch image generation.
---

# 电商整套图片策划与生成

把“产品照片＋简短需求”编译成可执行的电商套图：先锁定事实、平台与语言，再决定动态张数和逐图任务，最后生成中文提示词，使用 Codex 内置图像生成/编辑能力出图并验收。策划质量优先于盲目出图。

## 必守原则

1. 不套固定六图。只保留能回答不同买家问题、且当前素材能够支持的图片。
2. 策划说明、生图提示词、负面约束和 QA 一律使用中文；图内新增文案跟随目标市场；包装原文保持参考图原样。
3. 同一套图统一画幅。多平台需求先做内容母版，再分别派生平台套图；最终必须输出 `multi_set_manifest`，不得把不同平台规则混进一个单套计划。
4. 原始产品图是商品身份的最高依据。上一张 AI 成图不能成为下一张图唯一的产品参考。
5. 不猜测参考图看不见的背面、接口、内部、拆解、里料、材质成分、佩戴侧面或精确尺寸。
6. 未确认的性能、参数、认证、成分和比较结论不得写成事实；创意氛围不能升级为产品功效。
7. 每张图只有一个主要沟通任务。人物、场景、文案和视觉效果共同证明这个任务，不堆砌多个生活片段。
8. 精确参数、多行文字和关键营销文案优先采用“无字底图＋确定性排版”。
9. 当前生产边界固定为 Codex 内置能力：不接入、不配置、不调用任何外部生图或视频 API；实际出图只使用 Codex 内置 `imagegen` 图像生成/编辑能力。

## 工作流

### 1. 识别请求模式

- 用户只要策划或提示词：完成规划与验证，不调用生图。
- 用户明确要出图：规划验证通过后，使用 Codex 内置 `imagegen` 连续生成；已授权整套生成时，不逐张重复确认。
- 用户要求使用外部 API 或外部生成服务：说明该请求超出当前 Skill 的生产边界，不调用、不转接，也不把外部服务作为备用路线。

若缺少平台，采用唯一默认合同：`platform_type=portfolio`、`platform_name=国内通用电商作品集`、`decision_source=default`、`aspect_ratio=9:16`。这是可撤销默认值，不得归类为 `domestic_marketplace`。先阻塞受冲突事实直接影响的最小模块：只要商品身份仍可锁定，且存在不依赖冲突事实的安全页面，就必须保留可执行子集并把受影响页面写为 `blocking_scope=module`；只有没有任何安全 shot 时才允许以显式 `blocking_scope=whole_product` 阻塞整商品。用户明确要求暂缓某参数时，不得自行扩大到整 SKU。

用户同时指定两个或更多平台时，先提炼共享商品事实与买家问题，再为每个平台独立编译一套完整计划。顶层只能使用：`output_kind=multi_set_manifest`、`set_strategy=split`、`sets=[...]`。`sets[]` 中每套都必须独立填写平台、语言、画幅、首图、文案、shots、暂缓项与风险；不得用 `platform_plans` 对象、不得共享一个 `platform_decision`，也不得把 Amazon 白底首图与小红书内容封面塞进同一 `shots`。

### 2. 检查所有原始参考图

逐张查看原图，记录：商品身份是否清晰、可见角度、遮挡、包装文字、颜色、结构、比例、可直接复用部分和不可推断部分。不要仅凭文件名或用户一句话推断外观。

### 3. 判断平台与语言

完整阅读 [平台与语言规则](references/platform-language-rules.md)，输出判断来源与置信度。优先级：用户明确指定 > 上下文可靠推断 > 默认作品集。

把四件事分开：

- `planning_language`：固定 `zh-CN`
- `prompt_language`：固定 `zh-CN`
- `overlay_language`：服从用户或目标市场
- `packaging_text_policy`：固定 `preserve_original`

动态平台规范可能变化。凡声称“平台要求”时，先查询当前官方规则；无法联网时标注“待发布前复核”，不得把经验偏好冒充硬规则。

`platform_decision` 不只写结论，还必须写入以下非空溯源字段：

- `rule_checked_at`：本次核验时间，使用 ISO 8601 日期或日期时间，例如 `2026-07-22` 或 `2026-07-22T00:00:00+08:00`
- `hard_rules`：仅列平台、用户或项目的强制约束
- `creative_guidance`：单列非强制的转化与视觉建议
- `rule_sources`：每项包含非空 `title`、`url`、`source_type`

平台事实会变化；日期只说明本次核验发生过，不能替代发布前对当前官方规则的复核。

### 4. 建立事实账本与买家问题

将信息拆为：可见事实、用户确认事实、官方确认事实、不确定观察、缺失关键信息、创意假设。再列出买家真正需要回答的问题，例如“这是什么”“核心价值是什么”“如何使用”“尺寸是否合适”“有哪些配件”。

只有前三类事实可进入确定性卖点或参数。创意假设只能决定场景、色彩、人物和情绪。

### 5. 动态选择图片角色

从主 KV、合规白底、卖点、参数、细节、材质、尺寸、包装清单、比较、使用场景中按需选择。单张参考图通常形成 4–8 张可执行图；多角度、完整参数和包装资料可形成 6–10 张。这是经验区间，不是配额。

对有明确使用情境的实体商品，若“在哪里、如何使用”是核心买家问题，且现有商品身份图能够安全抠图合成，至少保留一张 `usage_scene`。人物接触会暴露参考图未显示的佩戴角度、背面或接口时，不要硬生成人体交互；可改用不接触商品的桌面、玄关、居家环境或前景商品合成来证明使用语境。只有场景不能增加新的购买信息或任何场景都会虚构商品结构时，才暂缓使用场景。不得因为某个参数无证据，就连同安全的使用价值一起删掉。

合并表达重复的页面。把缺证据的页面放入 `deferred_modules`，并显式写明 `blocking_scope=module | whole_product`；不得把它们计入 `recommended_image_count`。`recommended_image_count` 必须等于 `shots` 和 `ready_now` 的数量。

例如参考图正面可见 `480mL`、用户另提供 `500mL` 时，通常输出 `partially_ready`：保留不新增容量事实的主 KV、白底或其他安全页面，只把 `scale_capacity` 暂缓为 `blocking_scope=module`。只有用户明确要求制作 `500mL` 目标 SKU、现有引用却只能锁定 `480mL` 商品且没有任何匹配身份参考时，才把身份缺口标为 `blocking_scope=whole_product` 并输出 `blocked`。

### 6. 为每张图编写中文提示词

完整阅读 [规划输出合同](references/planning-contract.md) 和 [提示词与生成路由](references/prompt-generation-routing.md)。每张提示词通常写 150–250 个汉字，并按以下顺序表达：

先为每个可执行 `shots[]` 写入非空 `reference_inputs`，每项都包含原始或用户提供引用的 `path`，以及它在本图中约束商品身份、角度、结构、纹理、包装文字或尺寸证据的具体 `purpose`。没有足够身份或细节引用的模块必须进入 `deferred_modules`，不得为了通过合同塞入不支持该任务的引用。

1. 商品身份与参考图约束
2. 这张图唯一任务
3. 商品位置、占比与构图
4. 人物身份、动作与视线（适用时）
5. 场景、道具与效果证明
6. 镜头、光线、色彩与品牌气质
7. 图内文案、字体风格与安全位置
8. 保真要求和禁止项

文案策略必须自洽：

- `none`：提示词不得要求出现新增文字。
- `direct`：只用于极短、容错较高的标题，并明确准确文字。
- `post_layout`：生图提示词明确“画面不要生成任何新增文字，只预留文字安全区”，再由排版步骤添加 `exact_copy`。

### 7. 输出并验证严格 JSON

先在对话中给出可读中文摘要，再保存严格 JSON。输出字段、枚举与实例见 [规划输出合同](references/planning-contract.md)。将下方 `<SKILL_DIR>` 替换为本文件所在目录的绝对路径后运行：

单平台输出一个完整计划；多平台输出 `multi_set_manifest`，其中 `sets[]` 的每一项仍是同样的完整单平台计划。不要发明第二套顶层字段名。

所有新生成的单平台计划以及 `sets[]` 子计划都必须写 `version=2.0`，并为每个 `deferred_modules[]` 显式填写 `blocking_scope`。`version=1.0` 仅保留给 validator 读取历史非阻塞产物，不能用于新输出。

```powershell
python <SKILL_DIR>/scripts/validate_plan.py <plan.json>
```

验证失败就修订规划，未通过前不得开始批量出图。

### 8. 生成、排版与逐图验收

按照每张 `execution_action` 执行。实际出图统一使用 Codex 内置 `imagegen` 图像生成/编辑能力，不调用任何外部 API。需要编辑现有图时使用内置图像编辑模式，并始终附带原始产品参考。

每生成一张立即按 `qa_checks` 检查。完整阅读 [质量检查与失败恢复](references/qa-and-recovery.md)。身份、结构或事实错误属于致命失败，不得仅靠美化掩盖；每张最多三次有针对性的重试，仍失败则转合成、后期排版或人工复核。

## 默认交付物

- `content_plan.md`：中文策划摘要、平台与语言判断、逐图意图
- `image_set_plan.json`：可机检的完整规划
- `prompts.md`：按图片编号整理的中文提示词与负面约束
- `outputs/`：用户要求出图时的成图
- `qa_report.md`：逐图通过、失败、重试和待补资料记录

## 出图前停止线

出现任一情况，暂停对应页面而不是编造：

- 看不见的产品结构成为画面主体
- 精确参数、认证、成分或功效没有来源
- 平台首图可能违规
- 参考图不足以保持身份一致
- 文案语言、包装原文或文字生成路线相互冲突
- 当前页面仍试图同时表达两个以上主要购买理由
- 参数冲突只暂停直接依赖该参数的页面；若商品身份仍可锁定且存在安全页面，不得阻塞整套
