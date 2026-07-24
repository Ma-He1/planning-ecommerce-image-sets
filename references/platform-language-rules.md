# 平台与语言判断规则

## 先区分三种信息

- **平台硬规则**：发布前必须满足，可能随时间和类目变化；优先查询平台官方文档。
- **平台创意惯例**：提高转化或适配信息流的经验，不得写成强制要求。
- **本项目视觉决策**：为作品集统一性或品牌调性作出的选择。

判断顺序：用户明确指定 > 商品链接、站点或上下文可靠推断 > “国内通用电商作品集”默认。输出 `decision_source` 和 `confidence`，不隐藏推断。

每次判断都要把规则证据编译进 `platform_decision`：`rule_checked_at` 写实际核验日期；`hard_rules` 只放必须遵守的约束；`creative_guidance` 放非强制的转化与视觉建议；`rule_sources` 至少一项，每项写明 `title`、`url`、`source_type`。平台事实可能变化，生产前应再次检查当前官方规则；无法联网时明确“待发布前复核”，不得省略溯源或伪装成实时核验。

若用户没有提供平台，默认值必须完整写为：`platform_type=portfolio`、`platform_name=国内通用电商作品集`、`decision_source=default`、`aspect_ratio=9:16`。不得把这个作品集默认值归入 `domestic_marketplace`。其 `rule_sources[].url` 可使用 Skill 本地定位符 `skill://planning-ecommerce-image-sets/references/platform-language-rules.md#品牌官网与作品集`，`source_type` 写 `skill_local`。

## 平台类型

### Amazon

- 发布前查询目标站点、目标类目的官方图片规范。
- 当前通用首图策略：实际售卖商品、纯白背景、不得叠加营销文字、边框、水印或造成误解的非售卖道具。
- 本 Skill 默认把同套图规划为 `1:1`，这是便于资产统一和详情页复用的项目决策；若当前官方/类目规范或用户模板另有要求，以其为准。
- 首图角色必须为 `main_white`，文字策略必须为 `none`。
- 副图可使用英文卖点、场景、尺寸和图解，但文案必须有事实来源。

发布前复核入口：

- https://sellercentral.amazon.com/help/hub/reference/G1881
- https://sellercentral.amazon.com/seller-forums/discussions/t/13af96ea-6b07-4bf9-8dbe-a13292c2e3b1

### 国内货架电商

- 类型值：`domestic_marketplace`。
- 仅在用户明确指定或上下文可靠指向淘宝、天猫、京东等货架平台时使用；缺少平台时不要套用此类型。
- 默认首图为带品牌记忆和核心利益点的 `hero_kv`；若类目活动页要求白底或特定模板，服从当期规则。
- 画幅从用户店铺模板选择；无模板时，作品集展示默认 `9:16`，常规货架主图可选 `1:1`。
- 文案可更有冲击力，但每张仍只承担一个主要任务，不做“大字堆满”。

### TikTok、短视频商城与信息流轮播

- 类型值：`social_commerce`。
- 优先竖版、移动端大字号、明确安全区和真实使用动作。
- TikTok 当前轮播规范支持竖版 `720×1280`；创意手册建议优先 `9:16`、720P 以上并把重要元素放在安全区。发布前复核官方页面。
- 单张卡片应独立可读，连续卡片组成“识别—价值—证据—行动”节奏。

发布前复核入口：

- https://ads.tiktok.com/help/article/specifications-for-carousel-ads
- https://ads.tiktok.com/business/library/Image_Ads_Carousel_Ads_Playbook.pdf

### 小红书、Instagram 等内容种草

- 归为 `social_commerce`，并在 `platform_name` 写具体平台。
- 小红书作品集或商品种草默认可选 `3:4` 或 `9:16`；同一套只选一种。
- 用人物、动作、生活环境证明卖点，弱化传统参数海报感。标题和角标仍需预留安全区。

### 品牌官网与作品集

- 类型值分别为 `brand_site`、`portfolio`。
- 官网按组件槽位确定比例；作品集优先选择最能体现商品纵横结构的一种比例并贯穿整套。
- 作品集允许兼顾审美叙事，但不得伪造真实平台规则或产品功能。

## 语言分层

始终单独记录四层：

| 层级 | 默认策略 |
|---|---|
| 策划说明 | 简体中文 `zh-CN` |
| 生图提示词 | 简体中文 `zh-CN` |
| 图内新增文案 | 用户指定；否则跟随目标市场 |
| 包装、瓶身、铭牌原文 | `preserve_original`，不得翻译重绘 |

市场推断只作为默认：大陆市场 `zh-CN`，港澳台按目标地区选择繁体，Amazon US/TikTok US 选 `en-US`。用户指定优先。

## 字体与排版方向

- 简体中文：几何无衬线、现代黑体、字重对比明确；避免廉价描边和过度发光。
- 繁体中文：选择完整繁体字库；不以简体字形代替；短标题留足字面呼吸感。
- 英文：短标题可用现代 grotesk/sans，功能数据用易读数字字体；避免全图使用同一巨大粗体。
- 日文、韩文或阿拉伯文：只有在用户或市场明确时使用，并将精确文字默认转后期排版。

所有语言都要先确定文字层级、字数、对齐方式和安全位置，再写入逐图提示词。
