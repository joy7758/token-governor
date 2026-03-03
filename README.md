# 🌌 天将 TianJiang — LLM Agent Runtime Controller (Token Governor)

`TianJiang` 是一个面向 LLM Agent 的运行时控制层，用于控制 token 预算、限制 fallback 重试、记录运行审计，并支持自动策略推荐与多模式优化。

## 为什么使用

- 控制成本：限制 token 预算，减少无效消耗
- 保持稳定：限制 fallback 链路，避免失控重试
- 可量化对比：自动输出 baseline vs governor 报告（JSON/Markdown/PNG/HTML）
- 可扩展优化：支持缓存、上下文压缩、工具选择、模型路由等策略开关

## 快速开始

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

## 基础运行

### Baseline

```bash
python main.py --mode baseline --limit 20 --out-file metrics/data/baseline.jsonl
```

### Governor（自动策略）

```bash
python main.py \
  --mode governor \
  --drive-mode auto \
  --auto-strategy \
  --limit 20 \
  --out-file metrics/data/governor.jsonl
```

### 生成对比报告

```bash
python -m metrics.report \
  --baseline metrics/data/baseline.jsonl \
  --governor metrics/data/governor.jsonl \
  --outdir metrics/reports/compare-real \
  --interactive
```

## 自动更新的对比结果

### 图表

<!-- CHART_IMAGE_START -->
![LLM Token Savings and Cost Optimization Results / LLM 成本节省对比图](metrics/reports/compare-real/comparison_summary.png)
<!-- CHART_IMAGE_END -->

### 指标区块（由脚本自动覆盖）

<!-- REAL_METRICS_START -->
运行以下命令后，脚本会自动写入最新实测指标与参考区间：

```bash
bash scripts/run-all-and-update.sh
```
<!-- REAL_METRICS_END -->

> 说明：该区块是 README 唯一指标事实源。请勿手工追加第二份静态结论，避免重复和冲突。

## 驾驶模式（Drive Mode）

| 模式 | 目标 | 典型倾向 |
| --- | --- | --- |
| `auto` | 自动推荐 | 按任务特征动态组合策略（默认不自动启用 rocket） |
| `eco` | 成本优先 | 更强压缩与裁剪，降低 token 消耗 |
| `comfort` | 平衡优先 | 成本、质量、延迟折中 |
| `sport` | 质量优先 | 更强检索与上下文能力 |
| `rocket` | 能力优先 | 高性能组合，不计成本优先精度 |

示例：

```bash
python main.py --mode governor --drive-mode eco --limit 10
python main.py --mode governor --drive-mode rocket --enable-agentic-plan-cache --limit 10
```

## 一键全流程（推荐）

```bash
bash scripts/run-all-and-update.sh
```

该脚本会依次完成：

1. 运行 baseline + 多个 governor 模式
2. 生成 `metrics/reports/compare-real/` 对比报告
3. 构建模型画像 `metrics/profiles/model_profiles.json`
4. 自动更新 README 指标区块

## 模型画像（可选）

```bash
python scripts/build_model_profiles.py \
  --input "metrics/data/*-real.jsonl" \
  --output metrics/profiles/model_profiles.json
```

在自动模式中使用画像：

```bash
python main.py \
  --mode governor \
  --drive-mode auto \
  --model-profile metrics/profiles/model_profiles.json \
  --limit 20
```

## 项目结构

```text
.
├── baseline/        # baseline agent
├── governor/        # runtime guard and strategies
├── metrics/         # tracker and report
├── scripts/         # automation scripts
├── docs/            # design docs
├── main.py          # CLI entry
└── README.md
```

## 文档导航

- [路线图（Governor v0.x+）](docs/governor-v0x-roadmap.md)
- [策略面板 UI 规范](docs/strategy-panel-ui-spec.md)
- [模型画像 Schema](docs/model-profile-schema.md)
- [变更记录](CHANGELOG.md)
- [贡献指南](CONTRIBUTING.md)

## FAQ

**Q: 自动模式会覆盖我手动传入的参数吗？**
A: 不会。显式 CLI 参数优先级最高。

**Q: 为什么某些模式 token 反而更高？**
A: 策略组合会在成本、质量、稳定性之间权衡；请以报告中的多指标（success/latency/p95）一起评估。

**Q: Rocket 模式中的 APC 节省是保证值吗？**
A: 不是。研究数据只作方向参考，实际收益取决于任务分布和缓存命中率。

## License

TianJiang Non-Commercial License v1.0

- 非商用场景可免费使用
- 商用场景需要先购买商业授权或与作者达成合作协议
- 详细条款见 [LICENSE](LICENSE)
