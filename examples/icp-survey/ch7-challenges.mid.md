## 7. 开放挑战与未来方向 (Open Challenges and Future Directions)
<!-- label: sec:future -->

第 6 章从应用需求出发，系统梳理了 ICP 在自动驾驶、工业检测、机器人操作与医疗图像四大场景中的部署逻辑，并通过公开基准与横向比较确立了方法选型的四维约束框架。评测分析的核心价值不仅在于展示"什么方法在什么条件下更好"，更在于揭示现有技术体系在哪些条件下会**系统性失效**。初始位姿落在收敛盆外、动态物体形成结构化外点、几何退化导致不可观方向、实时约束与功耗预算在工程系统中同时收紧——这些失败模式在单一指标的基准评测中往往被平均效应掩盖，却是实际部署中最常见的障碍。本章将这些系统性挑战整理为"失败模式 → 代表性对策 → 仍未解决的缺口"的分析框架，目的不是给出最终答案，而是为未来研究划定最值得投入的方向边界。

### 7.1 初始化与全局粗配准：把问题拉回收敛盆

**失败模式**：局部 ICP 的可用范围由初始位姿和重叠率共同决定；一旦落在错误盆地，后续的目标函数微调很难纠正（[第 3.6 节](ref:sec:global-init)）。这一限制推动了“全局初始化 + 局部精修”的两阶段范式：先用全局方法产生候选位姿，再用 ICP 做局部收敛与精度抬升[Rusu et al.](cite:rusuFPFHFastPoint2009)[Zhou et al.](cite:zhouFastGlobalRegistration2016)。

**代表性路线**：
- **全局最优/可认证鲁棒估计**：Go-ICP 用分支定界在 $SE(3)$ 搜索全局最优解[Yang et al.](cite:yangGoICPGloballyOptimal2016)；TEASER/TEASER++ 用截断最小二乘与可认证优化在高外点对应下保持鲁棒[Yang et al.](cite:yangTEASERFastCertifiable2021)。
- **学习型对应/特征驱动的全局对齐**：FCGF 提供可学习局部特征用于匹配[Choy et al.](cite:choyFullyConvolutionalGeometric2019)，GeoTransformer 通过显式几何编码提升低重叠下的匹配质量[Qin et al.](cite:qinGeometricTransformerFast2022a)。

**尚未解决的缺口**：
- **“可证鲁棒性”与“实时性”的兼容**：可认证方法在工程系统中需要与下游 ICP、位姿图优化等模块一起端到端评估（[第 6.2 节](ref:sec:benchmarks) 和 [第 6.3 节](ref:sec:comparison)），其失败告警、置信度输出与系统策略仍缺统一接口。
- **域偏移与跨传感器一致性**：学习型描述子在训练分布外会出现显著退化，评测需显式覆盖跨传感器与跨场景设置[Zeng et al.](cite:zeng3DMatchLearningLocal2017)[Caesar et al.](cite:caesarNuScenesMultimodalDataset2020)。

### 7.2 动态场景与语义信息：把“外点”当成可建模结构

**失败模式**：动态物体并非零均值噪声，而是空间上连贯、时间上相关的“结构化外点”。仅靠 M-estimator 或截断策略（[第 3.2 节](ref:sec:outlier)）有时只能缓解偏置，难以从根源上区分“应配准的静态结构”和“应忽略/单独建模的动态结构”[Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002)[Zhang et al.](cite:zhangFastRobustIterative2022)。

**代表性路线**：
- **语义辅助配准**：将语义标签引入对应与优化，能在类别一致性约束下提升鲁棒性[Parkison et al.](cite:parkisonSemanticIterativeClosest2018)[Zaganidis et al.](cite:zaganidisIntegratingDeepSemantic2018)。
- **利用额外物理测量**：Doppler ICP 将径向速度残差并入目标函数，同时可用速度一致性剔除动态目标点[Hexsel et al.](cite:hexselDICPDopplerIterative2022)。

**尚未解决的缺口**：
- **联合建模而非串联管线**：现实系统往往采用“分割/检测 → 过滤 → 配准”的串联结构，但每一级的不确定性会累积并放大。更稳健的方向是把“动态点/语义”作为潜变量，与对应和位姿在同一框架中联合推断[Parkison et al.](cite:parkisonSemanticIterativeClosest2018)。
- **动态基准缺失**：现有配准基准对动态外点的系统刻画仍然有限，导致方法改进难以被独立量化与复现。

### 7.3 几何退化与不确定性：何时“拒绝配准”更可靠

**失败模式**：在长走廊、隧道、平面主导等场景中，点到面约束的某些方向会变得不可观，导致优化问题退化（degeneracy），并引发漂移或错误自信[Zhang et al.](cite:zhangDegeneracyOptimizationBased2016)[Hinduja et al.](cite:hindujaDegeneracyAwareFactorsApplications2019)。

**代表性路线**：
- **退化检测与因子化建模**：将局部几何不可观性显式建模到状态估计图中，触发降权或切换策略[Zhang et al.](cite:zhangDegeneracyOptimizationBased2016)[Ji et al.](cite:jiPointtodistributionDegeneracyDetection2024)。
- **不确定性传播与后验近似**：Stein ICP 等方法提供粒子集近似后验，用于下游规划与安全告警[Maken et al.](cite:makenSteinICPUncertainty2022)；在里程计语境下，亦出现面向退化鲁棒的自适应加权路线[Lee et al.](cite:leeGenZICPGeneralizableDegeneracyRobust2025)。

**尚未解决的缺口**：
- **与系统级“安全失败模式”的接口**：退化检测与不确定性估计必须映射为可执行策略（重定位、降速、切换传感器），否则只会变成论文里的附加指标。

### 7.4 硬件感知算法：从“加速某一步”走向“端到端共设计”

**失败模式**：ICP 的瓶颈往往来自最近邻搜索与内存访问模式（[第 4 章](ref:sec:software) 与 [第 5 章](ref:sec:hardware-accel)）。如果算法结构与硬件存储层级不匹配，即便算力充足也可能被带宽与随机访存拖垮[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。

**代表性路线**：
- **专用处理器与共设计**：Tigris 通过架构与算法协同为点云任务提供高吞吐的近邻搜索与几何算子支持[Xu et al.](cite:xuTigrisArchitectureAlgorithms2019)。
- **FPGA 流式化与可配置搜索**：面向 LiDAR 在线建图的 FPGA 流水线设计可在能效约束下实现稳定吞吐[Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025)。
- **近存储计算（PIM）**：将 KNN/相关计算靠近存储阵列执行以减少数据搬运，是应对内存受限瓶颈的另一条路线[Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025)。

**尚未解决的缺口**：
- **把“预处理与质量控制”纳入加速范围**：动态点剔除、法向估计、退化检测等往往决定系统稳定性（[第 7.2 节](ref:sec:future) 与本章后续小节），但现有加速器多只覆盖“对应搜索 + 小规模求解”的核心环节。

### 7.5 评测与复现：从单指标到“协议 + 资源 + 失败率”

**失败模式**：同名指标在不同论文中常对应不同阈值、不同预处理与不同实现细节，导致横向对比结论不稳（[第 6.2 节](ref:sec:benchmarks)）。经典 PCL 基准强调模块组合对结果的主导作用，提示“缺少协议一致性时，方法差异会被实现差异淹没”[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。

**代表性路线**：
- **标准数据集与协议**：TUM RGB-D、3DMatch/3DLoMatch、KITTI 等为部分子任务提供了相对稳定的比较语境[Sturm et al.](cite:sturmBenchmarkEvaluationRGBD2012)[Zeng et al.](cite:zeng3DMatchLearningLocal2017)[Geiger et al.](cite:geigerVisionMeetsRobotics2013)。
- **跨场景、跨传感器数据集**：nuScenes、Waymo、RobotCar、MulRan 等更贴近工程部署的分布漂移与长时序变化[Caesar et al.](cite:caesarNuScenesMultimodalDataset2020)[Sun et al.](cite:sunScalabilityPerceptionWaymo2020)[Maddern et al.](cite:maddernOxfordRobotCarDataset2017)[Kim et al.](cite:kimMulRanMultimodalRange2020)。

**尚未解决的缺口**：
- **硬件感知的统一评估维度**：除精度外，延迟、吞吐、内存峰值与功耗等资源维度需要标准化报告口径，尤其是在硬件加速与边缘部署语境下（[第 5 章](ref:sec:hardware-accel)）。

![ICP 开放挑战全景图](../images/ch7-open-challenges-map.png)
<!-- caption: ICP 研究的主要开放挑战全景图。每个挑战都对应典型失败模式（收敛盆外、结构化外点、几何退化、内存瓶颈、协议不一致）及代表性技术方向（全局鲁棒估计、语义/物理量辅助、退化检测与不确定性、端到端共设计、标准化基准）。 -->
<!-- label: fig:open-challenges -->
<!-- width: 0.9\textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style for all panels: white background, flat vector illustration, no realistic rendering, no 3D shading, no poster or marketing aesthetics. Treat this as a conceptual mechanism diagram rather than a measured chart unless verified data are explicitly provided. Do not fabricate exact statistics, timings, ratios, or axis values. Use consistent color mapping across all figures: compute/process modules = #2B4C7E, storage/cache/memory = #3C7A89, data flow/candidate flow = #D17A22, retained/active/valid regions = #5B8C5A, bottleneck/pruned/conflict/failure = #A23B2A, text = #333333, borders = #888888, light gray blocks = #EDEDED. Chinese-first labels with concise academic wording, rounded rectangles for modules, aligned multi-panel layout, clear arrows, minimal line crossings, crisp lines, balanced whitespace, suitable for thesis or survey paper.
  Create a publication-quality infographic (flat 2D vector style) summarizing open challenges of ICP.
  White background, generous margins, clean sans-serif font with CJK support.
  Title (20pt): "ICP 开放挑战全景图"
  Layout: a 2x3 grid of rounded rectangles (panels), each panel has:
  - A bold Chinese panel title (16pt)
  - Two short bullet lists (12–13pt):
    left column "失败模式" (2 bullets), right column "代表方向" (2 bullets)
  Panels (left-to-right, top-to-bottom):
  1) Title: "初始化与收敛盆"
     失败模式: "初值偏离导致落入局部极小", "低重叠时对应不稳定"
     代表方向: "全局初始化 + 局部精修", "可认证鲁棒估计(TEASER/Go-ICP)"
  2) Title: "动态与结构化外点"
     失败模式: "动态物体形成偏置残差", "外点非独立同分布"
     代表方向: "语义辅助对应", "Doppler/多模态约束"
  3) Title: "几何退化与不确定性"
     失败模式: "不可观方向导致漂移", "错误自信与安全风险"
     代表方向: "退化检测与降权", "后验不确定性估计"
  4) Title: "内存瓶颈与实时性"
     失败模式: "随机访存拖垮吞吐", "端到端延迟不稳定"
     代表方向: "数据结构/近似NN", "流水线化与并行化"
  5) Title: "硬件感知共设计"
     失败模式: "只加速单模块难以端到端获益", "算法结构不匹配存储层级"
     代表方向: "专用处理器(Tigris)", "PIM/FPGA 流式化"
  6) Title: "评测与复现"
     失败模式: "阈值与协议不一致", "难以跨论文比较"
     代表方向: "标准协议(3DMatch/KITTI)", "资源维度(功耗/内存/吞吐)统一报告"
  Styling: use light gray panel borders (#D0D0D0), subtle header accent bar in blue (#1F77B4).
  No icons, no 3D, no gradients.
-->

| 挑战维度 | 典型失败模式 | 常见对策（代表工作） | 仍未解决的问题 |
|---------|--------------|----------------------|----------------|
| 初始化与全局粗配准 | 初值落在收敛盆外、低重叠匹配不稳定 | 全局初始化 + ICP 精修[Zhou et al.](cite:zhouFastGlobalRegistration2016)、可认证鲁棒估计[Yang et al.](cite:yangTEASERFastCertifiable2021) | 可证鲁棒性与实时性/系统接口的统一 |
| 动态与语义 | 结构化外点导致系统性偏置 | 语义辅助配准[Parkison et al.](cite:parkisonSemanticIterativeClosest2018)、物理量辅助（Doppler）[Hexsel et al.](cite:hexselDICPDopplerIterative2022) | 动态基准与联合推断框架不足 |
| 退化与不确定性 | 不可观方向导致漂移与错误自信 | 退化检测因子[Ji et al.](cite:jiPointtodistributionDegeneracyDetection2024)、不确定性估计[Maken et al.](cite:makenSteinICPUncertainty2022) | 安全失败模式与系统策略耦合 |
| 硬件/资源约束 | 随机访存与带宽限制吞吐 | 专用处理器[Xu et al.](cite:xuTigrisArchitectureAlgorithms2019)、PIM[Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025) | 预处理与质量控制的端到端共设计 |
| 评测与复现 | 指标阈值/协议不一致 | PCL 系统化基准[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)、3DMatch 协议[Zeng et al.](cite:zeng3DMatchLearningLocal2017) | 硬件感知的统一报告口径 |
<!-- caption: 第 7 章开放挑战的“失败模式—对策—缺口”总结表。 -->
<!-- label: tab:open-challenges -->

上表中的五类挑战彼此耦合，而不是彼此独立。几何退化会进一步压缩初始化的容错窗口，动态外点的联合推断依赖不确定性估计是否可信，硬件资源约束又反过来限制复杂联合优化能否落地。因此，更值得投入的方向不是在单一指标上继续压榨局部改进，而是构建能在系统约束下同时处理多个失败模式的框架。[第 8 章](ref:sec:conclusion) 将据此回到全文主线，总结本文的主要判断与工程启示。
