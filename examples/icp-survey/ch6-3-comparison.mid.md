## 6.3 方法横向比较 (Cross-Method Comparison)
<!-- label: sec:comparison -->

横向比较的关键不是在一张表里罗列尽可能多的方法，而是在统一的约束与评测语境下明确取舍：同一配准任务在初始化质量、外点率、重叠率与算力预算不同的条件下会呈现完全不同的有效域。本节以“任务条件 → 方法族 → 代表性证据 → 失效前提”为主线，总结[第 3 章](ref:sec:variants)到[第 5 章](ref:sec:hardware-accel)中各类技术的互补关系。

### 6.3.1 算法变体的综合对比

不同论文报告的 RMSE、RR 多半来自不同数据集、不同阈值与不同实现细节，直接拼接到同一张数值表会产生误导。因此，这里只保留“同类任务下能互相解释”的数字，并显式写出它们来自哪一类协议，例如 ETH/PCL 基准、3DMatch/3DLoMatch 或 ModelNet40 [Pomerleau et al.](cite:pomerleauComparingICPVariants2013)[Zeng et al.](cite:zeng3DMatchLearningLocal2017)。
需要做定量对比时，最小可行做法是固定公开基准、复用同一实现框架并明确超参数搜索范围；否则，实现差异经常会压过算法差异 [Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。

| 方法族 | 代表方法 | 代表性数据与数值 | 主要收益 | 典型代价 | 常用评测语境 |
|------|---------|---------|---------|------------|
| 基线局部 ICP | P2P ICP [Besl and McKay](cite:beslMethodRegistration3D1992) | 经典曲面例子中 RMS 0.59；ETH/PCL 中位时间约 1.45 s [第 3.1 节](ref:tab:correspondence-data) | 实现简单，作为局部精修基线 | 收敛盆小，对外点敏感 | 高重叠、初值较好 |
| 几何约束增强 | P2Pl ICP [Chen and Medioni](cite:chenObjectModellingRegistration1992)、GICP [Segal et al.](cite:segalGeneralizedICP2009) | GICP 以 20 近邻估计协方差，50 次迭代上限；30 m 间隔实测扫描仍可稳定配准 [第 3.4 节](ref:tab:transform-data) | 旋转与切平面约束更强 | 依赖法向/协方差估计质量 | 结构化几何、法向可信 |
| 鲁棒化 | TrICP [Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002)、FRICP [Zhang et al.](cite:zhangFastRobustIterative2022) | TrICP：Frog 上 MSE 0.10 vs ICP 的 5.83；FRICP：Bunny 上 0.34 s、RMSE 0.85/0.69×10^-3 [第 3.2 节](ref:tab:outlier-data) | 提升外点与部分重叠耐受 | 额外超参数/计算开销 | 外点率较高、部分重叠 |
| 收敛加速 | AA-ICP [Pavlov et al.](cite:pavlovAAICPIterativeClosest2017) | TUM RGB-D + Bunny 上中位加速约 35%，误差中位数改善约 0.3% [第 3.3 节](ref:tab:convergence-data) | 降低迭代次数 | 对噪声/非线性更敏感，仍需入盆 | 初值较好、迭代成本高 |
| 全局初始化 + 精修 | FPFH+FGR+ICP [Zhou et al.](cite:zhouFastGlobalRegistration2016) | UWA benchmark 0.05-recall 84%；FGR 在合成 range 数据噪声 σ=0.005 时平均 RMSE 0.008 [第 3.6 节](ref:tab:global-init-data) | 扩大可用初始化范围 | 额外特征与全局优化开销 | 大初始误差、易局部极小 |
| 学习化对应 | DCP [Wang and Solomon](cite:wangDeepClosestPoint2019)、RPM-Net [Yew and Lee](cite:yewRPMNetRobustPoint2020)、GeoTransformer [Qin et al.](cite:qinGeometricTransformerFast2022a) | DCP：ModelNet40 RMSE(R) 3.150°、RMSE(t) 0.0050；RPM-Net：部分可见+噪声 1.712°/0.018；GeoTransformer：3DLoMatch RR 75.0% [第 3.7 节](ref:tab:dl-data) | 低重叠或复杂扰动下更鲁棒 | 训练、域偏移与部署成本 | 对象级合成 / 室内片段对 / 低重叠片段 |
<!-- caption: 主要方法族的横向对比。表格刻画的是典型取舍与适用语境，而非跨论文可直接对比的统一数值。 -->
<!-- label: tab:method-comparison -->

**关键洞察**：

1. **初始化决定可用范围**：在大初始误差或低重叠场景下，全局初始化比局部目标函数的微调更关键；它的作用是把问题拉回 ICP 的收敛盆内，而不是单纯提高局部最优的数值精度。FGR、TEASER++ 和 GeoTransformer 的收益都属于这一类，相关数据见[第 3.6 节](ref:tab:global-init-data)和[第 3.7 节](ref:tab:dl-data)。

2. **鲁棒化经常是最先该加的一层保护**：截断、核函数或 GNC 等机制能直接处理“对应里混入了坏点”这一问题。它们解决的不是初值，而是偏置残差，因此在已入盆但外点较多时收益最直接；若初值还没进盆地，再强的鲁棒核也只能稳定地收敛到错误局部解。[第 3.2 节](ref:tab:outlier-data)里的 TrICP 和 FRICP 数据正反映了这一点。

3. **学习化方法的核心风险是域偏移与评测协议差异**：对象级合成任务与真实扫描在噪声、采样密度与遮挡模式上差异显著；横向对比时必须同时说明训练数据、测试数据与阈值设置。[第 6.2 节](ref:sec:benchmarks)已经说明 ModelNet40、3DMatch 和 KITTI 回答的并不是同一个问题。

4. **GICP 的优势在于建模统一性**：它以局部协方差统一 P2P 与 P2Pl 的误差结构，在结构化场景中常具备较稳健的收敛行为；但它依赖协方差估计和近邻选择，若局部平面假设不成立或法向估计受噪声污染，收益会先在对应建模环节消失，相关前提见[第 3.1 节](ref:tab:correspondence-data)和[第 3.4 节](ref:tab:transform-data)。

### 6.3.2 软件优化的叠加效果

[第 4 章](ref:sec:software)的软件优化策略并非互斥，工程中常按“先降规模、再降常数”的顺序叠加：先用降采样或多分辨率降低问题规模，再用数据结构、并行化与近似最近邻降低常数项开销 [Pomerleau et al.](cite:pomerleauComparingICPVariants2013)[Muja and Lowe](cite:mujaScalableNearestNeighbor2014)。

| 优化策略 | 主要收益 | 典型代价/风险 |
|---------|----------|--------------|
| 降采样（体素/法向空间/自适应） | 显著降低对应搜索次数 | 可能削弱细节约束，改变收敛盆 |
| 更快的数据结构（KD 树变体/体素哈希） | 降低最近邻常数项 | 动态更新与内存局部性权衡 |
| 并行化（SIMD/OpenMP/GPU） | 提升吞吐并降低延迟 | 并行效率受内存访问模式限制 |
| 近似最近邻（ANN） | 在可控误差下加速 | 近似误差可能引入系统性偏置 |
| 多分辨率/粗到细 | 扩大收敛盆、降低总体迭代 | 参数较多，调参成本上升 |
<!-- caption: 软件优化叠加的典型路径与取舍（定性总结）。 -->
<!-- label: tab:software-stacking -->

软件优化常能在不改变硬件的前提下实现数量级加速，尤其是在最近邻搜索与数据布局上；但其收益高度依赖点云规模、内存层级与场景结构，评测应明确软硬件配置与实现细节，参见[第 6.2 节](ref:sec:benchmarks)。

### 6.3.3 硬件加速路线的终端效果

结合[第 5 章](ref:sec:hardware-accel)的数据，专用加速器的收益主要来自对最近邻搜索与相关矩阵构建的结构化重写，尤其是[第 5.1 节](ref:sec:hardware)和[第 5.5 节](ref:sec:codesign)所示的数据通路重排。

| 路线 | 代表工作 | 主要优势 | 主要代价 |
|---------|------|-----|-----|
| FPGA | 多模式对应搜索加速器 [Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025) | 高能效、可重配置 | 开发成本与验证周期较长 |
| ASIC | Tigris 专用处理器 [Xu et al.](cite:xuTigrisArchitectureAlgorithms2019) | 极致延迟与功耗 | 灵活性低、设计前期需充分定型 |
| PIM | PICK SRAM-PIM [Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025) | 减少数据搬运，能效高 | 受存储阵列结构约束，算法耦合更强 |
<!-- caption: 典型硬件路线的代表工作与取舍（定性总结）。 -->
<!-- label: tab:hardware-comparison -->

**Pareto 视角的组合建议**（以定性原则为主）：

- **移动机器人与通用平台**：优先软件优化与稳健的局部目标（如 P2Pl/GICP），在满足延迟约束后再考虑硬件投入。
- **嵌入式与严格能耗预算**：当软件优化仍无法满足约束时，再引入 FPGA/PIM/ASIC 等路线，并在原型阶段尽量冻结数据结构与计算图，详见[第 5 章](ref:sec:hardware-accel)。

![ICP 方法全景对比雷达图](../images/ch6-method-radar.png)
<!-- caption: 六种 ICP 配置在五个维度（精度、实时性、功耗效率、鲁棒性、部署难度）上的雷达图全景对比。配置：（1）CPU 基线 P2P、（2）CPU 优化 GICP、（3）GPU ICP、（4）FPGA 多模式、（5）Tigris ASIC、（6）深度学习 RPM-Net。每个维度 1–5 为概念性评分，用于呈现典型取舍，而非严格基准测试结果。 -->
<!-- label: fig:method-radar -->
<!-- width: 0.8\textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Create a publication-quality academic figure for a thesis/survey paper.
  Use a unified academic publication figure style:
  - White background
  - Flat clean vector illustration
  - Crisp lines, balanced whitespace
  - No 3D rendering, no glossy style, no marketing aesthetics
  - Render as a conceptual trade-off diagram, not as a real benchmark chart
  Global color system and semantic consistency:
  - Main structure / compute units: deep blue #2B4C7E
  - Memory / storage related: teal blue #3C7A89
  - Data / candidate flow: orange #D17A22
  - Valid / retained / normal path: dark green #5B8C5A
  - Conflict / bottleneck / hard-to-deploy / constrained region: dark red #A23B2A
  - Text dark gray #333333
  - Borders medium gray #888888
  - Background block light gray #EDEDED
  - Keep total color count within 5-6 and preserve cross-figure consistency
  Layout:
  - Single main radar chart panel
  - Concentric rings labeled 1-5 with medium-gray gridlines
  - Legend fixed at right side, vertically aligned, compact
  - Strict alignment and generous margins
  Typography:
  - Chinese-only in-chart labeling
  - Main title largest, axis labels second, legend third, notes smallest
  - Clean academic sans-serif with good CJK support
  - Title: "ICP 配置取舍全景对比（概念示意图）"
  Axes (clockwise from top):
  - 精度
  - 实时性
  - 能效
  - 鲁棒性
  - 部署便利性
  - Scale meaning for 部署便利性: 5 = 更易部署, 1 = 更难部署
  Configurations:
  - CPU P2P 基线
  - CPU 优化 GICP
  - GPU ICP
  - FPGA 多模式
  - Tigris ASIC
  - DL RPM-Net
  Data handling:
  - Use schematic integer scores only, not benchmark measurements
  - CPU P2P 基线: 3, 2, 2, 2, 5
  - CPU 优化 GICP: 4, 3, 3, 3, 4
  - GPU ICP: 4, 4, 2, 3, 3
  - FPGA 多模式: 4, 5, 4, 4, 2
  - Tigris ASIC: 5, 5, 5, 4, 1
  - DL RPM-Net: 4, 2, 3, 5, 2
  Visual encoding:
  - Use restrained palette variants consistent with the global academic color system
  - Keep overlap readable and publication-safe
  - Stroke width about 2px, fill opacity around 0.15-0.18, no point markers
  - Avoid rainbow palette and exaggerated contrast
  Note:
  - Add a small note under the plot in dark gray:
    "注：评分为概念示意，用于表达典型取舍关系，不代表统一基准测试结果。"
-->

### 6.3.4 算法-硬件协同选择原则

综合[第 3 章](ref:sec:variants)到[第 5 章](ref:sec:hardware-accel)的讨论，可把选型原则压缩为下面四条：

**原则一：从应用约束出发，反向确定技术路线**。先明确最严格的约束（是延迟、功耗、精度还是成本），再选择能满足该约束的最简单方案，而非追求理论最优。

**原则二：优先软件优化，再考虑硬件**。降采样、近似最近邻与并行化常能提供数量级加速；只有当软件优化后仍不满足约束时，才值得投入 FPGA/ASIC 等硬件开发。

**原则三：全局初始化是鲁棒性的保险**。当初值质量不可控或低重叠频繁出现时，在 ICP 前加入全局粗配准([第 3.6 节](ref:sec:global-init))能显著扩大可用范围；是否采用取决于系统对延迟与失败率的容忍度。

**原则四：硬件设计与算法深度绑定**。FPGA/ASIC 方案一旦确定数据结构（KD-Tree、RPS 或球形桶等），后续算法变更成本极高。应在 FPGA 原型阶段充分验证算法选型，再考虑 ASIC 流片。

这些原则把“方法优劣”重新还原成“条件匹配”。真正需要避免的不是选错某一个缩写，而是在没有写清初值、重叠率和时延预算的情况下讨论优劣。[第 7 章](ref:sec:future)将继续讨论这些条件在动态场景、跨传感器泛化和硬件感知基准中的未解部分。
