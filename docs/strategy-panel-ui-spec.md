# 策略选择面板（Web 配置页）提案

## 页面目标

为用户提供 4 个可视化策略套餐（`light / balanced / knowledge / enterprise`）+ 自动推荐模式（`auto`），并支持细粒度参数覆盖，确保 UI 配置与 CLI 一一对应。

## 面板结构

1. 顶部说明区：解释“策略会影响 token/成功率/延迟”。
2. 策略卡片区：4 张套餐卡，单选。
3. 模式切换区：`Auto Recommend` / `Manual`。
4. 高级参数区：开关+数值输入，可覆盖套餐默认值。
5. CLI 预览区：实时显示可复制命令。
6. 指标预估区：展示预期 token/成功率/延迟方向。

## 自动推荐（Auto Recommend）

自动模式根据任务元信息推荐套餐，并保留人工覆盖能力。

当前后端启发式输入：

- 历史 token 规模（`history_tokens`）
- 工具调用数量（`tool_calls`）
- 外部检索需求（`external_query`）
- 语义重复度（`semantic_similarity_score`）

自动推荐输出：

- 推荐套餐（`balanced/knowledge/enterprise` 等）
- 推荐分数（`score`）
- 推荐理由（`reasons`）
- 特征快照（`features`）

CLI：

```bash
python main.py --mode governor --auto-strategy --limit 20
```

兼容写法（保留）：`--opt-strategy auto`。

## 套餐卡片定义

### 1) Light

- 适用：低门槛成本控制
- 默认开关：
  - `enable_context_compression=false`
  - `enable_smart_tool=true`
  - `enable_rag=false`
  - `enable_context_pruning=false`
  - `enable_semantic_cache=false`
  - `enable_agentic_plan_cache=false`
  - `enable_model_routing=false`
- 默认参数：
  - `tool_top_k=3`
  - `history_summary_chars=400`
- 预期指标：
  - token：轻微下降
  - 成功率：稳定
  - 延迟：稳定

### 2) Balanced

- 适用：通用生产配置
- 默认开关：
  - `enable_context_compression=true`
  - `enable_smart_tool=true`
  - `enable_rag=false`
  - `enable_context_pruning=false`
  - `enable_semantic_cache=false`
  - `enable_agentic_plan_cache=false`
  - `enable_model_routing=false`
- 默认参数：
  - `tool_top_k=3`
  - `history_summary_chars=800`
- 预期指标：
  - token：中度下降
  - 成功率：稳定
  - 延迟：轻微变化

### 3) Knowledge

- 适用：知识密集 / 检索驱动场景
- 默认开关：
  - `enable_context_compression=true`
  - `enable_smart_tool=true`
  - `enable_rag=true`
  - `enable_context_pruning=true`
  - `enable_semantic_cache=false`
  - `enable_agentic_plan_cache=false`
  - `enable_model_routing=false`
- 默认参数：
  - `tool_top_k=3`
  - `history_summary_chars=1000`
- 预期指标：
  - token：显著下降
  - 成功率：稳定
  - 延迟：轻度上升

### 4) Enterprise

- 适用：企业级全量控制
- 默认开关：
  - `enable_context_compression=true`
  - `enable_smart_tool=true`
  - `enable_rag=true`
  - `enable_context_pruning=true`
  - `enable_semantic_cache=true`
  - `enable_agentic_plan_cache=true`
  - `enable_model_routing=true`
- 默认参数：
  - `tool_top_k=3`
  - `history_summary_chars=1200`
- 预期指标：
  - token：最大下降
  - 成功率：高稳定
  - 延迟：可控提升

## UI 字段到 CLI 参数映射

| UI 字段 | CLI 参数 |
| --- | --- |
| 自动推荐模式 | `--auto-strategy` |
| 驾驶模式（Drive Mode） | `--drive-mode <auto|eco|comfort|sport|rocket>` |
| 策略套餐（手动） | `--opt-strategy <light|balanced|knowledge|enterprise>` |
| 上下文压缩 | `--enable-context-compression` / `--disable-context-compression` |
| 智能工具选择 | `--enable-smart-tool` / `--disable-smart-tool` |
| RAG | `--enable-rag` / `--disable-rag` |
| 上下文剪枝 | `--enable-context-pruning` / `--disable-context-pruning` |
| 语义缓存 | `--enable-semantic-cache` / `--disable-semantic-cache` |
| Agentic Plan Cache | `--enable-agentic-plan-cache` / `--disable-agentic-plan-cache` |
| 模型路由 | `--enable-model-routing` / `--disable-model-routing` |
| Tool Top-K | `--tool-top-k <int>` |
| 历史摘要字符上限 | `--history-summary-chars <int>` |
| 输出文件 | `--out-file <path>` |

## 驾驶模式（Drive Mode）映射

| Drive Mode | 目标 | 典型配置 |
| --- | --- | --- |
| `auto` | 动态推荐 | task-feature recommendation（默认不自动启 rocket） |
| `eco` | 成本优先 | `light` + compression + smart tool |
| `comfort` | 平衡优先 | `balanced` + semantic cache |
| `sport` | 质量优先 | `knowledge` + RAG + semantic cache |
| `rocket` | 能力优先 | `enterprise` + semantic/plan cache + model routing |

## Rocket 模式文案建议（带研究背书）

推荐用于 UI 卡片 hover/详情弹窗：

```text
Rocket（火箭模式）
- 极致质量与能力优先，不计成本
- 启用语义缓存、计划缓存（Agentic Plan Cache）、模型路由等高性能策略
- 在公开 APC 研究中，报告了约 45%+ 成本下降与 20%+ 延迟下降量级（特定评测条件）
- 结果依赖任务分布与缓存命中率，实际收益以本地实验为准
```

推荐附带链接：

- https://arxiv.org/abs/2506.14852
- https://arxiv.org/html/2506.14852v1

## CLI 示例（UI 导出）

### Balanced（默认）

```bash
python main.py --mode governor \
  --opt-strategy balanced \
  --limit 20 \
  --out-file metrics/data/governor.jsonl
```

### Auto（推荐）

```bash
python main.py --mode governor \
  --drive-mode auto \
  --limit 20 \
  --out-file metrics/data/governor.jsonl
```

### Enterprise + 覆盖参数

```bash
python main.py --mode governor \
  --drive-mode rocket \
  --enable-agentic-plan-cache \
  --tool-top-k 4 \
  --history-summary-chars 1500 \
  --limit 20 \
  --out-file metrics/data/governor.jsonl
```

## 前端交互建议

- 卡片单选后立即更新“生效配置预览”。
- 高级参数有改动时，展示“覆盖了套餐默认值”提示。
- CLI 预览支持一键复制。
- 给每个开关提供 tooltip，说明对 token/成功率/延迟的常见影响方向。
- 当用户选择 `auto` 时，在卡片上明确提示“默认不自动启用 rocket 高成本档位”。
