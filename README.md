# Token Governor — LLM 推理成本优化与策略治理引擎
**Token Governor 提供高效的 LLM 推理成本控制、策略推荐、Token 节省与自动化对比分析。**  
*Token Governor is an inference cost optimization and adaptive strategy governance engine for LLM workloads.*

<div align="center">
  <img src="https://img.shields.io/github/license/joy7758/token-governor" alt="License" />
  <img src="https://img.shields.io/github/stars/joy7758/token-governor" alt="Stars" />
</div>

---

## 🧠 一、简介 / Introduction
**中文说明：**  
Token Governor 是一套面向生产级 LLM 推理阶段的成本与策略治理框架，支持 Token 节省、动态策略推荐、模型路由、缓存与压缩等多种优化策略组合。

**English Description:**  
Token Governor helps reduce inference cost and improve runtime stability by combining strategy profiles, drive modes, caching/compression controls, and automated benchmark reporting.

---

## 🚀 二、快速开始 / Quick Start

### 📦 Clone & Install / 克隆与安装
```bash
git clone https://github.com/joy7758/token-governor.git
cd token-governor

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

配置环境变量（任选其一）：
```bash
export OPENAI_API_KEY="your_openai_key"
# 或
export GOOGLE_API_KEY="your_google_key"
```

### 📊 Run Baseline / 基础测试
```bash
python main.py --mode baseline --limit 20 --out-file metrics/data/baseline.jsonl
```

### 🛡️ Run Governor / 策略控制
```bash
python main.py --mode governor --drive-mode eco --limit 20 --out-file metrics/data/governor.jsonl
```

### 📈 Generate Report / 生成对比分析
```bash
python -m metrics.report \
  --baseline metrics/data/baseline.jsonl \
  --governor metrics/data/governor.jsonl \
  --outdir metrics/reports/compare-real \
  --interactive
```

---

## ✨ 三、核心功能 / Features

| Feature | 说明 | Description |
| --- | --- | --- |
| 多驱动模式 | Eco / Auto / Comfort / Sport / Rocket | Drive modes for different cost-vs-quality trade-offs |
| 自动策略推荐 | 自动分析任务并推荐最优策略 | Adaptive strategy recommendation |
| 多策略组合 | 缓存、压缩、路由、RAG 等 | Semantic cache, prompt compression, model routing, RAG |
| 自动报告生成 | JSON / Markdown / 可视化图表 | Automated comparative reporting |
| CLI 参数控制 | 丰富的命令行配置选项 | Command-line interface with rich options |
| 模型画像支持 | 支持 `--model-profile` 驱动推荐偏置 | Profile-guided auto strategy hints |

---

## 🧪 四、使用示例 / Usage Examples

### 🚗 Eco 模式（最省 Token）
```bash
python main.py --mode governor --drive-mode eco --limit 20
```

### 🤖 Auto 模式（智能推荐）
```bash
python main.py --mode governor --drive-mode auto --auto-strategy --limit 20
```

### 🚀 Rocket 模式（高质量输出）
```bash
python main.py --mode governor --drive-mode rocket --enable-agentic-plan-cache --limit 20
```

---

## 📊 五、对比图与实时指标 / Metrics & Visuals

<!-- CHART_IMAGE_START -->
![LLM inference cost and token savings comparison / LLM 推理成本与 Token 节省对比图](metrics/reports/compare-real/comparison_summary.png)
<!-- CHART_IMAGE_END -->

<!-- REAL_METRICS_START -->
Baseline vs Optimized Results / Baseline 与优化策略对比  
(自动生成，可通过 `scripts/update_readme_metrics.py` 重新填充)
<!-- REAL_METRICS_END -->

---

## 📍 六、参数说明 / CLI Reference

| 参数 / Parameter | 说明 / Description | 默认值 / Default |
| --- | --- | --- |
| `--mode` | 运行模式：`baseline` / `governor` | `baseline` |
| `--drive-mode` | 驾驶模式：`auto/eco/comfort/sport/rocket` | `None` |
| `--opt-strategy` | 手动策略：`light/balanced/knowledge/enterprise` | `balanced` |
| `--auto-strategy` | 启用自动策略推荐 | `False` |
| `--limit` | 任务数量限制 | `None`（全部默认任务） |
| `--model` | 模型选择（如 `auto`, `openai:gpt-4o-mini`） | `auto` |
| `--max-tokens` | Governor 每任务累计 token 预算 | `12000` |
| `--max-fallback` | Governor 最大 fallback 次数 | `2` |
| `--out-file` | 结果 JSONL 输出路径 | `None` |
| `--model-profile` | 模型画像 JSON 路径 | `None` |

---

## 🧠 七、典型场景 / Use Cases

**中文：**
- 企业级 LLM 推理成本优化
- 多模型推理策略治理
- Agent 智能体推理优化
- 自动化对比实验与报告

**English:**
- Enterprise LLM inference cost control
- Multi-model strategy governance
- Agent runtime optimization
- Automated benchmarking and reporting

---

## ❓ 八、常见问题 / FAQ

**Q1: 什么是 Drive Mode？**  
A: Drive Mode 用于在成本与质量之间做权衡，例如 Eco 模式优先节省 Token，而 Rocket 模式优先输出质量。

**Q2: Auto 和 Comfort 有何区别？**  
A: Auto 是任务特征驱动的动态推荐路径；Comfort 是固定平衡型档位。

**Q3: 自动模式会覆盖手动参数吗？**  
A: 不会。显式传入的 CLI 参数优先级更高。

---

## 👥 九、贡献指南 / Contributing

欢迎提交 Issue 和 Pull Request，细则见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 📜 十、许可证 / License

本项目使用 **TianJiang Non-Commercial License v1.0**：
- 非商用可免费使用
- 商用需要先购买授权或建立合作协议  
详见 [LICENSE](LICENSE)。

---

## 📚 十一、参考 / References

- [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
- [Awesome README Collection](https://github.com/matiassingers/awesome-readme)
- [standard-readme](https://github.com/RichardLitt/standard-readme)
