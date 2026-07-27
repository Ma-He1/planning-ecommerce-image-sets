# 交付记录合同

本合同把一次策划或生成运行保存为可复核目录。`run_manifest.json` 是计划、输入、逐图尝试、最终输出和 QA 结论之间的机器可检索索引；只有 `validate_plan.py` 与 `validate_delivery.py` 都通过后，才能声称交付完成。

## 目录结构

两种模式都必须保存：

```text
<run-root>/
├── brief.json
├── inputs/
├── content_plan.md
├── image_set_plan.json
├── prompts.md
└── run_manifest.json
```

`generation` 还必须保存：

```text
├── qa_report.json
├── outputs/
└── contact_sheet.jpg
```

`planning_only` 不生成图片：`qa_report.json` 与 `contact_sheet.jpg` 不存在，`outputs/` 不存在或为空，manifest 中的输出与联系表字段为空或省略。

## 路径与 SHA256

- manifest 内所有路径使用相对 `<run-root>` 的路径，不接受绝对路径、盘符、UNC 路径或 `..` 越界。
- 路径解析后必须仍在 `<run-root>` 内，并指向合同要求的普通文件或目录；符号链接不能绕过边界。
- 原始参考放在 `inputs/`，接受的最终图放在 `outputs/`。
- 每个计划引用必须存在于 manifest 的 `inputs[]` 中。
- 每个输入、计划、提示词、任务简报、内容计划、QA、联系表、成功尝试原始结果和接受的最终图都记录文件字节的 SHA256；值必须是 64 位小写十六进制。

## `run_manifest.json`

顶层字段：

| 字段 | 合同 |
|---|---|
| `schema_version` | 固定为 `1.0` |
| `run_id` | 本次运行的非空唯一标识 |
| `mode` | `planning_only` 或 `generation` |
| `tool_route` | 生成模式固定为 Codex 内置 `imagegen`；纯策划使用 `none` |
| `started_at`, `finished_at` | 含时区的 ISO 8601 日期时间 |
| `total_elapsed_ms` | 非负整数，与顶层起止时间相差不超过 1 ms |
| `inputs[]` | `{path, sha256}`；每个输入均在 `inputs/` 内 |
| `brief`, `content_plan` | 两种模式都必填的 `{path, sha256}` 证据记录 |
| `plan`, `prompts` | `{path, sha256}`，分别指向 `image_set_plan.json` 与 `prompts.md` |
| `qa_report`, `contact_sheet` | `generation` 必填的 `{path, sha256}` 证据记录 |
| `shots[]` | 与计划逐图一一对应的运行记录 |
| `aggregate_metrics` | 可从 `shots[]` 重算的汇总 |

这些证据记录不是仅凭同名文件存在即可省略的索引；缺少字段、哈希或文件字节变化都使交付无效。

### 逐图与逐次尝试

每个 `shots[]` 包含：

```json
{
  "image_id": "01_hero",
  "attempt_count": 1,
  "elapsed_ms": 1500,
  "attempts": [
    {
      "attempt_index": 1,
      "started_at": "2030-01-01T12:00:00Z",
      "finished_at": "2030-01-01T12:00:01.500Z",
      "elapsed_ms": 1500,
      "tool_route": "imagegen",
      "prompt": "生成产品主视觉，严格保持原始参考中的身份与结构。",
      "prompt_sha256": "c81bcdbc91de21b589a4c88f81e1162e42c755ddb162403959ffc340af00a0b3",
      "reference_inputs": [
        {
          "path": "inputs/reference.png",
          "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        }
      ],
      "status": "success",
      "raw_result_path": "outputs/raw/01-attempt-1.png",
      "raw_result_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    }
  ],
  "output_path": "outputs/01.png",
  "output_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "qa_verdict": "pass"
}
```

- 每图最多 3 次尝试。
- `attempt_index` 从 1 开始且连续；`attempt_count == attempts.length`。
- 尝试时间使用含时区的 ISO 8601；结束不得早于开始，也不得超出运行起止时间。
- 每次 `elapsed_ms` 与起止时间相差不超过 1 ms；逐图耗时等于尝试耗时之和。
- 每次尝试固定记录 `tool_route: "imagegen"`、实际发送的非空 `prompt` 及其 UTF-8 字节 SHA256。
- 每次尝试的非空 `reference_inputs[]` 路径与 SHA256 必须逐项匹配顶层 `inputs[]`。
- `status` 为 `success` 或 `failed`；每个成功尝试必须保存并校验 `raw_result_path` 与 `raw_result_sha256`。
- 每次尝试完成后立即把记录写回 manifest，不在整套完成后凭记忆补写。
- 生成模式的 `attempts[]` 必填且非空；只有 `attempt_count` 与 `elapsed_ms` 的摘要不能构成可审计生成记录。

### QA 与通过条件

生成模式的 `qa_report.json` 至少包含：

```json
{
  "overall_verdict": "pass",
  "shots": [
    {
      "image_id": "01_hero",
      "verdict": "pass",
      "output_path": "outputs/01.png",
      "reviewed_at": "2030-01-01T12:00:01.500Z",
      "reviewer": "codex",
      "checks": {
        "identity": "pass",
        "facts": "pass",
        "platform": "pass",
        "text": "not_applicable",
        "composition": "pass"
      },
      "issues": [],
      "recovery": ""
    }
  ]
}
```

- 计划、manifest 与 QA 的 `image_id` 集合必须相同且无重复。
- `reviewed_at` 使用含时区 ISO 8601，`reviewer` 为非空字符串。
- `checks` 必须覆盖 `identity`、`facts`、`platform`、`text` 与 `composition`，每项只能为 `pass` 或 `not_applicable`。
- `issues` 是字符串数组，`recovery` 是字符串。
- manifest 的 `qa_verdict` 与 QA 记录必须一致且为 `pass`。
- `pass` 必须绑定存在于 `outputs/` 的最终图、正确 SHA256 和相同 QA 输出路径。
- 只有 `overall_verdict` 和全部计划图片都为 `pass` 的完整生成套图才能通过交付验证。

### Amazon `main_white` 平台证据

当 `image_set_plan.json` 的 `platform_decision.platform_type` 为 `amazon`，并且某个计划图片的 `role` 为 `main_white` 时，对应 QA 图片还必须保存：

```json
{
  "platform_evidence": {
    "longest_side_px": 1600,
    "corner_sample_ratio": 0.1,
    "corner_strict_white_ratio": 1.0,
    "overall_strict_white_ratio": 0.530547265625,
    "product_fill_height_ratio": 0.89875
  }
}
```

`validate_delivery.py` 使用 Pillow 直接读取接受的最终图并重算，不信任人工填写的 `platform: "pass"`：

- 最长边至少为 1000 px，且 `longest_side_px` 与图片尺寸一致。
- 从四角分别截取宽、高各 10% 的矩形；像素只有在 RGB 三通道均为 255 时才算严格白色。`corner_strict_white_ratio` 记录四块中的最低比例，并且不得低于 0.99。
- `overall_strict_white_ratio` 记录整张图严格 RGB 255 像素占比。
- 前景像素定义为任一 RGB 通道低于 245；其非空包围盒高度除以画布高度得到 `product_fill_height_ratio`，必须位于 0.85 至 1.0。
- `corner_sample_ratio` 固定为 0.1；全部记录值与重算值的允许误差为 `1e-6`。缺字段、灰白角落、分辨率不足、主体高度不足或伪造比例都会使验证失败。

修改 `qa_report.json` 后必须同步更新 manifest 的 QA SHA256。

### 汇总字段

```json
{
  "aggregate_metrics": {
    "shot_count": 1,
    "attempt_count": 1,
    "elapsed_ms": 1500,
    "accepted_count": 1
  }
}
```

四项分别等于 manifest 图片记录数、逐图尝试数之和、逐图耗时之和和 QA 通过数。任何手写汇总与重算值不一致都判为无效。

## `planning_only` 示例

纯策划仍保存完整计划链，但不声称成图：

```json
{
  "schema_version": "1.0",
  "run_id": "planning-example",
  "mode": "planning_only",
  "tool_route": "none",
  "started_at": "2030-01-01T12:00:00Z",
  "finished_at": "2030-01-01T12:00:00.250Z",
  "total_elapsed_ms": 250,
  "inputs": [
    {
      "path": "inputs/reference.png",
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  ],
  "brief": {
    "path": "brief.json",
    "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
  },
  "content_plan": {
    "path": "content_plan.md",
    "sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
  },
  "plan": {
    "path": "image_set_plan.json",
    "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  },
  "prompts": {
    "path": "prompts.md",
    "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  },
  "shots": [
    {
      "image_id": "01_hero",
      "attempt_count": 0,
      "elapsed_ms": 0,
      "attempts": []
    }
  ],
  "aggregate_metrics": {
    "shot_count": 1,
    "attempt_count": 0,
    "elapsed_ms": 0,
    "accepted_count": 0
  }
}
```

## 验证

从项目或 Skill 目录引用脚本：

```powershell
python <SKILL_DIR>/scripts/validate_plan.py <run-root>/image_set_plan.json
python <SKILL_DIR>/scripts/validate_delivery.py <run-root>
```

任一命令非零退出时，按诊断修复记录或文件；不得删减证据来绕过失败。
