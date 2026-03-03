# Governor v0.x+ 进阶路线设计（Token 节省 20%+）

## 1. 目标

在保持任务成功率和时延稳定的前提下，将当前约 5.8% 的平均 token 节省提升到 20%+，并建立可持续迭代的运行时优化框架。

核心约束：

- 成功率下降不超过 2 个百分点
- 平均延迟上升不超过 10%
- 结果可解释、可审计、可回滚

## 2. 现状与问题

现状（真实 20 任务）：

- `baseline.mean_token = 1704.3`
- `governor.mean_token = 1604.9`（约 -5.8%）
- 成功率均为 100%
- `governor.p95_token` 高于 baseline

关键问题：

- 目前工具选择几乎是 no-op
- 上下文管理没有实质压缩
- 没有缓存层（prompt/semantic）
- 没有尾部任务（P95）专项治理策略

## 3. 分阶段路线

### 阶段 A（1-2 周）：低风险快收益

目标：token 再降 10-30%

范围：

1. Prompt Cache（完全相同命中）
2. Smart Tool Selector v1（关键词+embedding Top-K）
3. Context Compression v1（摘要替代全量历史）

落地改造：

- `governor/tool_selector.py`：
  - 从 `return all_tools` 升级为 `Top-K`
  - 默认 `k=2/3`，可配置
- `governor/context_manager.py`：
  - 新增 `summarize_history(history, max_chars)` 接口
  - 超阈值时摘要，否则原样
- 新增 `governor/cache.py`：
  - key = `hash(model + prompt + toolset_signature)`
  - value = final answer + token usage + timestamp

验收指标：

- `mean_token` 相比当前 governor 再降 >= 10%
- 成功率 >= 98%
- `cache_hit_rate` >= 15%（对重复任务集）

### 阶段 B（2-4 周）：系统级优化

目标：总节省 30-50%

范围：

4. RAG + Context Pruning（仅注入相关片段）
5. Semantic Cache（近似语义命中）
6. Agentic Plan Cache（跨任务执行计划模板复用）
7. Token Attribution Pruning（去低价值上下文）

落地改造：

- 新增 `governor/retriever.py`：
  - `retrieve(query, k)` 返回相关文档
  - 加一层 `prune_context(chunks)` 过滤冗余片段
- 新增 `governor/semantic_cache.py`：
  - embedding + 相似度阈值（如 0.9）
- 新增 `governor/plan_cache.py`：
  - 复用高相似任务的执行计划模板与工具路径
- 在 `governor/agent.py` 注入策略链：
  - prompt 构造前先走 semantic cache
  - 再走 agentic plan cache
  - 未命中再走 RAG + pruning

验收指标：

- `mean_token` 相比 baseline 降 >= 30%
- `p95_token` 不高于 baseline 的 110%
- `semantic_cache_hit_rate` >= 20%

### 阶段 C（4-8 周）：高强度协同优化

目标：总节省 50%+（看任务结构）

范围：

7. Hybrid Prompt Compression（动态压缩策略）
8. Sliding Window + Dynamic Memory Buffer
9. Model Routing（任务级别轻重模型分流）

落地改造：

- 新增 `governor/router.py`
  - 低风险/结构化任务走轻模型
  - 高复杂任务走强模型
- `governor/context_manager.py`
  - 窗口化保留近期强相关上下文
  - 历史长期记忆用摘要块替代

验收指标：

- `mean_token` 相比 baseline 降 >= 50%（特定数据集）
- 成功率下降 <= 2pp
- 延迟变化可控（SLA 内）

## 4. 推荐技术架构

请求处理链（建议）：

1. 预算检查（Budget Guard）
2. Prompt Cache 检查
3. Semantic Cache 检查
4. Tool Selector（Top-K）
5. Context Compression / RAG Pruning
6. Model Routing
7. 推理执行
8. 结果记录（metrics + trace）
9. 回写缓存

## 5. 关键伪代码

```python
def guarded_run(prompt, task_id):
    if budget.exceeded():
        raise BudgetExceeded

    if prompt_cache.hit(prompt):
        return prompt_cache.get(prompt)

    sem_hit = semantic_cache.search(prompt, threshold=0.9)
    if sem_hit:
        return sem_hit

    tools = tool_selector.select(prompt, all_tools, k=3)
    context = retriever.retrieve_and_prune(prompt, k=5)
    history = context_manager.compress(history_store.get(task_id))

    model = router.pick(prompt, context, policy="cost_first")
    result = run_llm(model, prompt, context, history, tools)

    metrics.log(result)
    prompt_cache.put(prompt, result)
    semantic_cache.put(prompt, result)
    return result
```

## 6. A/B 实验规范

每次策略上线都做 A/B：

- A: baseline（不启用该策略）
- B: governor + 新策略

固定统计项：

- `mean_token`
- `p50_token`
- `p95_token`
- `success_rate`
- `mean_latency`
- `fallback_trigger_rate`
- `cache_hit_rate`（如适用）

报告产出：

- `metrics/reports/<date>-<strategy>/comparison.json`
- `comparison.md`
- `comparison_summary.png/.html`

## 7. 风险与回滚

主要风险：

- 过度压缩导致信息缺失
- cache 污染导致回答偏差
- router 误判导致质量波动

回滚策略：

- 每个策略都有独立开关（feature flag）
- 支持按任务类型灰度启用
- 任一指标超阈值立即回退到前一策略集

## 8. v0.x 实施清单（建议优先级）

P0：

- `tool_selector` Top-K 化
- `context_manager` 摘要化
- `prompt cache` 接入

P1：

- semantic cache
- RAG pruning
- 报告中增加 cache 命中率指标

P2：

- model routing
- attribution pruning
- memory buffering

---

执行建议：先完成阶段 A 的 3 个 P0 项，再跑一轮 20 任务对比。如果 `mean_token` 降幅未达 15%，优先推进语义缓存而不是先做复杂路由。
