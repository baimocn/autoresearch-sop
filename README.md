# AutoResearch 出题 SOP（实战迭代版）

把论文变成**可持续优化、自动评分、真实留证、干净复现**的 AutoResearch 题目。

> **本仓库的特色：每条规则都对应一次真实事故，且配可执行工具。**
> 光有文档拦不住人——所以关键教训都做成了**会给出退出码的脚本**，在花钱之前拦住结构性不可行。

## 主干：五道不可跳级里程碑（M1→M5，任一不过不进入下一阶段）

```
M1 selection  论文身份/许可/方法级优化面/题库状态     ← 不写题面、不租卡      [零成本]
M2 pilot      B/R receipt/独立复算/效应与噪声结论      ← 不启动双轨          [<50 元]
M3 container  双镜像 digest/Hidden 隔离/完整 trial     ← 不计长跑时长
M4 long_run   两条独立血缘/闭合时长/机外快照与恢复     ← 不拼接旧轮次
M5 release    两份独立 QA/聚合共识/隐私报告/manifest   ← 任一失败即 NOT READY
```

```bash
python tools/milestone_gate.py --milestone M1 --title "<论文>" --repo <owner/name> ...
python tools/milestone_gate.py --milestone M2 --b <实测B> --r <实测R> --u <地盘> --reference-recomputed yes
python tools/milestone_gate.py --milestone M3..M5 --evidence-dir <专家证据目录>
# exit: 0=RECOMMEND  2=NEEDS_EVIDENCE  1=REJECT
```

**不做总分补偿**：热度/引用数/新颖性不能抵消许可、评测、资源或交付失败。

## 快速开始（新题目的 3 小时预检，成本 <50 元）

```bash
# ⓿ P0 静态筛查（零成本，30 分钟）——项目实测「14 道题 7% 成功率，死因 100% 在选题」
python tools/paper_screen.py --title "<论文标题>" --repo <owner/name>     --community-baseline <社区公认值> --reported-baseline <论文报告值> --delta-percent <声称增益%>     --n-benchmarks <主表benchmark数> --n-ablation <消融数> --metric-type physical
#   → FAIL 即弃题；MANUAL 逐条按提示实查（多为零成本静态检查）
# ① 零成本：只用论文数字做纸面预解（5 分钟）
python tools/feasibility_gate.py --from-paper --b <论文Baseline指标> --r <论文Reference指标> --u-hint <估计地板>
#   → 退出码 1 = 结构性不可行，直接换题，不要投算力

# ② 零成本：跨规模参数的数值反推（30 秒）
python tools/numeric_backsolve.py --official-value <官方硬编码值> \
    --data-stats "min=..,mean=..,max=.." --official-S 64 --target-S 128

# ③ 低成本：增益探针（1 seed × B/R，≤2× 单跑耗时）
#    用论文主打规模、官方脚本原样 → 拿到真实 B/R 数字

# ④ 再判定（有探针数字后）
python tools/feasibility_gate.py --from-probe --b <实测B> --r <实测R> --u <实测地板>
#   → 退出码 0 = 可行，进入正式 B/R；1 = 止损；2 = 信息不足
```

**只有 ① 和 ④ 都返回"可行"，才允许投入全 seed 正式协议。**

## 仓库结构

```
SKILL.md                     主入口（含 19 条执行规则，规则 11–19 来自实战教训）
references/
  production-sop.md          完整制作与验证流程（V01–V14）+ §2.5 五道里程碑、§4.3 探针优先、§5.6 官方仓复用清单
  field-lessons.md           ★ 实战教训 L1–L16（探针优先/判定预解/指标直译/数值反推/失败诊断顺序…
                                 ｜ + L11–L16：原生 NOP 环境、质检字段契约、哈希交叉验证、
                                 ｜   单一真源、交付物防护、清理安全顺序）
  failure-patterns.md        ★★ 跨题目失败模式（9 条题线 + 83 条事故的提炼：六类死因过滤器、
                                 ｜ Top5 根因、决策类错误清单、选题画像 2001 同构标准）
  gpu-budget.md              GPU 选型与预算（用实测报价、按分支期望报）
  source-policy.md           来源与口径（规范快照）
assets/checklist.md          制作与验证检查表（复制到题目证据目录逐项填）
scripts/
  gpu_budget.py              离线租价计算（用户提供报价）
  validate_skills.py         ★ 技能结构自检（防止文档漂移/密钥/本机路径进仓库）
tools/
  milestone_gate.py          ★★ 五道里程碑门禁（M1/M2 真实数据判定 → exit 0/1/2）
  nop_preflight.py           ★★ 原生 NOP 环境前置预检（GPU/runtime/buildx/compose/容量，
                                 exit 0=就绪 1=硬前提不满足 2=需人工确认）
  paper_screen.py            ★ P0 静态筛查（六类死因 + 玩具四判据 + 2001 同构，零成本 30 分钟）
  feasibility_gate.py        ★ 可行性闸门（判定门是否闭合，零 GPU）
  numeric_backsolve.py       ★ 跨规模参数数值反推（零 GPU）
  probes/                    诊断探针（从已存 rollout 算多指标，零 GPU）
  orchestrators/             自动化链（编排/回填/V09/定稿）
cases/
  README.md                  ★ 跨题线失败案例集（9 个案例：1851 baseline 口径 / 1430 trivial 反超 /
                                 ｜ 1352 混淆变量 / 1633 剂量恶化 / 2001 并发 / 2768 val 泄漏…）
  AutoRe0566-MNO-20261007.md ★ 单题完整案例（530 元，五个方向全部证伪）
```

## P0 零成本筛查清单（项目实测：93% 的题死在这一步）

来自 9 条题线的**统计规律**——**「死因 100% 在选题」**，而判据几乎全静态：

| 判据 | 工具/动作 | 拦住的真实案例 |
|---|---|---|
| 官方仓存在且非空壳 | `paper_screen.py`（GitHub API） | auto2027/1891/1918 |
| 有权重 ≠ 有训练代码 | `git clone --filter=blob:none` + grep `Trainer(` | — |
| **baseline 口径不可比** | 对照社区公认值（差值>15% 即查是否作者自跑） | **1851（差 23.8）** |
| 判据被混淆变量污染 | 六项对比（大小/行数/长度/source/id/md5） | 1352 |
| **trivial 基线反超** | 先跑 persistence / 最近邻 | **1430** |
| 广度 ≥3 benchmark | 主表统计 | 体检 61 道 |
| 增益幅度 ≥10% | 论文主图 | 2001 同构标准 |
| 指标是物理量（U 可构造） | 排除 LLM-judge / 胜率 | 官方口径 |

## 19 条执行规则（摘要）

**方法与环境（1–10）**：方法空间真实 / 基线公平 / 评分标定 / 证据完整 / 双镜像 / 移交合同 / 迭代时序 / 两组长程 / 最佳与轨迹 / 最终 NOP。

**实战新增（11–19）**：
- **11 探针优先**：正式 B/R 前必须跑 1 seed×(B+R) 探针（≤2× 单跑耗时），用论文主打规模；未通过禁止投入全 seed。
- **12 判定先算后跑**：用 1 seed + 地板 U 纸面预解 `R_norm∈[0.15,0.8]` 与 `Δ≥3σ_B` 是否存在可行交集；无交集即结构性不可行。
- **13 指标直译论文主张**：自造指标须写明与论文主张的映射；优先复用论文主图/主表指标。
- **14 跨规模参数须数值反推**：用官方已有规模的取值反推真实意图，不按文档字面重算。
- **17 NOP 环境前置预检**：跑原生 NOP 前实测五项前提（GPU 直通/runtime/buildx/compose/容量）；
  加速走试验层不改交付字节；容量不足用 trial 层 ignore 并留痕。
- **18 运行绑定与交付字节交叉验证**：运行前算全量哈希清单，交付时逐文件比对；任何字节改动须重跑 NOP。
- **19 同一事实单一真源**：锚点/口径全包只能一套生效声明；预登记值与生效值不一致须披露变更时间线。

## 和其他题目的连接方式

| 用途 | 做法 |
|---|---|
| 新题预检 | 直接用 `tools/feasibility_gate.py`（输入换成新题的 B/R/U） |
| 复用基础设施 | `tools/orchestrators/`、题包模板、评分器框架（数据无关） |
| 失败归因 | 对照 `cases/` 里的案例，判断属于"论文不成立"还是"配置错" |
| 教训累积 | 每次失败按 `references/field-lessons.md` 的格式追加 L 编号条目（附实测数字） |

## 案例：AutoRe0566（一次 530 元的教训）

**论文**：Learning Chaotic Dynamics in Dissipative Systems（NeurIPS 2022，MNO）
**结果**：未出成。五个方向全部证伪（详见 `cases/`）：

| 方向 | 结果 |
|---|---|
| 官方配对（FNO vs MNO，Re=500） | Δ=0.004，R_norm=0.039（需 ≥0.15） |
| 等容量（MNO@width128） | 0.174，**比 baseline 还差** |
| U-Net 作 Baseline | 塌缩/爆炸，不能充当合法基线 |
| Re=5000 + 半径标定（3 候选） | 最佳 0.2137，窗口要求 ≤0.1386（差 54%） |
| 扰动鲁棒性（论文 Figure 1 主张） | B/R 都稳定，**无区分度** |

**根因**：论文未公开 Re=5000 的完整配置；官方 Re=500 的默认配置下 Reference 都无法显著优于 Baseline（Δ=0.004）。
**我的失误**：未做判定预解与探针（本可省 ~480 元）；指标未直译论文主张；参数未做数值反推。
**已固化**：规则 11–14 + 两个可执行工具 + 本案例。

## 与上游 autoresearch-skills 的关系

本仓库的结构（五道里程碑、门禁三态、不做总分补偿、最小返修循环）**吸收自**
[`bosprimigenious/autoresearch-skills`](https://github.com/bosprimigenious/autoresearch-skills) v0.3.4
的 `shift-left-qa.md` 与选题目录（`candidate-gates.md` / `selection-gates.md`）。

**本仓库的增量是实测数据与可执行判定**：

| 上游提供 | 本仓库补充 |
|---|---|
| 门禁的**结构与语义**（M1–M5、三态、不补偿、返修循环） | **实测代价数据**（9 条题线：增益不足占 5/9；0566 亏 530 元其中 ~480 可拦） |
| 证据引用核对器（只查"文件有没有"） | **真实数据判定器**（`milestone_gate.py` 的 M1/M2 会算出判定门是否闭合，返回退出码） |
| 候选门的 7 类判据 | **六类死因过滤器 + 玩具四判据 + 2001 同构标准**（含可执行判法与 VIF/rho 类量化门槛） |
| skill 自检（frontmatter/name） | 自检 + **脱敏扫描**（密钥模式、本机绝对路径） |

**分工建议**：选题用上游的 `paper-discovery`（候选题硬门槛）→ 本仓库 `paper_screen.py` + `feasibility_gate.py` 做零成本判决 →
pilot 用 `milestone_gate.py M2` 判定 → 制作期按上游 `task-authoring/run-isolation/task-qa` 走 → 发布前用 `validate_skills.py` 自检。

## 授权与边界

本仓库是**方法论与工具**，不含任何具体论文的数据、模型或私有证据。使用时遵守各平台的规则与授权范围。
