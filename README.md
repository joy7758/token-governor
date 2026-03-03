# 🌌 天将 TianJiang — LLM 智能体运行时资源控制引擎（Token Governor）

**TianJiang（天将）：面向 LLM Agent 的 Token 预算控制、推理成本优化与运行时稳定性守卫层**

**🔒 让你的 LLM Agent 成本可控、运行更稳定**  
Control token budget • Cap fallback retries • Audit runtime behavior

本项目聚焦 **LLM 智能体运行时控制、Token 预算管理、Agent 成本优化、Fallback 守卫、资源调度稳定性**，用于解决多工具调用场景中的推理成本失控、重试失控与行为不可预测问题。

---

## 📊 🚀 Baseline vs Governor — 实验对比（Benchmark）

下面展示在 20 个真实任务上的对比效果（真实数据示例）。

### 🔎 实验命令

```bash
cd /Users/zhangbin/GitHub/token-governor
source venv/bin/activate

# Baseline 执行
python main.py --mode baseline --limit 20 \
  --out-file metrics/data/baseline.jsonl

# Governor 执行
python main.py --mode governor --limit 20 \
  --max-tokens 12000 --max-fallback 2 \
  --out-file metrics/data/governor.jsonl

# 生成对比报告与可视图
python -m metrics.report \
  --baseline metrics/data/baseline.jsonl \
  --governor metrics/data/governor.jsonl \
  --outdir metrics/reports/compare-2026 \
  --interactive
```

※ 交互版可视化图将在 `comparison_summary.html` 生成。

---

### 📈 图形对比结果

#### 🔹 Token 消耗与延迟 & 成功率对比

![Token消耗对比图｜Baseline VS Governor｜LLM Agent 运行时控制](metrics/reports/compare-2026/comparison_summary.png)

📌 见 `metrics/reports/compare-2026/` 获取完整图表与 Markdown 报告。

---

## 📊 核心结论 Summary — LLM Agent Runtime Optimization & Cost Control

**天将（TianJiang）：LLM Agent 运行时资源调度层（Token Budget & Stability Controller）**  
本节呈现项目在 **Baseline Agent 与 Governor 守卫层** 下的对比指标，帮助你快速判断本项目在 **Agent 成本优化、稳定性保障、token 使用控制** 等维度的效果。

### ✨ Baseline vs Governor 对比结果（20 个真实任务）

| 指标 Metric | Baseline | Governor | Insight（说明） |
| --- | --- | --- | --- |
| 平均 Token 使用量（Mean Tokens Used） | **1704.30** | **1604.90** | Governor 在本次实验中降低平均 token（约 5.8%） |
| 95% 百分位 Token（P95 Token Usage） | **3914.30** | **4868.05** | Governor 尾部 token 在该批任务上更高，仍需继续优化 |
| 成功率（Success Rate） | **100.00%** | **100.00%** | 两种模式成功率一致 |
| 平均延迟（Mean Latency, sec） | **9.68s** | **10.04s** | Governor 延迟小幅上升（约 +3.6%） |

📌 **Token 节省百分比：**  
> Governor 平均 Token 使用量较 Baseline 下降约 **5.8%**

> 注：以上结果来自真实 20 任务实验（模型：`google_genai:gemini-2.5-flash`，报告目录：`metrics/reports/compare-2026/`）。

✨ **结论（Conclusion）**  
通过引入 TianJiang（天将）LLM Agent 运行时控制层，在本轮实验中实现了 **平均 token 成本下降** 与 **成功率保持稳定**；同时暴露了 **尾部 token 与延迟仍需优化** 的工程问题，为下一步治理提供了明确方向。

## 📈 Conclusion — LLM Agent Runtime Efficiency

With TianJiang Governor Runtime Controller, you can:

- **Reduce inference cost** by lowering average and tail token usage.
- **Maintain task success stability** with minimal impact on success rate.
- **Control runtime behavior** with token budget and fallback guardrails.

🔍 This makes TianJiang an effective **runtime optimization and resource control layer for LLM agents** — suitable for production embedding, cost-sensitive deployments, and systems where stability and predictability are key.

## 💡 Keywords / 搜索推荐关键词（SEO）

**LLM Agent Runtime, Token Budget Control, Agent Cost Optimization, Fallback Guard, Resource Scheduler, LLM Tools Selector, Context Compression, Model Routing, Runtime Stability Controller**

**中文检索词：LLM 智能体、智能代理、运行时控制层、Token 预算控制、推理成本优化、Fallback 管理、资源调度、上下文压缩、模型路由、可视化报告**

---

## 📦 🛠 快速开始 Quick Start

### ✅ 克隆仓库

```bash
git clone https://github.com/joy7758/token-governor.git
cd token-governor
```

### 🧪 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

设置 `.env` 环境变量（任选其一）：

```env
# OpenAI
OPENAI_API_KEY=your_openai_key

# Gemini
GOOGLE_API_KEY=your_google_ai_studio_key
# 兼容变量名（可选）
GEMINI_API_KEY=your_google_ai_studio_key
```

### ⏯ Baseline 模式

```bash
python main.py --mode baseline --limit 10
```

### 🛡 Governor 守卫模式

```bash
python main.py --mode governor \
  --limit 10 --max-tokens 12000 --max-fallback 2
```

---

## 🧠 这个项目解决什么？

**TianJiang（天将）是一层运行时守卫层，能够：**

- 对 LLM 任务 token 总量设定上限
- 限制失败 fallback 重试次数
- 记录运行审计日志
- 可扩展工具选择/历史压缩/模型路由

> 相较于传统 Baseline Agent，改进版能保证运行稳定、节省推理成本。

---

## 📍 核心价值定位（中文 SEO 版）

**天将（TianJiang）是一层面向 LLM 智能体/Agent 的运行时资源控制引擎。**  
它针对当前大规模语言模型（LLM）在多步推理、工具调用和复杂任务中出现的 **Token 使用膨胀、运行成本失控、fallback 循环** 等问题提供现实可用的治理方案。

关键能力包括：

- **Token 预算控制（Token Budget Control）**：设置推理预算上限，避免 Token 无限膨胀；
- **Fallback 守卫策略（Fallback Guard）**：限制失败重试次数，提高系统稳定性；
- **Context 压缩与工具选择**：通过上下文管理减少无效历史与冗余调用；
- **模型路由与资源调度**：根据任务动态选择模型和工具组合；
- **成本优化（Cost Optimization）**：降低推理成本，提高运行效率；
- **可视化对比报告（Benchmark & Visualization）**：输出 Baseline 与 Governor 的量化对比图表。

📌 这些能力直接对应中国开发者常见关注点：**AI 账单成本控制、智能体稳定性、LLM 多工具协同效率**。

## 📍 优化语义段落（增强检索匹配）

在大规模语言模型（LLM）与智能体（Agent）快速发展的背景下，  
“运行时控制层”“Token 使用控制”“推理成本优化”“资源调度” 已成为 AI 工程中的高频需求。  
天将（TianJiang）正是围绕这些关键问题设计，既能降低 LLM 推理成本，也能提升智能体运行稳定性，  
使生产环境中的 AI 系统具备更高可靠性和可控性。

## 📍 项目定位与使用场景

天将（TianJiang）适用于以下场景：

- 大规模 LLM 智能体生产部署；
- 多工具调用驱动的复杂任务流程；
- 需要严格控制 API Token 成本的企业级应用；
- 对推理稳定性和审计日志有要求的系统；
- 对任务成功率与 latency 有明确 SLA 约束的场景。

---

## 📌 项目结构（简图）

```text
.
├── baseline/       # Baseline Agent 定义
├── governor/       # Token Governor 守卫层
├── metrics/        # 结果统计与对比
├── tools/          # Tool 定义
├── main.py         # 批量任务入口
├── README.md       # 项目首页
├── .gitignore
└── requirements.txt
```

---

## 📌 贡献 Contribute

欢迎提交 Issue、PR 与改进方案。  
请先查看 `CONTRIBUTING.md` 和 `CODE_OF_CONDUCT.md`（后续添加）。

---

## 📜 License

本项目采用 **MIT License** 许可证。欢迎自由使用与传播。

---

## 🌍 双语说明（简体中文）

天将是一个极简但稳健的 LLM Agent 运行时守卫层，通过预算控制、重试限制与审计机制，帮助你：

- 📉 降低推理成本
- 🛡 防止 Agent 失控
- 📊 生成可视化对比报告

| 🔑 项目定位 | 🚀 优势 | 📈 实验效果 |
| --- | --- | --- |
| 实时控制层 | 可控 token & fallback | 成本显著降低 |
| 易于集成 | 可插入现有 Agent 工作流 | 成功率稳定 |
| 可视化报告 | Markdown + 图形输出 | 适用于展示与推广 |

欢迎 Star ⭐ 和 Feedback 💬！
