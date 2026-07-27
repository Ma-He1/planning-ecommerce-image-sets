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
- 同一套图统一画幅和视觉系统；多个平台分别输出完整计划。
- 策划说明与生成提示词使用中文，图内文案跟随目标市场，包装原文保持不变。

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

Amazon `main_white` 另有机器复核：QA 必须保存结构化 `platform_evidence`，验证器使用 Pillow 读取最终图，重算最长边、四角 10% 严格 RGB 255 比例、整图严格白色比例与主体高度占比。人工填写 `platform: "pass"` 不能替代像素证据。

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
    │   ├── prompt-generation-routing.md
    │   └── qa-and-recovery.md
    └── scripts/
        ├── validate_delivery.py
        └── validate_plan.py
```

## 本地验证

```powershell
python .\planning-ecommerce-image-sets\scripts\validate_plan.py <plan.json>
python .\planning-ecommerce-image-sets\scripts\validate_delivery.py <run-dir>
```

只有两条命令都以退出码 0 完成，才能把该目录作为已验证交付。

## 使用边界

- 用户需要确保产品照片、品牌、人物肖像、字体和宣传文案具有合法使用权限。
- 发布前应重新核验目标平台和类目的当前官方规则。
- 透明材质、反射、商标、包装文字、手部动作和细小结构需要逐张检查。
- 医疗功效、安全认证、材料等级和性能数据必须有可靠来源。

## 许可

本仓库公开可见，但未附加开源许可证。公开可见不代表自动授予复制、修改、商用或再分发权限。
