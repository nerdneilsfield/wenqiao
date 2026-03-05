## 6.2 标准数据集与基准测试 (Standard Datasets and Benchmarks)
<!-- label: sec:benchmarks -->

跨方法比较的前提不是“都在做点云配准”，而是“使用了同一数据集、同一阈值、同一成功判据”。一旦训练集构造、点云下采样、RANSAC 采样数或成功阈值不一致，表面上接近的 RR、RTE 或 RMSE 就无法互相解释。因此，本节先补齐主流基准的数据规模和协议，再讨论它们各自缺什么，而不是直接把不同论文的最优数字拼在一起。

### 6.2.1 室内 RGB-D 数据集

**TUM RGB-D 数据集**提供室内 RGB-D 序列与地面真值轨迹，是 RGB-D SLAM 与基于深度图的局部配准常用测试集之一 [Sturm et al.](cite:sturmBenchmarkEvaluationRGBD2012)。原始 benchmark 含 39 个序列，Kinect 以 640×480、30 Hz 采样，动捕系统提供 100 Hz 真值轨迹。它适合检验近距离、小视场条件下的局部精配准稳定性；但由于视距短、点云范围有限，不能直接外推到车载 LiDAR 的大尺度稀疏场景。

**ScanNet 数据集**提供大规模室内 RGB-D 扫描序列与重建场景，是室内三维理解与片段级配准任务常见的数据来源之一 [Dai et al.](cite:daiScanNetRichlyAnnotated2017)。它的价值不在于“配准协议已经标准化”，而在于提供跨房间、跨遮挡的大量真实重建片段，使学习型方法可以从中再构造局部片段对。也正因为如此，ScanNet 更接近上游数据源而不是直接可比较的配准榜单；若论文只写“在 ScanNet 上测试”，还必须继续交代如何抽取片段、如何生成真值和采用何种重叠阈值。

**Stanford 3D 扫描库**（Stanford 3D Scanning Repository）包含 Bunny、Dragon、Happy Buddha 等经典扫描模型，常用于展示高重叠、低噪声条件下的局部配准精度上限。[Besl and McKay](cite:beslMethodRegistration3D1992) 的早期曲面实验以及 [Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001) 的采样/收敛研究都依赖这类对象级数据。它们适合解释目标函数和采样策略的差异，但不适合代表真实传感器噪声、动态外点和长时序漂移。

**3DMatch 数据集**是学习型局部特征与配准方法的核心评测基准之一：从室内 RGB-D 重建中构造点云片段对，并提供训练与评估用的配准真值 [Zeng et al.](cite:zeng3DMatchLearningLocal2017)。PREDATOR [Huang et al.](cite:huangPREDATORRegistration3D2021) 进一步把官方 3DMatch 中重叠率大于 30% 的样本之外的片段对单独整理为 3DLoMatch，仅保留 10%–30% 重叠的困难样本。这个划分很重要，因为很多方法在 3DMatch 上已经接近饱和，但在 3DLoMatch 上仍会明显掉点。

评测指标（不同工作阈值设置差异较大，横向比较时需同时报告阈值）[Zeng et al.](cite:zeng3DMatchLearningLocal2017)：
- **FMR（Feature Matching Recall）**：特征匹配召回率，反映描述子质量与匹配稳定性。
- **IR（Inlier Ratio）**：对应集中满足几何一致性阈值的比例。
- **RR（Registration Recall）**：配准变换误差落在给定旋转/平移阈值内的比例。

### 6.2.2 室外 LiDAR 数据集

**KITTI 里程计数据集**是自动驾驶与移动机器人领域的标准基准之一，提供车载多传感器数据与里程计评测协议[Geiger et al.](cite:geigerVisionMeetsRobotics2013)。在点云配准语境中，KITTI 常被用于评估室外驾驶序列上的帧间扫描匹配与里程计漂移，常见报告口径是相对平移/旋转误差。
更具体地说，LOAM 使用的 KITTI odometry 数据以 10 Hz Velodyne 记录，配准结果由 benchmark 服务器按 100 m 到 800 m 的轨迹段统一打分 [Zhang and Singh](cite:zhangLOAMLidarOdometry2014)。因此，KITTI 更适合衡量“前端累计误差会不会在道路尺度上扩散”，而不适合替代片段级 RR/FMR 这类局部配准指标。

KITTI 的主要局限：
- 场景较"规整"（城市道路），缺少隧道、森林等非结构化场景。
- 以车载多线 LiDAR 为主，对低线数、稀疏点云与极端遮挡的覆盖不足。
- 无动态物体标注，动态物体（行人、车辆）引入的外点对 ICP 的干扰未被单独量化。

**ETH 数据集**是室外静态场景的三维点云配准基准之一，常用于比较不同 ICP 变体在噪声、外点与部分重叠条件下的精度与鲁棒性 [Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。它的价值在于场景固定、协议清楚，适合比较 P2P、P2Pl、GICP、TrimmedDist 和采样策略的组合；局限也同样明显，即动态外点极少，无法反映自动驾驶中的车辆和行人干扰。

**M2DGR 数据集**提供多传感器、多场景的 SLAM 数据序列与地面真值，是近年来用于检验算法跨场景泛化能力的代表性数据集之一[Yin et al.](cite:yinM2DGRA2022)。[Sun et al.](cite:sunEA2DLSLAMEnvironmentAnalysisbased2025) 在自适应降采样评测中同时使用了 M2DGR 和 KITTI，反映了评测从单传感器、单场景向多模态、多场景综合比较的趋势。

**更大规模与长时序数据集**常用于检验跨天气、跨光照与跨传感器配置的稳定性：nuScenes [Caesar et al.](cite:caesarNuScenesMultimodalDataset2020) 与 Waymo Open Dataset [Sun et al.](cite:sunScalabilityPerceptionWaymo2020) 提供多模态车载传感器套件；Oxford RobotCar [Maddern et al.](cite:maddernOxfordRobotCarDataset2017) 与 MulRan [Kim et al.](cite:kimMulRanMultimodalRange2020) 覆盖更长周期与更复杂城市变化；手持/近距离建图的 Newer College 数据集 [Ramezani et al.](cite:ramezaniNewerCollegeDataset2020) 则更接近轻量移动平台的扫描匹配负载。这类数据集不一定直接提供“点云对点云”的配准真值，但对工程系统的端到端鲁棒性评估更贴近现实。

### 6.2.3 合成数据集与点云配准专用基准

**ModelNet40** 最早随 3D ShapeNets 工作推广为对象级 3D 形状基准之一 [Wu et al.](cite:wu3DShapeNetsDeep2015)。DCP [Wang and Solomon](cite:wangDeepClosestPoint2019) 和 RPM-Net [Yew and Lee](cite:yewRPMNetRobustPoint2020) 等方法都把它作为对象级刚体对齐的标准起点：前者在 12,311 个 CAD 模型上随机采样 1024 点，后者在部分类别不重叠、加噪和部分可见设置下继续扩展协议。它的优势是可控真值和可控噪声；缺点是局部几何过于干净，外点和遮挡是人工注入的，和真实 RGB-D 或 LiDAR 片段仍有明显分布差异。

**Redwood/片段级配准基准**：室内重建数据常被切分为局部片段并构造片段对评测（与 3DMatch 的设置相近），Redwood 系列数据与其衍生评测在开源实现中被广泛采用[Choi et al.](cite:choiRobustReconstructionIndoorScenes2015)。其优势是可直接检验"低重叠 + 遮挡 + 噪声"下的局部配准与鲁棒对应模块。

**PCL 基准**（Pomerleau et al., Autonomous Robots 2013 [Pomerleau et al.](cite:pomerleauComparingICPVariants2013)）：首个系统化的 ICP 变体对比基准，在 ETH 场景上评测约 30 种组合（对应方法 × 外点处理 × 误差最小化）。其价值不只在于给出优劣排序，而在于证明三点：对应建立方式常比局部最小化器更影响结果；降采样和搜索结构常比“再换一个损失函数”更影响总时延；场景一旦变化，最优配置也随之改变。这也是第六章坚持把“条件”写在“结果”前面的原因。

| 数据集/协议 | 典型场景 | 原文规模或划分 | 常用指标/阈值 | 适合回答的问题 | 不足 |
|-------------|----------|----------------|---------------|---------------|------|
| TUM RGB-D [Sturm et al.](cite:sturmBenchmarkEvaluationRGBD2012) | 室内 RGB-D | 39 序列；640×480@30 Hz；真值 100 Hz | ATE/RPE、局部对齐误差 | 小场景精配准是否稳定 | 点云范围短，不代表车载稀疏场景 |
| ScanNet [Dai et al.](cite:daiScanNetRichlyAnnotated2017) | 大规模室内扫描 | 大规模室内重建序列，常被二次切片 | 论文自定义片段级指标 | 学习型方法是否能从真实室内重建中泛化 | 不是单一固定配准协议 |
| Stanford 3D | 对象级高重叠扫描 | Bunny/Dragon/Buddha 等 | RMSE、成功率 | 局部目标函数和采样策略的上限表现 | 噪声与外点过少 |
| 3DMatch [Zeng et al.](cite:zeng3DMatchLearningLocal2017) | 室内片段级配准 | 62 场景；PREDATOR 使用 46/8/8 划分 | FMR、IR、RR | 学习特征和片段级全局配准是否有效 | 只覆盖 >30% 重叠的标准样本 |
| 3DLoMatch [Huang et al.](cite:huangPREDATORRegistration3D2021) | 低重叠室内片段 | 从 3DMatch 中抽取 10%–30% 重叠对子 | FMR、IR、RR | 低重叠前端是否还可靠 | 场景仍局限于室内 RGB-D |
| KITTI odometry [Geiger et al.](cite:geigerVisionMeetsRobotics2013) | 车载道路 LiDAR | 10 Hz Velodyne；按 100–800 m 轨迹段评分 | 相对平移/旋转误差，端到端漂移 | 前端里程计是否能在长距离驾驶中稳住漂移 | 动态外点未单独量化 |
| ETH/PCL benchmark [Pomerleau et al.](cite:pomerleauComparingICPVariants2013) | 室外静态点云对 | 固定六场景，约 30 种 ICP 组合 | 时间、收敛质量 | 传统 ICP 模块化取舍 | 动态外点和硬件约束缺失 |
| nuScenes [Caesar et al.](cite:caesarNuScenesMultimodalDataset2020) | 大规模车载多模态 | 多传感器、长时序场景 | 多任务指标，配准常需自定义协议 | 跨天气、跨传感器鲁棒性 | 配准协议分散，难直接横比 |
<!-- caption: 第 6.2 节主流基准的任务边界汇总。表中信息用于说明“不同数字来自什么协议”，避免把片段级 RR、里程计漂移和对象级 RMSE 混成同一类结果。 -->
<!-- label: tab:benchmark-landscape -->

### 6.2.4 评估指标的标准化

点云配准的评估指标尚未完全统一，不同论文采用不同指标造成比较困难：

**变换精度指标**：
$$
\text{RMSE}_T = \sqrt{\frac{1}{n_\text{test}} \sum_{i=1}^{n_\text{test}} \|e_i\|^2}
$$
<!-- label: eq:rmse-transform -->
其中 $e_i$ 为第 $i$ 个测试对的变换误差（可以是欧氏位移误差或旋转角度误差）。

**配准召回率**（Registration Recall，RR）：
$$
\text{RR} = \frac{|\{i : \|e_i\| < \tau\}|}{n_\text{test}}
$$
<!-- label: eq:registration-recall -->
$\tau$ 的选取决定了 RR 的严格程度；不同基准与不同论文常采用不同的阈值组合，必须与 RR 同时报告，否则 RR 无法互相比较 [Zeng et al.](cite:zeng3DMatchLearningLocal2017)。

**RTE/RRE**（3DMatch 系列常用）：令估计变换为 $(R,t)$、真值为 $(R^\*, t^\*)$，则平移误差 $\text{RTE}=\|t-t^\*\|_2$；旋转误差常定义为 $\text{RRE}=\arccos((\mathrm{tr}(R^\top R^\*)-1)/2)$，多数论文再把它转成角度表示 [Zeng et al.](cite:zeng3DMatchLearningLocal2017)。

**时间指标**：
- 单帧延迟（Latency）：测量从输入点云到输出变换的总时间，包含预处理、对应搜索、优化全流程。
- 吞吐量（Throughput）：单位时间处理的点对数量（对并行系统更重要）。
- 首帧响应时间 vs 稳态帧率：流式处理系统（LiDAR 里程计）中，稳态帧率（包含 Pipeline 重叠）更具参考价值。

**内存指标**：片上 BRAM 用量（FPGA）、参数量（深度学习方法）、运行时峰值内存（CPU/GPU）。

![主要数据集特性分布雷达图](../images/ch6-dataset-radar.png)
<!-- caption: 五个常用点云配准数据集（Stanford、TUM RGB-D、ETH、KITTI、3DMatch）在六个特性维度（场景规模、点云密度、噪声水平、低重叠挑战、地面真值精度、传感器多样性）上的雷达图对比。该图按学术概念图绘制，用于帮助读者建立“数据集偏向什么困难”的直觉，不对应统一协议下的定量测量。 -->
<!-- label: fig:dataset-radar -->
<!-- width: 0.75\textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Create a publication-quality academic figure for a thesis/survey paper.
  Use a unified academic publication figure style:
  - White background
  - Flat vector style
  - Clean structure, crisp lines, balanced whitespace
  - No realistic rendering, no 3D, no poster look
  - This is a conceptual diagram / qualitative comparison, not a real benchmark plot
  Global color system and semantic consistency:
  - Main structure / primary frame: deep blue #2B4C7E
  - Memory / auxiliary blocks: teal blue #3C7A89
  - Data / intermediate flow: orange #D17A22
  - Normal / retained / valid: dark green #5B8C5A
  - Conflict / bottleneck / pruned: dark red #A23B2A
  - Text dark gray #333333
  - Borders medium gray #888888
  - Light gray background blocks #EDEDED
  - Keep the entire figure within 5-6 colors
  Layout:
  - Single radar/spider chart panel centered on the page
  - Concentric rings labeled 1-5 with thin gray gridlines
  - Legend fixed at right side, compact and strictly aligned
  - Clean radial spacing and no decorative markers
  Typography:
  - Chinese-first labels only
  - Title largest, axis labels second, legend labels third, note smallest
  - Thesis-like sans-serif with good CJK support
  - Title: "常用数据集特性分布（概念示意图）"
  Axes (clockwise from top):
  - 场景规模
  - 点云密度
  - 噪声水平
  - 低重叠挑战
  - 真值精度
  - 传感器多样性
  Datasets:
  - Stanford
  - TUM
  - ETH
  - KITTI
  - 3DMatch
  Data handling:
  - Use schematic integer scores only, not benchmark measurements
  - Stanford: 2, 5, 1, 1, 5, 1
  - TUM: 2, 3, 3, 2, 4, 2
  - ETH: 3, 2, 4, 3, 4, 2
  - KITTI: 5, 3, 2, 2, 3, 3
  - 3DMatch: 3, 3, 3, 5, 3, 4
  Visual encoding:
  - Use 5 distinct but restrained polygons derived from the shared academic palette
  - Main series colors should stay muted and publication-safe, not rainbow-like
  - Stroke width about 2px, fill opacity around 0.15-0.18, no point markers
  - Preserve readability where polygons overlap
  Note:
  - Add a small note below the chart in dark gray:
    "注：评分为概念示意，用于帮助建立数据集偏好与困难类型的直觉，不代表统一协议下的定量结论。"
-->

### 6.2.5 评估体系的局限性与展望

当前基准测试体系存在若干值得关注的局限性：

**静态场景假设**：绝大多数基准数据集以静态场景为主（如 Stanford、ETH），或只包含有限的动态干扰。真实交通与人机协作环境中，动态物体经常是外点的主要来源，但现有基准对动态外点的系统刻画仍不足。

**传感器偏差**：室外车载多线激光雷达与室内 RGB-D 的噪声模型、采样密度与遮挡模式差异显著。算法在一个数据集上的表现不一定能迁移到不同传感器类型。

**硬件感知评估缺失**：现有基准几乎全部聚焦于算法精度，忽略了硬件资源占用、功耗和延迟的综合评估。随着[第 5 章](ref:sec:hardware-accel)所述的专用硬件加速兴起，急需一套统一的“精度-效率-资源”综合基准框架，将算法精度与硬件实现效率联合评估。

[Pomerleau et al.](cite:pomerleauReviewPointCloud2015) 的综述已指出上述问题，但目前仍缺乏一个统一的、跨传感器、跨场景、硬件感知的综合基准平台。这一缺口会直接影响第六章的解读方式：任何只在单一数据集上成立的优势，都不该被外推成“通用结论”。相关开放问题将在[第 7 章](ref:sec:future)继续讨论。
