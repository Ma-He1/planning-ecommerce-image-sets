# Planning Ecommerce Image Sets

面向 **OpenAI Codex** 的电商整套图片策划 Skill。

它把产品照片和简短资料整理成可执行的电商视觉方案：确认产品事实、判断平台和语言、分析买家问题、选择图片角色、编写逐图中文提示词，并在用户要求时使用 Codex 内置图像生成能力完成图片与质量检查。

它依托 Codex 智能体完成从策划、提示词到生成验收的完整流程，并针对不同平台分别编译套图。

## 主要能力

- 从一张或多张产品照片建立事实账本
- 根据商品与购买问题动态决定图片数量和顺序
- 规划主视觉、合规首图、卖点、参数、细节、材质、尺寸、包装和使用场景
- 为不同平台、市场和语言分别建立套图合同
- 为每张图分配原始参考、构图、人物、场景、文案、安全区和负面约束
- 输出中文生成提示词与可机检 JSON
- 检查商品身份、结构、文字、事实和平台合同
- 对失败页面提供重试、合成、后期排版或补资料路线
- 保存相对路径、SHA256、逐次尝试、耗时与 QA 的可审计交付记录

## 设计原则

- 产品原始照片优先于生成结果，生成图不能替代商品身份参考。
- 图片数量由事实、素材、买家问题和平台要求共同决定。
- 未确认的参数、功效、认证、成分和比较结论不能进入确定性卖点。
- 每张图只承担一个主要沟通任务。
- 同一套图统一视觉系统；画幅服从真实发布槽位，单一画幅和多槽位比例都可表达；多个平台分别输出完整计划。
- 策划说明与生成提示词使用中文，图内文案跟随目标市场，包装原文保持不变。

## 平台规则覆盖

Skill 内置机器可读的 `platform-requirements.json`，每条规则记录适用发布面、强制/建议/条件层级、官方来源、核验日期和发布前复核项。当前覆盖 14 个平台画像：

| 画像 | 当前证据状态 | 说明 |
|---|---|---|
| Amazon US | 公开规则已核验 | 通用商品详情图；类目例外仍需复核 |
| eBay US | 公开规则已核验 | 商品刊登图 |
| Etsy | 公开规则已核验 | 商品 listing 图片 |
| Walmart US | 公开规则已核验 | Marketplace 商品详情图 |
| TikTok Shop US | 公开规则已核验 | 商品详情图，不含短视频或广告素材 |
| Shopify | 公开规则已核验，主题需复核 | 商品媒体上传合同与主题槽位分开 |
| Shopee | 部分公开 | 站点和 Mall/普通店差异需复核 |
| Lazada | 部分公开 | Open Platform API 与 Seller Center 不混用 |
| 淘宝 | 基础公开规则已核验 | 淘宝通用发布规则；像素、比例和叶子类目规则需后台复核 |
| 天猫 | 部分公开 | 只固化淘宝与天猫共同适用的 AI 图片不失真规则，其余按当前类目与后台复核 |
| 京东 | 基础公开规则已核验 | 业务类型和类目专项规则需后台复核 |
| 拼多多 | 基础公开规则已核验 | 动态上传规格需后台复核 |
| 抖音电商 | 通用公开规则已核验 | 商品详情图与内容封面分开 |
| 小红书 | 必须实时核验 | 旧开放平台 API 仅作条件规则 |

规则库本次核验日期为 2026-07-29。平台规则会变化，发布时仍需按目标国家/地区、类目、账号和当前发布器复核。公开资料不足的平台不会用第三方博客数字补齐，也不会把建议值伪装成发布硬门槛。官方来源 URL 还会按画像的官方域名白名单校验，历史官方课件只能作为部分证据，不能自行升级为当前通用硬规则。

规则库同时给每个画像声明一个最小 `machine_constraints` 子集，用于检查计划总张数、发布槽位张数、首图角色和文字模式；`hard_rules` 还必须与唯一的稳定 `hard_rule_ids` 一一绑定，`verified_current` 计划必须完整继承画像通用硬规则。机器通过不等于平台全部合规，类目例外、条件规则、商品真实性、审美和当前发布后台仍需人工复核。

`user_contract` 和普通链接不能放宽内置平台规则。`live_platform_ui` 可以作为审计来源，但不会仅凭标签自动提高核验状态、删除硬规则或改写首图合同；平台确有变化时，应先复核证据、更新规则库并跑完回归测试。

几个容易混淆、已在规则库中明确分开的例子：

- Amazon US 通用图片最长边公开发布范围为 500–10,000 px；1000 px 以上是支持缩放的生产建议，不是发布底线。
- eBay 的文字、营销图形和水印禁限适用于全部刊登图片；它没有通用强制纯白背景。
- Etsy 没有全站统一白底或固定比例硬规则，首图应为不同缩略图裁切留空间。
- TikTok Shop US 的 1:1 是常规商品图建议；3:4 至 4:3 只属于官方 Excel/批量上传路径的条件规则，不能外推为所有入口的通用合同。
- 拼多多公开通则写“主图背景以纯白为主”，这不等同于 Amazon 的严格 RGB 255 像素合同。

## Codex 图像生成

本仓库是策划 Skill，不包含独立模型或模型权重。

当用户要求成图时，Skill 指导 Codex 使用当前环境提供的内置 `imagegen` 进行生成或编辑。仓库不要求配置额外密钥，也不会自行启动独立生成服务。实际可用能力和额度取决于用户当前的 Codex 环境。

## 输入

最低输入：

- 至少一张产品照片
- 一句任务描述

推荐补充：

- 产品名称、型号和售卖版本
- 尺寸、容量、材质、颜色和包装清单
- 已确认卖点及证据
- 目标平台、国家或地区
- 图内文案语言
- 画幅、店铺模板或作品集用途
- 禁止出现的元素

信息不足时，Skill 会保留能够安全执行的页面，并把受影响的内容列为暂缓模块。

## 输出

- `brief.json` 与 `inputs/`：确认后的任务和原始参考
- `content_plan.md`：事实边界、平台判断、视觉系统和逐图意图
- `image_set_plan.json`：可机检的完整计划
- `prompts.md`：逐图中文提示词、准确文案和负面约束
- `run_manifest.json`：模式、文件哈希、逐次尝试、耗时与汇总指标
- `outputs/`：用户要求生成时的图片
- `qa_report.json`：生成模式的结构化逐图 QA
- `contact_sheet.jpg`：生成模式的整套联系表

纯策划使用 `planning_only`，不得登记生成输出；成图使用 `generation`，必须保存最终图片、结构化 QA 与联系表。完整字段和示例见 `references/delivery-record-contract.md`。

生成交付还必须逐次记录实际提示词、参考输入、原始结果及其 SHA256，并由具名复核者完成身份、事实、平台、文字与构图检查。`brief.json`、`content_plan.md`、`qa_report.json` 和 `contact_sheet.jpg` 都必须在 manifest 中有可校验的证据记录；总体和每张计划图片全部通过才算完整。

Amazon `main_white` 另有机器复核：QA 必须保存结构化 `platform_evidence`，验证器使用 Pillow 读取最终图，重算 500–10,000 px 最长边、四角 10% 严格 RGB 255 比例、整图严格白色比例、前景面积与抗细线主体最长轴占比。这个像素检查是保守型 QA 代理，不替代平台和类目人工审核；人工填写 `platform: "pass"` 也不能替代像素证据。逼真的 AI 生成人物 XMP 元数据目前仍是发布前人工检查项。

## 安装到 Codex

真正的 Skill 位于仓库子目录：

```text
planning-ecommerce-image-sets/
```

可以在 Codex 中使用 `$skill-installer` 从以下目录安装：

```text
https://github.com/Ma-He1/planning-ecommerce-image-sets/tree/main/planning-ecommerce-image-sets
```

也可以把该子目录复制到个人 Skill 目录。安装后重新启动或刷新 Codex，使其重新发现 Skill。

## 调用方式

显式调用：

```text
$planning-ecommerce-image-sets
根据我提供的产品照片和参数，先判断平台与语言，再规划整套电商图。每张图说明沟通任务、表达方式、参考图、准确文案和中文生成提示词。
```

需要生成时：

```text
$planning-ecommerce-image-sets
先完成并验证整套策划，再使用 Codex 内置图像生成能力逐张生成和验收。
```

## 目录结构

```text
.
├── README.md
└── planning-ecommerce-image-sets/
    ├── SKILL.md
    ├── agents/
    │   └── openai.yaml
    ├── references/
    │   ├── delivery-record-contract.md
    │   ├── planning-contract.md
    │   ├── platform-language-rules.md
    │   ├── platform-requirements.json
    │   ├── prompt-generation-routing.md
    │   └── qa-and-recovery.md
    └── scripts/
        ├── validate_delivery.py
        ├── validate_platform_rules.py
        └── validate_plan.py
```

## 本地验证

```powershell
python .\planning-ecommerce-image-sets\scripts\validate_platform_rules.py .\planning-ecommerce-image-sets\references\platform-requirements.json
python .\planning-ecommerce-image-sets\scripts\validate_plan.py <plan.json>
python .\planning-ecommerce-image-sets\scripts\validate_delivery.py <run-dir>
```

只有对应模式所需的命令都以退出码 0 完成，才能把该目录作为已验证交付。

### 计划合同升级

本版本把计划 schema 升级为 `3.0`。旧 `2.0` 计划必须补齐平台画像、验证状态、与硬规则一一对应的 `hard_rule_ids`、来源和发布前复核字段后再运行 `validate_plan.py`；验证器会明确拒绝未迁移的旧合同，避免它们绕过新的平台规则检查。

## 使用边界

- 用户需要确保产品照片、品牌、人物肖像、字体和宣传文案具有合法使用权限。
- 发布前应重新核验目标平台和类目的当前官方规则。
- 透明材质、反射、商标、包装文字、手部动作和细小结构需要逐张检查。
- 医疗功效、安全认证、材料等级和性能数据必须有可靠来源。

## 许可

本仓库公开可见，但未附加开源许可证。公开可见不代表自动授予复制、修改、商用或再分发权限。
