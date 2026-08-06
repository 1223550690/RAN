# `final_version` 集成变更记录

本文件记录 `final_version` 上每次集成工作的范围。详细报告保存在 `docs/integration/reports/`，历史记录不覆盖。

## 2026-08-02

- 冻结 RAN 合同 V1，见 `frozen_contracts_v1_zh.md`。
- 开始建立固定场景规模的多 Agent 编排基底。
- 详细变更见 `reports/2026-08-02_01_multi_agent_foundation_zh.md`。

## 2026-08-03

- 新增五个开发板块的项目会议评估材料。
- 记录各板块职责、目标要求、静态进度、集成建议和核心逻辑问题。
- 为各板块及跨模块核心逻辑问题补充编号对应的参考答案。
- 详细内容见 `project_meeting_five_part_review_zh.md`。

## 2026-08-04

- 在工作树根目录新增 `IDEA.md` 项目交接文件。
- 汇总项目背景、Python/Java边界、冻结合同、五成员分支进度、Agent/LLM导航设计、当前工作树风险和建议接手顺序。
- 明确区分未提交脚手架、静态审查结论、尚未实现内容和未运行验证事项。

## 2026-08-05

- 基于 `editor/data/scenes/bristol_topology.json` 与原始俯瞰图生成屋顶移除式 2.5D 地图背景。
- 保持正交俯视构图，强化建筑内外墙、门洞、入口和环境光遮蔽；修正 Royal Fort 三块开放绿地被误渲染为围墙的问题。
- 新增 `outputs/scene_bristol_bg_2000_2p5d.png`，未覆盖原图，尚未接入模拟预览页面。

## 2026-08-05

- 实现 Agent 状态生成完整链路(LLM/模板 → 语义解析 → 导航 → 移动 → 意图提交 → RAN → 完成事件 → 再规划)。
- 新增 `simulation/agent/` 子系统与 `simulation/orchestrator.py`;`ran/scenario.py` 增加 `submit_intent()` 运行中提交意图;合同与 schema 按默认字段向后兼容扩展。
- 已授权执行验证:模板模式端到端闭环通过(tick 52 全部 Agent DONE、业务全 COMPLETED、字节守恒)。
- 详细变更见 `reports/2026-08-04_01_agent_state_generation_zh.md`。

## 2026-08-06

- 实时预览增加路由规划可视化:Agent 规划路线(虚线)、终点标记、历史轨迹、Agent 摘要面板(前端 ScenePreview/livePreview,后端 AgentSnapshot.waypoints)。
- 导航子系统针对 Bristol 2000×2000 大地图重构:
  - 通道(Channel)抽象:`Portal.channel_id` 数据合同 + 几何合并兜底(开口段共线重叠自动归并),编辑器多视角门在全局收敛为唯一通道边界。
  - 分层网格:建筑内局部网格(细 cell)、跨建筑/户外粗网格(cell≈6.6m)、网格空间索引与连通性预检(flood fill)。
  - 共享边界无墙:相邻室内区域共享边界不建墙,非共享边界扣除门开口。
  - 修复:BFS 门序列回溯、open_space/outside 归一化、area 级门坐标转换。
- 性能:Bristol 单条规划 43.5s → 0.13-2.5s;potions 室内回归毫秒级,端到端闭环通过。
- 详细变更见 `reports/2026-08-06_01_channel_and_bristol_navigation_zh.md`。

## 2026-08-06 (续)

- LLM 自动模式实调验证(DeepSeek `deepseek-v4-flash`,OpenAI 兼容接口):
  - 单学生 Bristol 场景,同建筑内转移(Block 09 → Conference Room)全链路通过:
    LLM 决策 → 语义解析 → 规划 → 移动 → 意图提交 → RAN 处理 → 完成 → 再决策。
  - 新增 `--llm-same-building`:目的地 catalog 限制在当前建筑内,并排除当前所在区域
    (代码层约束,不依赖 LLM 遵守);`configs/agents/llm_single_student_bristol.json` 单学生配置。
  - 修复:LLM 虚构目标(强化 system prompt + 语义索引模糊匹配兜底:独立词匹配,
    区域优先、层级最浅优先、唯一命中采用);同建筑过滤大小写;`by_name` 补注册完整
    层级路径;DeepSeek `response_format=json_object` 要求 prompt 含 "json"(已满足)。
  - 失败重试验证:偶发失败 1 次后 LLM 重新决策自动恢复。

## 2026-08-06 (续二)

- 五成员分支合并完成(zhiqian/3gpp、haoyu_amf、xizhe_pdcp/rlc、boyu/area-b、tr22068/scheduling-tests),集成分支 `integration/merge` 已推送 GitHub。
- 集成适配:恢复 RanUploadScenario 兼容层、兼容层升级 xizhe 实体管道、boyu 合同校验适配(可选字段原则)、tr22068 调度算法 + PHR 向后兼容合入。
- 合并后验证:unittest 131/131、pytest 89/89、Bristol Agent 闭环正常。
- 文档:`integration_branch_overview_zh.md`(集成分支总览)、`tr22068_merge_report_zh.md`(tr22068 合并报告)。
