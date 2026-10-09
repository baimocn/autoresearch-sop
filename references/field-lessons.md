# 出题实战教训（2026-10-07 一轮失败录 · MNO/NeurIPS2022）

> 来源：AutoRe0566（Learning Chaotic Dynamics in Dissipative Systems / neural-operator/markov_neural_operator）完整一轮出题实践。
> 结果：**未出成**（Re=500 全路线失败 → 转 Re=5000 → 首配置失败 → 半径扫描中）。
> 代价：~420 元 GPU + ~26h 墙钟。本文件只记**可复用的判断与流程改进**，不复述过程。
> 用法：这些条目在 P0/P1 阶段**强制**过一遍，作为 SOP §4.1 的补充检查项。

---

## L1 ★★★ 探针优先原则（本轮最贵的教训，约 200 元）

**错误做法**：选题确定后直接投入"完整协议"（全 seed × 全角色 × 官方超参），跑 12 小时才发现 B/R 无区分度。

**正确做法——三阶段递进，每阶段失败即止损**：

| 阶段 | 规模 | 耗时预算 | 通过条件 | 失败动作 |
|---|---|---|---|---|
| **P1.0 增益探针** | 1 seed × (B+R)，官方脚本原样 | **≤ 单跑耗时 × 2**（如 2h） | Δ 为正且量级足够（见 L2） | **立即停**，换切入点或换论文 |
| **P1.1 判定探针** | 2–3 seeds × (B+R) | ≤ 6h | Δ/σ_B ≥ 3 且 R_norm ∈ [0.15,0.8] | 调整协议（须记录）后重跑 P1.0 |
| P1.2 正式 B/R | 全 seed 集 | 1–2 天 | 全部门通过 | 返修 |

**硬规则**：
- **P1.0 未通过，禁止启动 P1.2**。不许以"再跑几个 seed 看看"为名扩大投入。
- P1.0 的 checkpoint 与日志**全部保留**（它可能就是 P1.2 的 seed 1，协议不变时可直接计入）。
- 探针阶段**必须用论文主打规模**（见 L3），不用"小一号"的替代设置。

## L2 ★★★ 判定条件必须"先算后跑"（本轮次贵的教训，约 150 元）

**错误做法**：跑完 B/R 才去算 R_norm 和 3σ_B，结果两者数学上**互斥**（R_norm 要求 B_mean 高 → seed 散布大 → 3σ 必挂）。

**正确做法**：在 P1.0 之前，用**已有数字**（1 个 seed 的 B/R + 真值侧地板 U）**预解**判定空间：

```
给定 U（真值侧地板，一次性算好）、B_1（首个 baseline seed）、R_1：
  ① R_norm 合规要求：B_mean ≥ (R_mean − 0.15·U)/0.85   （minimize 情形）
  ② 3σ 门要求：Δ = B_mean − R_mean ≥ 3σ_B，而 σ_B ≈ 由 seed 散布决定
  ③ 写出两个要求对"seed 散布"的依赖，检查是否存在**可行交集**
若不存在交集 → 该 (指标, 规模, 协议) 组合**结构性不可行**，立即改指标或改规模
```

**本轮实例**：`R_norm ≥ 0.15 需 B_mean ≥ 0.1475`（比 seed1 高 9%）；而达到这种 B_mean 需要 seed 间差异 ~0.012 → `3σ_B ≈ 0.035 > Δ ≈ 0.005–0.018` ✗ → **结构性死局**，跑之前就能算出来。

## L3 ★★ 指标必须直译论文的主张（根本性错误）

**错误做法**：论文的核心现象是**耗散性/稳定性**（Figure 1：无正则 baseline 崩坏、有正则回归吸引子），我却测"长期统计量离真值多近"——**两个不同的科学问题**。论文的主张**不蕴含**"MNO 的统计误差更小"。

**正确做法**——P1 阶段强制回答三个问题并写进协议：

| 问题 | 反例（本轮） |
|---|---|
| ① 论文的**一句话主张**是什么？ | "耗散性设计使学习的算子能留在吸引子上" |
| ② 我的指标是否**直接测量**该主张？ | ✗ 我测的是统计精度，不是稳定性/吸引力 |
| ③ 若论文的机制**完美实现**，我的指标会变好吗？ | ✗ 会变好一点，但不是论文主张的"量级差异" |

**推荐做法**：优先**复用论文自己的主图/主表指标**（如本轮的 Figure 1 是"rollout 是否崩坏"），而不是自造一个"看起来合理"的指标。自造指标须在协议里写明"与论文主张的映射关系"。

## L4 ★★ 参数标定：先数值反推，再动手（本轮 ~50 元）

**错误做法**：论文的 README 给了一句模糊表述（"内半径的**下界**应为 `norm(data).max()`"），我按字面取均值 86,204 → 球壳覆盖吸引子 → 过阻尼 → 参考解崩。

**正确做法——三段式标定**：

1. **数值反推官方常量**：拿官方在**已有规模**上的取值，与数据统计量对比，推断官方**真实意图**
   - 本轮：官方 Re=500 用 `156.25×64 = 10000`，而该数据 `norm×S` 的 **min = 13786** → **官方值比"下界"还小 0.73 倍** → 说明官方是"**吸引子内软约束**"，不是"球壳在吸引子外"
   - ⇒ 一句话：**用官方已给的数字做反推，胜过按文档字面新算一个值**
2. **若必须跨规模换算**：优先照抄**同一公式**（如 `156.25*S`），而不是"按文档描述重算"
3. **扫描要有界且有依据**：候选数 ≤ 3–4 个，每个候选必须能说出"它对应文档/代码的哪种读法"；扫描用**探针规模**（1 seed）

## L5 ★★ 失败后的第一反应：怀疑指标，而不是加密配置

**错误做法**：8:20 首次判定失败，我的第一反应是换配对（P1 等容量）、换基线架构（U-Net）——**多烧 4h 与两次无效训练**。

**正确做法**——失败诊断的**固定顺序**（成本从低到高）：

| 顺序 | 检查 | 成本 |
|---|---|---|
| 1 | **指标是否测对了论文主张**（L3） | 0（重读论文） |
| 2 | **判定条件是否结构性可行**（L2） | 0（纸面计算） |
| 3 | **超参标定是否正确**（L4 数值反推） | 30 min |
| 4 | 实现的容量/预算是否匹配（同参数量、同 epoch） | 1 探针 |
| 5 | 换配对/换架构/换数据集 | 贵，最后才做 |

## L6 ★ 失败必须区分"论文不成立"与"我配置错"

本轮诊断结论：**论文的主张未被推翻**，是（a）我的指标不对题（b）我的标定错。两者都**不是论文的错**。

**规则**：写失败归因时，必须给出**至少一条"论文主张仍然可能成立"的证据**；不能笼统写"论文不可复现"。同时**不能**因为"论文对"就无限追加试错（L1 的探针预算就是上限）。

## L7 ★ 交付物资产化的正收益

即使题目失败，以下资产**100% 可复用**（换题边际成本 ~1–2 天）：
- 双镜像（Dockerfile/test.sh/make_reward）——数据无关
- 冻结评分器框架（指标可换、质量门可换、anchor 机制保留）
- 自动化链（编排器/回填器/监测/参数化器/转换器/汇总器/finalize）——数据无关
- 数据管线（下载/派生/真值/地板）——只改路径
- 双轨环境（两台机器 + codex + 双模型 + 同步机制）
- 填表文字模板（c13/c16/c17/c19 + 成本四列）

**做法**：从第一轮起就把这些写成"与数据集解耦"的脚本（本轮做到了，所以换 Re5000 只花了 1 小时）。

## L8 ★ 环境与数据的易错点（本轮实测，可直接抄）

| 坑 | 症状 | 处理 |
|---|---|---|
| 官方脚本 `sys.path.append('../')` | `ModuleNotFoundError: utilities` | 按官方目录布局铺 `utilities.py`/`dissipative_utils.py`/`models/` 到父目录，**不要改脚本** |
| 官方脚本 `torch.save(model, path)` **无扩展名** | 按 `*.pt` 找 checkpoint 恒失败 | 用 `run.log` 的 `Weights saved` 判断完成；找文件按"最大的非 json/log 文件" |
| pickle 引用官方模块 | `No module named 'fno_2d'` | 转换时把官方仓 root 与 models/ 加进 `sys.path` |
| `domain_size` 硬编码 | rollout `shape invalid` | 转换器加 `--domain-size` **并做一次前向尺寸校验** |
| 生成脚本的 CRLF | bash `syntax error near '\r'` | `sed -i 's/\r$//'`，且**写入时用 LF** |
| SSH 门户不稳 | 长命令被掐 | 远端脚本 + `setsid nohup`；**短命令探测**；关键链路自驱动不依赖控制端 |
| 多实例并发 | 重复启动训练抢卡 | 全局 flock + 按 `/proc/*/cwd` 检测已运行任务 |
| 官方 stdout 块缓冲 | 中途看不到 epoch | 用 GPU 利用率 + 进程 cwd 判断在跑；ETL 用别的信号（如 `model/` 出现） |
| 论文 README 的模糊参数 | 参考解崩/无区分度 | 见 L4：**数值反推官方常量** |

## L9 ★ 成本与排期的诚实估算

- **单跑耗时要实测**（本轮 Re=500 估 3.5h 实测 8.7h；Re=5000 估 2h 实测 1.1h）→ 探针阶段顺手记录耗时，**不要用论文的 epoch 数 × 猜测的速度**。
- 预算要按**分支期望**报：`E[成本] = Σ 分支概率 × 分支成本`，而不是"最顺利路径"。
- 失败后的追加投入必须**有明确上限**（本轮设了"扫描 3 候选 + 1 轮探索，否则止损"）。

---

## L10 ★★★ 五道不可跳级里程碑（吸收自 autoresearch-skills v0.3.4 的 shift-left QA）

这是本仓库最重要的结构升级：把"检查"从"最后集中质检"改成**五道按序门禁，任一不过不进入下一阶段**。
依据：本项目 9 条题线的失败，全部可归入"问题在长跑/打包后才暴露"（新增计算只扩大返工面）。

| 里程碑 | 进入下一阶段前必须已具备的证据 | 失败动作 | 本项目的对应事故 |
|---|---|---|---|
| **M1 selection** | 论文身份、许可边界、**方法级优化面**、题库权威状态 | **换题或补证；不写题面、不租卡** | 0565/1851/1430/1352 全在此该被拦 |
| **M2 pilot** | B/R **receipt**、独立复算、**效应/噪声结论** | 修协议或拒题；**不启动双轨** | 0566：无 pilot 直接全 seed，亏 ~480 元 |
| **M3 container** | Agent/Verifier 镜像 digest、Hidden 隔离、目标 Harness 完整 trial | 修构建与路径；**不计长跑时长** | 双镜像 V01–V05 已过（本阶段我做对了） |
| **M4 long_run** | 两条独立血缘、闭合有效时长、机外快照与恢复 probe | 补真实运行；**不得拼接旧轮次** | 2001 三会话互写权重（血缘污染） |
| **M5 release** | 两份独立 QA 报告、机器聚合共识、隐私报告、白名单 manifest | 任一失败即 **NOT READY** | 0340「备好≠已交」；EMERALD 无结论 |

**门禁语义（照抄其原则，不妥协）**：
- **不做总分补偿**：热度、引用数、新颖性不能抵消许可/评测/资源/交付失败
- 三态结论：`RECOMMEND`（全部硬门 PASS）/ `NEEDS_EVIDENCE`（有 UNKNOWN/REVIEW）/ `REJECT`（任一 FAIL）
- 非发布里程碑的检查器**只核对证据引用是否齐全**；`release` 门才重算 SHA256、核对两份 QA 同源不同会话

**最小返修循环**（也是他们的规则，非常实用）：
1. **只修当前最早失败的里程碑**，后续阶段暂停
2. 用**新 run/trial ID** 重跑最小证据，不改写旧 receipt
3. 比较修复前后冻结合同与来源哈希，确认没有换题/换分母/换 evaluator
4. 重跑本里程碑门禁 **及所有受影响的上游门禁**
5. 只有当前里程碑重新通过，才恢复下一阶段

**关键限定**（他们说得很清楚，我也认同）：这套流程**降低返修成本，但不保证零返修**。目标是让失败尽早、边界清楚、可重放。

---

## L11 ★★★ 原生 NOP Trial 是"环境类"事故的重灾区（2026-10-08 auto2768 实录）

> 来源：auto2768（DREAM / 图标签噪声）返修轮。此前包内只有"手工 Docker 模拟"被当成 NOP，
> 被平台判为**不能证明原生 Harbor NOP**，触发 H06/QA17 不通过。
> 修复后跑通原生 Trial 两次（首次 692.2s、缓存命中后 35.0s），本条只记**可复用的判断与操作**。

**核心认知**：NOP 的 0 分**不是失败**，它证明的是**链路**（镜像能建、容器能起、独立 Verifier 能执行并落地 reward）。
真正会失败的是**环境前提**，而且这些前提**在跑之前就能查**。

### 环境前提清单（跑 NOP 前逐条实测，不要假设）

| 前提 | 检查命令 | 典型失败 | 修法 |
|---|---|---|---|
| Docker 能申请 GPU | `docker run --rm --gpus all <img> nvidia-smi -L` | `invoking the NVIDIA Container Runtime Hook directly is not supported` | 见下"snap Docker 陷阱" |
| nvidia runtime 已注册 | `docker info --format '{{json .Runtimes}}'` | 只有 `runc`，无 `nvidia` | 装 `nvidia-container-toolkit` 并在 daemon.json 注册 |
| buildx 存在 | `docker buildx version` | `unknown flag: --file` | 装 buildx 插件到 `~/.docker/cli-plugins/` |
| compose v2 存在 | `docker compose version` | `docker: 'compose' is not a docker command` | 装 compose v2 插件 |
| 宿主容量 ≥ 题面声明 | `nproc`、`free -g` vs `task.toml` 的 `cpus`/`memory_mb` | `Range of CPUs is from 0.01 to 8.00` | 见下"资源施加方式" |
| 网络可达 GitHub/PyPI | `curl -sI https://github.com` | `early EOF`、`index-pack failed` | 用 codeload tarball 或代理 |

### ★ snap 版 Docker 的结构性陷阱（本项最隐蔽）

**症状**：`--gpus all` 报 `invoking the NVIDIA Container Runtime Hook directly is not supported`；
补装 toolkit 后变成 `mkdir /usr/bin/nvidia-cuda-mps-control: read-only file system`。

**根因**：snap 版 Docker 的 dockerd 跑在**只读挂载命名空间**里，CDI 规范要求逐个 bind mount 宿主文件，
被只读命名空间拒绝。这不是配置错误，是**包装方式的结构限制**。

**判定**：`snap list docker` 显示 `confinement: strict` + 挂载命名空间内 `/usr` 只读 ⇒ 必然失败。

**修法（已验证）**：起一个**私有 dockerd**（宿主命名空间），与 snap 版并存互不干扰：

```bash
cat > $B/daemon.json <<EOF
{ "runtimes": { "nvidia": { "path": "/usr/bin/nvidia-container-runtime", "runtimeArgs": [] } },
  "storage-driver": "overlay2", "log-level": "error", "default-runtime": "runc" }
EOF
nohup /usr/bin/dockerd --host unix:///$B/docker.sock --pidfile $B/dockerd.pid \
  --data-root $B/docker-data --exec-root $B/docker-exec \
  --config-file $B/daemon.json --containerd /run/containerd/containerd.sock \
  >> $B/logs/dockerd.log 2>&1 &
export DOCKER_HOST=unix:///$B/docker.sock
docker run --rm --gpus all <cuda-img> nvidia-smi -L      # 必须实测通过
```

**共享机器时的隔离纪律**：若目标机已有其他题线在用（如租用机上另一道题在跑），
必须使用**独立根目录 + 独立 dockerd + 独立镜像名**，不碰对方的 data-root / 镜像 / 工作树。
这是可复用的做法，不是"抢机器"。

### ★ 构建超时：镜像源是合法加速，不是"取巧"

**症状**：`timed out after 1800`（题面声明的 `build_timeout_sec`）。根因是从官方源拉 torch 约 0.5 MB/s。

**正确做法**：镜像源（清华/阿里）只是同一批 wheel 的不同 CDN，
`torch>=2.5.1` 这类**声明式版本约束**装出的版本与二进制完全一致。
**不要**把它当成"证据不干净"而拒绝——那是把"证据要干净"错误外推成"不能换下载源"。

**关键纪律**：加速必须走**试验层**（不改交付包字节），例如 Harbor 的
`environment.extra_docker_compose` 注入 `build.args.PIP_INDEX_URL`。
交付包的文件哈希必须仍与运行绑定一致（见 L13）。

### ★ 资源施加方式与"声明容量"的落差

题面声明 `cpus=16 / memory_mb=65536`，而租用机只有 8CPU/16GB ⇒ 按声明设限会触发
Compose 的 CPU 范围错误而**无法启动容器**。

**做法**：试验层设 `cpu_enforcement_policy: ignore` / `memory_enforcement_policy: ignore`，
**并把这一差异如实写进 evidence**（含宿主 `nproc`/`free` 实测值）。
**不得隐瞒**：GPU 数量、网络策略、Verifier 分离方式必须与交付题包完全一致，
差异只允许出现在"施加方式"上，且必须留痕。

### ★ NOP 结果的正确解读（判据）

```json
{"status":"INVALID","failure":"FORMAT_ERROR","hard_gate":false,
 "candidate_fault":true,"reward":0.0,
 "detail":"missing prediction file: /workspace/solution/artifacts/<ds>/test_pred.npy"}
```

- `hard_gate: false` ⇒ 未触发 LABEL_LEAK / QUALITY_GATE 等**非作弊硬约束**，这是预期分支。
- 该 0.0 是"没有提交物"的**正确值**，既不判失败，也不等于通过。
- NOP 要验证的四条链路：**镜像能构建 / 容器能起 / 独立 Verifier 在 separate 模式真实执行 / reward 正确落地**。

**通过判据（全部满足）**：`finished_at` 有值、`exception_info` 为空、
`verifier_environment_mode == "separate"`、`verifier_result.rewards` 为有限数值且与
`reward.txt`/`reward.json` 一致、同一次 Trial 的 config/result/日志/artifacts manifest 齐备。

## L12 ★★★ 质检 Skill 的契约字段必须一次性对齐（21 次报错的教训）

> 来源：auto2768 质检轮。同一份 review.json 撞了 **21 次 `inspection_error`**、13 种不同错误。

**错误做法**：改一处 → 重跑 → 撞下一个错 → 再改。高频重复项：`QA17.remediation` **6 次**、
`H06 requires config.json` **5 次**。

**正确做法**：动手写 review.json 前，**先把校验器的约束清单一次性列全**：

```bash
# 把 validator 里所有会 raise 的字段约束抓出来，对着清单改，不靠试错
grep -n "raise ValueError" <qa-skill>/scripts/*.py
```

**已实测的高频字段约束（照抄即可少走弯路）**：

| 约束 | 说明 |
|---|---|
| `harbor.path_contract.profile` + `profile_basis` | 必填；profile 取 `harbor-environment-v1`（当前默认）或 `teaching-task-root-v1` |
| `hidden_review.mode` | 必须是 `prebuilt` / `generated` / `injected`；prebuilt 还需 `asset_paths` 指向**真实非空文件** |
| H 项 `summary` | **≤220 字符**，超出即报 "concise summary and evidence array required" |
| 证据引用 | 必须是**文件**，不能是目录（`tests/private/` 这类目录引用会被拒） |
| H06 证据 | 必须同一次 Trial 的 config + result + reward + 日志**全在证据列表里** |
| G 门 | `status`、`summary`、`reason_code` **三者都非空**；fail/manual 还须 `remediation` 与 `acceptance_evidence` |
| QA17 | 状态由 H01–H06 **聚合**得出，不能手填覆盖；其 `remediation` 在非 pass 时强制非空 |
| overview 统计量 | 必须与 `paired_runs` **全精度**一致（脚本按 `rel_tol=1e-7` 比），写 4 位小数会被判"与逐 seed 重算不一致" |
| `duration_hours` | 必须 ≥ `effective_seconds/3600`；**浮点边界会咬人**：`11.0036×3600 = 39612.96 < 39613` |
| `duration_evidence` | 必须是 collector 生成的**原始候选串精确匹配**（前缀须等于 `source_path`） |
| `risk_notes` | 必须是字符串数组 |

**入口差异**：来源附件的 `audit_task.py` **不支持 `--review`**（传了也白传，报告会退回初稿状态），
必须用 `implementation_review.py`。且**输出目录必须新鲜**（已存在会被拒）。

**注意**：这些是**报告结构约束**，不是题目缺陷。撞它们不代表包有问题，但反复撞会掩盖真正该看的证据。

## L13 ★★★ 运行绑定的哈希必须与交付字节交叉验证

> 来源：auto2768。这是把"NOP 记录"从"一份日志"升级为"可验证证据"的关键一步。

**做法**：NOP/正式 Trial 运行**之前**，对题包树算全量 SHA-256 清单并随证据归档：

```
task-tree-hashes.json  ← {"files":[{"path":"...","sha256":"..."} , ...]}
```

**验证**：交付 zip 内对应文件逐个比对，**必须逐一相同**。

```python
rec  = {e['path']: e['sha256'] for e in load('task-tree-hashes.json')['files']}
ship = {n[len('workspace/harbor_task/'):]: sha256(read(zip, n)) for n in names if ...}
assert rec == ship        # 逐文件一致
```

**为什么重要**：没有这一步，"我跑过 NOP"只是自陈；有了它，才能证明**跑的就是交付的那份字节**，
而不是另一个副本。这是回应"哈希与交付文件不一致"类质控意见的唯一硬手段。

**连带纪律**：任何交付包内的字节改动（哪怕只是文档措辞）都会让绑定失效，
必须**重跑一次 NOP 并重新生成哈希清单**。代价已实测：缓存命中时**约 35 秒**（首次构建约 11.5 分钟）。

## L14 ★★ 同一事实的多个声明必须对齐（U/锚点类"双真源"）

> 来源：auto2768。包内对同一个上界 `U` 存在**两套互相排斥的声明**，比措辞问题严重得多。

**实测**：`tests/calibration.json`（生效）写 U=75.1333；而 `expert_annotation.json`、
`repair/protocol_decisions.json`、`专家作业说明文档.md` 三处写 U=100.0，
且 `protocol_decisions.json` 自称 `no_post_result_upper_bound_tuning: true`。

**时间线暴露真问题**：U 在正式 B/R 结果**之前**预登记为 100，在结果**之后**改为 75.1333
⇒ 与"不得见结果后调上界"的自我声明**直接冲突**。

**正确做法（已采用）**：
1. 把生效值统一为实际使用的锚点，其余作为**明确标注的口径对照**（两种口径下归一化 0.6528 / 0.2269 均在 [0.15,0.8]）。
2. 把 `no_post_result_upper_bound_tuning` 改为 `false`，**并写明变更发生在结果之后**。
3. 在公开协议里明确 `U` 与"数学上限 100"是**两个不同的量**（前者是奖励锚点，后者是资格分母用的天花板）。

**原则**：**宁可如实披露一次口径变更，也不要留一个自相矛盾的 `true`**。
审阅者能接受披露过的变更，不能接受被掩盖的矛盾。

## L15 ★★ 交付物消失/被覆盖的防护（快照与报告分离）

> 来源：auto2768 清理轮。交付前发现**桌面上的报告与改过的表格都不在磁盘上**，
> 只剩改动前备份，且工作目录里那份同名旧表的目标行是**另一道题**。

**教训**：
1. **交付物与工作快照分离**：交付报告不要只存在于会话结束时的隐式状态里，落盘后**立即回读校验**。
2. **改前先备份并命名带日期**：`<原名>.backup_<YYYYMMDD>.xlsx`，且**备份不能是"损坏版"**。
3. **同目录可能有同名异构文件**：改表前必须先确认**主键命中**（要查 `题号 == 目标` 的那一行），
   再动手；文件名相同**不代表**是同一份数据。
4. **报告与表格内容必须同源**：报告里的每列新值应当**直接从已写入的文件回读**，而不是从记忆重写。

## L16 ★★ 磁盘清理的安全顺序（先验证，再删除）

> 来源：auto2768 清理轮。D 盘 99% 满（剩 9.2G），回收约 15G。

**正确顺序**：
1. **先列出"必须保留"清单并逐一验证存在**（最终交付 zip、最终质检报告、工作树、NOP 证据）。
2. **再按"是否含最终版本引用"筛候选**：用最终 zip 名或版本号在所有候选目录里做内容检索，
   命中者为待核，未命中者才进删除列表。
3. **删除前打印确认列表**（路径 + 体积），确认无 `_final`/最新版本混入。
4. **删除后重新核对交付物**仍在。

**易误判**：`du` 可能给出**陈旧的元数据**（实测把 0 文件空目录报成 412M/710M）。
判断"是否真的释放"要用 `df` 前后对比，不要只信 `du`。

**典型的中间产物**（可安全回收）：`qa_final_*` 调试副本（保留最终一个）、
`_superseded*` 旧交付包、旧版扫描目录、旧版包的解压副本、空壳目录。
**不可回收**：最终交付包、最终质检报告、NOP 证据、工作树、带日期的备份。

---

## 快速检查清单（P0/P1 阶段强制过）

- [ ] 论文的**一句话主张**写下来了吗？指标**直接测量**它吗？（L3）
- [ ] 用 1 seed 的 B/R + U **预解**过 R_norm 与 3σ 的**可行交集**吗？（L2）
- [ ] 探针规模 ≤ 2×单跑耗时，且**通过前不启动正式 B/R**？（L1）
- [ ] 所有跨规模的超参都做了**数值反推**（而非按文档字面重算）吗？（L4）
- [ ] 失败诊断按"指标 → 判定 → 标定 → 容量 → 换题"顺序走吗？（L5）
- [ ] 资产与数据集**解耦**了吗（换题只需 1–2 天）？（L7）
- [ ] 跑 NOP 前实测过 GPU/buildx/compose/容量/网络**五项前提**吗？（L11）
- [ ] 交付字节与运行绑定哈希**交叉验证过**逐文件一致吗？（L13）
- [ ] 同一事实（锚点/口径/U）在包内**只有一套生效声明**吗？变更有披露吗？（L14）
- [ ] 写 review.json 前**一次性列全**校验器字段约束了吗？（L12）
- [ ] 清理前先列"必须保留"清单并验证存在了吗？（L16）
