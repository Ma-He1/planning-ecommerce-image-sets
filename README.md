# Planning Ecommerce Image Sets

一个面向 **OpenAI Codex** 的电商整套图片策划 Skill。

它把“一张或几张产品照片 + 简短产品信息”整理成可执行的电商视觉方案：先确认产品事实、目标平台和语言，再动态决定图片数量、每张图承担的任务、画面表达、文字位置、参考图使用方式、中文生图提示词与验收规则。

> 这是 Codex Skill，不是独立生图模型，也不是外部生图 API 客户端。

## 它解决什么问题

常见电商图片工作流容易直接套用固定六张图，导致不同产品都使用同一结构，主图、参数图、卖点图和场景图之间重复，提示词也缺少产品事实约束。

本 Skill 采用动态策划：

1. 识别产品照片中可见、不可见和待确认的信息。
2. 根据 Amazon、国内电商、社交电商等平台规则选择图片角色。
3. 根据目标市场确定画面文案语言、语气和信息密度。
4. 围绕买家问题动态规划整套图片，不强制固定张数。
5. 为每张图生成明确的画面任务、构图、文字层级、人物或场景表达、参考图和负面约束。
6. 在出图后检查产品身份、结构、文字、事实和平台合规性。

## Codex 与生图能力的关系

策划、提示词编排、校验和失败恢复由本 Skill 指导 Codex 完成。

实际生成或编辑图片时，Skill 只调用当前 Codex 环境提供的内置 `imagegen` 图像生成/编辑能力：

- 不接入 GPT Image、HFSY、Echoon、Seedance 等第三方或外部生成服务。
- 不要求用户在本仓库中配置 API Key。
- 不包含模型权重，也不会自行启动外部计费 API。
- 仓库本身不会独立生成图片；必须在能够使用 `imagegen` 的 Codex 环境中运行。
- Codex 账户、工作区或产品版本是否提供图像生成能力，以及相关使用额度，以用户当前环境为准。

## 适用范围

- 商品主 KV、白底主图、尺寸参数图和结构说明图
- 材质、接口、工艺、包装和局部细节图
- 人物使用场景、生活方式场景和问题解决型场景
- 单卖点或多卖点信息图
- Amazon US 等海外平台的英文画面文案
- 国内平台的中文高信息密度卖点表达
- 同一产品面向多个平台或多种语言的差异化方案

当前方案适合消费电子、家居日用、服饰箱包、食品饮料、美妆护肤、玩具摆件等实体商品。涉及医疗功效、安全认证、材料等级、容量、尺寸、电气参数等信息时，只能使用用户提供或可靠来源确认的事实。

## 输入

最低输入：

- 一张产品照片
- 一句简短需求

推荐补充：

- 产品名称和型号
- 尺寸、容量、材质、颜色、包装清单
- 已确认卖点及其证据
- 目标平台、国家或地区
- 画面文案语言
- 期望比例或作品集展示方式
- 禁止出现的元素

信息不足时，Skill 会把缺失内容标记为待确认、延期模块或人工复核项，不会把猜测写成商品事实。

## 输出

一次完整策划通常包含：

- 产品事实表与证据等级
- 平台、语言、比例和视觉方向
- 动态图片数量及选择理由
- 每张图的图片角色与买家问题
- 主标题、副标题和卖点文案
- 构图、产品位置、人物、场景、光线和字体建议
- 参考图使用说明
- 每张图的中文生成提示词
- 文字生成或后期排版路线
- 负面约束与逐图质量检查
- 延期模块和需要用户确认的事实

提示词使用中文编写；当目标市场要求英文画面文案时，提示词仍为中文，但需要展示的英文文案以精确文本写入。

## 安装到 Codex

本仓库使用“仓库说明 + 独立 Skill 目录”的结构，真正的 Skill 位于：

```text
planning-ecommerce-image-sets/
```

推荐在 Codex 中调用 `$skill-installer`，并要求它从下面的 GitHub 子目录安装：

```text
https://github.com/Ma-He1/planning-ecommerce-image-sets/tree/main/planning-ecommerce-image-sets
```

也可以手动把该子目录复制到用户级 Skill 目录：

```text
~/.agents/skills/planning-ecommerce-image-sets
```

Windows 对应位置通常是：

```text
%USERPROFILE%\.agents\skills\planning-ecommerce-image-sets
```

Codex 通常会自动检测 Skill 变化；若没有出现在 Skill 列表中，重新启动 Codex。

## 调用示例

显式调用：

```text
$planning-ecommerce-image-sets
用这两张杯子照片做一套 Amazon US 电商图。产品高 15cm、容量 250ml，画面文案使用英文，提示词使用中文。
```

也可以直接描述任务，由 Codex 根据 Skill 的描述自动匹配：

```text
根据这张产品照片和简短卖点，先策划整套电商图，再用 Codex 内置生图能力生成并逐张验收。
```

## 目录结构

```text
.
├── README.md
├── .gitignore
└── planning-ecommerce-image-sets/
    ├── SKILL.md
    ├── agents/
    │   └── openai.yaml
    ├── references/
    │   ├── planning-contract.md
    │   ├── platform-language-rules.md
    │   ├── prompt-generation-routing.md
    │   ├── qa-and-recovery.md
    │   └── example-earbuds-plan.json
    └── scripts/
        ├── validate_plan.py
        └── evaluate_plan.py
```

## 本地验证

校验示例策划：

```powershell
python .\planning-ecommerce-image-sets\scripts\validate_plan.py `
  .\planning-ecommerce-image-sets\references\example-earbuds-plan.json
```

## 重要边界

- 产品照片是产品身份和结构的主要依据，生成结果不能擅自改变外形、接口、包装或品牌元素。
- 未确认的参数、认证、功效、材质和兼容性不能作为确定卖点。
- Amazon 主图与附图、国内平台和社交内容的规则不同，必须按目标平台单独判断。
- AI 生成的文字、透明材质、反射、商标和细小结构需要逐张检查。
- 用户需要确保产品照片、品牌、人物肖像、字体和宣传文案具有合法使用权限。

## 当前状态

- Skill 结构校验：通过
- 示例策划校验：通过
- 自动化回归测试：100 项通过
- 外部生图 API：未接入
- 实际出图路线：Codex 内置 `imagegen`

## 许可

当前仓库按私有项目发布，暂未附加开源许可证。未获得仓库所有者许可前，不代表允许公开复制、修改或再分发。
