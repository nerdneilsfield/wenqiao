## 3.6 全局初始化与两阶段配准框架 (Global Initialization and Two-Stage Registration)
<!-- label: sec:global-init -->

ICP 是局部方法：它只能在当前估计附近搜索极小值，无法跨越势垒到达全局最优。这意味着在未知初始位姿的通用场景中，单独依赖 ICP 常会陷入错误盆地。第 2.2.4 节已从收敛盆地角度解释了这种敏感性。本节关注“如何把误差压入盆地”：全局配准方法通过不同策略提供粗初始值（特征匹配 + 鲁棒估计）、或通过全局搜索/可认证优化获得可靠解，再交由 ICP 完成局部精修。

![全局初始化 + ICP 精修两阶段 pipeline](../images/ch3-global-local-pipeline.png)
<!-- caption: 全局初始化 + ICP 精修的两阶段 pipeline 示意图。上行：特征提取（如 FPFH/FCGF）→ 特征匹配 → 全局估计（如 RANSAC/FGR/Go-ICP/TEASER++）→ 粗位姿 $T_\\text{global}$。下行：以粗位姿为初始值进行 ICP 局部精修，输出 $T_\\text{final}$。右侧以“误差分布逐步收敛”的形式示意：初始化误差较大，粗配准后显著收缩，ICP 精修后进一步集中。 -->
<!-- label: fig:global-local-pipeline -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Academic publication figure style for thesis/survey paper.
  White background, clean flat vector illustration, no photorealism, no 3D rendering, no poster style, no marketing style.
  Use conceptual diagram or mechanism illustration unless explicitly drawing a verified data figure from the paper.
  Emphasize structural clarity, strict alignment, readable hierarchy, balanced whitespace, crisp lines, and publication quality.
  Use consistent color mapping across all figures:
  - computation or processing units: deep blue #2B4C7E
  - storage, cache, or memory: teal blue #3C7A89
  - data flow, candidate flow, or intermediate states: orange #D17A22
  - valid region, retained path, or normal state: dark green #5B8C5A
  - conflict, bottleneck, pruned, or failed region: dark red #A23B2A
  - neutral text #333333, border #888888, light background block #EDEDED
  Limit total colors to 5-6 and keep the same semantic-to-color mapping across figures.
  Chinese-first labels, optional English in parentheses only when necessary.
  Use concise academic wording only; avoid promotional claims.
  Prefer multi-panel layout with consistent spacing and strict alignment.
  Rounded rectangles for modules, grid or bank layout for memory, horizontal chained blocks for pipelines, top-down layout for trees or hierarchies.
  Use dark red crosses, dashed lines, or fading for pruning, failure, and conflict.
  Place legend consistently at top-right or bottom-right.
  If no verified numeric data exist, do not show exact values, exact axes, exact ratios, exact timings, or fake statistics.
  Output should be suitable for thesis or survey paper.
  Chapter 3 figure mode: method-variant mechanism comparison.
  Focus on correspondence construction, outlier suppression, convergence acceleration, transform estimation, degeneracy handling, global initialization, deep registration, and solver structure.
  Use multi-panel comparative diagrams showing baseline step, modified step, failure condition, and effect on optimization path.
  If a figure is not redrawn from verified paper data, explicitly keep it conceptual and avoid exact numeric plots.
  Academic flowchart of two-stage point cloud registration pipeline, clean and publication-quality.
  Top row (global stage, blue theme):
    Left: "源点云 P" small 3D point cloud icon.
    Arrow → "特征提取 FPFH/FCGF" (histogram icon).
    Arrow → "特征对应 Matching" (two point clouds with dotted connection lines, some red outliers).
    Arrow → "全局算法 (FGR / RANSAC / TEASER)" (globe with search icon).
    Arrow → "粗位姿 T_global" (coarsely aligned point clouds, slightly off).
  Bottom row (local stage, orange theme):
    Takes "粗位姿 T_global" from top row → Arrow down.
    "ICP 精修 (Local Refinement)" (iterative arrows cycling).
    Arrow → "最终位姿 T_final" (tightly aligned point clouds, green checkmark).
  Right side: three small schematic distribution plots (not numeric) showing error narrowing:
    "初始化" wide distribution, "粗配准后" narrower, "ICP 精修后" narrowest.
  All in-figure text Chinese only. Clean white background, consistent clean style.
-->

### 3.6.1 两阶段框架的数学基础

全局粗配准 + ICP 精修的两阶段 pipeline 可以形式化为：

$$
T_\text{final} = \underbrace{\text{ICP}(T_\text{global},\,\mathcal{P},\,\mathcal{Q})}_{\text{局部精修（见第 3.1--3.4 节）}} \circ \underbrace{T_\text{global}}_{\text{全局粗配准（本节）}}
$$
<!-- label: eq:two-stage-pipeline -->

两阶段的"劳动分工"可以概括为：全局阶段负责把初始误差压入 ICP 的可收敛区域，全局方法更重视鲁棒性与覆盖性；随后由 ICP 在局部盆地内完成高精度精修。以 FGR 为例，[Zhou et al.](cite:zhouFastGlobalRegistration2016) 在 UWA benchmark（50 个场景、188 对配准测试，最低重叠率约 21%）上报告 0.05-recall 达到 84%；在这类“先把大误差压下去”的设置里，ICP 更像最后的几何抛光工序：负责把粗配准收进某个局部极小附近，而不是从零开始兜底全局搜索。

### 3.6.2 局部几何描述子

全局配准的第一步是为每个点提取旋转不变的局部几何特征，再通过特征最近邻匹配生成候选对应集。描述子的判别力（区分不同几何位置的能力）和鲁棒性（对噪声、密度变化的不敏感性）决定了候选对应集的质量。

#### 3.6.2.1 FPFH

**FPFH（Fast Point Feature Histograms）** [Rusu et al.](cite:rusuFPFHFastPoint2009) 是点云配准领域最广泛使用的手工描述子。对于点 $p$ 及其 $k$ 个近邻，计算每对 $(p, p_j)$ 的三个角特征：

$$
\alpha = \mathbf{v} \cdot \mathbf{n}_j, \quad \phi = \frac{\mathbf{u} \cdot (p_j - p)}{\|p_j - p\|}, \quad \theta = \arctan\!\left(\mathbf{w} \cdot \mathbf{n}_j,\, \mathbf{u} \cdot \mathbf{n}_j\right)
$$
<!-- label: eq:fpfh-features -->

其中 $(\mathbf{u}, \mathbf{v}, \mathbf{w})$ 为由 $p$ 的法向量和 $p$–$p_j$ 连线定义的局部坐标系，$\mathbf{n}_j$ 为近邻点 $p_j$ 的法向量。三个角特征各量化为 11 个 bin，组成 33 维直方图，对刚体变换严格不变。

**FPFH 的速度优化**：相比原始 PFH（$O(k^2)$），FPFH 先为每个点独立计算 SPFH（simplified PFH，$O(k)$），再以 SPFH 的加权组合得到 FPFH（$O(k)$），从而显著降低计算代价，使其更适合作为工程中的默认手工描述子 [Rusu et al.](cite:rusuFPFHFastPoint2009)。

在实现层面，[Rusu et al.](cite:rusuFPFHFastPoint2009) 还在 bunny00 数据集的复杂度分析中展示了“重排序 + 计算缓存”的收益：对 PFH 而言，把点云索引按空间连续性重排后再用 FIFO 缓存重用中间量，计算时间可降低约 75%（图中对比了乱序/重排两种情况）。

**局限性**：FPFH 是纯几何描述子，在平面主导或高重复结构中判别力较弱，容易产生大量歧义匹配，从而显著增加后续鲁棒估计（如 RANSAC）的负担。

![FPFH Darboux 参考系与三角特征提取](../images/ch3-fpfh-darboux-frame.png)
<!-- caption: FPFH 特征提取的几何机制示意。（a）以中心点法向与邻域连线构造 Darboux 参考系；（b）在该参考系下定义三种角特征 $(\\alpha,\\phi,\\theta)$；（c）刚体变换下参考系随点一起旋转，角特征保持不变；（d）将角特征统计为直方图并拼接为局部描述子，用于特征匹配。 -->
<!-- label: fig:fpfh-darboux-frame -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Academic publication figure style for thesis/survey paper.
  White background, clean flat vector illustration, no photorealism, no 3D rendering, no poster style, no marketing style.
  Use conceptual diagram or mechanism illustration unless explicitly drawing a verified data figure from the paper.
  Emphasize structural clarity, strict alignment, readable hierarchy, balanced whitespace, crisp lines, and publication quality.
  Use consistent color mapping across all figures:
  - computation or processing units: deep blue #2B4C7E
  - storage, cache, or memory: teal blue #3C7A89
  - data flow, candidate flow, or intermediate states: orange #D17A22
  - valid region, retained path, or normal state: dark green #5B8C5A
  - conflict, bottleneck, pruned, or failed region: dark red #A23B2A
  - neutral text #333333, border #888888, light background block #EDEDED
  Limit total colors to 5-6 and keep the same semantic-to-color mapping across figures.
  Chinese-first labels, optional English in parentheses only when necessary.
  Use concise academic wording only; avoid promotional claims.
  Prefer multi-panel layout with consistent spacing and strict alignment.
  Rounded rectangles for modules, grid or bank layout for memory, horizontal chained blocks for pipelines, top-down layout for trees or hierarchies.
  Use dark red crosses, dashed lines, or fading for pruning, failure, and conflict.
  Place legend consistently at top-right or bottom-right.
  If no verified numeric data exist, do not show exact values, exact axes, exact ratios, exact timings, or fake statistics.
  Output should be suitable for thesis or survey paper.
  Chapter 3 figure mode: method-variant mechanism comparison.
  Focus on correspondence construction, outlier suppression, convergence acceleration, transform estimation, degeneracy handling, global initialization, deep registration, and solver structure.
  Use multi-panel comparative diagrams showing baseline step, modified step, failure condition, and effect on optimization path.
  If a figure is not redrawn from verified paper data, explicitly keep it conceptual and avoid exact numeric plots.
  Four-panel academic diagram explaining FPFH feature extraction for point cloud registration.
  Layout: 2×2 grid, white background, clean vector style, consistent blue/orange palette.
  Panel (a) title "Darboux 参考系": show center point "p", neighbor "p_j", normals "n_p" and "n_j",
    and local axes "u,v,w" as arrows (no numeric annotations).
  Panel (b) title "角特征": show arcs for "α","φ","θ" with minimal formulas.
  Panel (c) title "刚体不变性": show a before/after rigid rotation sketch with a green checkmark,
    indicating the angular features are unchanged (no numeric values).
  Panel (d) title "直方图": show three mini histograms labeled "α","φ","θ" and a concatenation bracket.
  All in-figure text Chinese only; keep formulas minimal and legible.
-->

#### 3.6.2.2 FCGF

**FCGF（Fully Convolutional Geometric Features）** [Choy et al.](cite:choyFullyConvolutionalGeometric2019) 将点云转换为稀疏体素表示，以深度卷积网络（Minkowski Engine 稀疏卷积）提取 32 维描述子。训练目标函数为度量学习的对比损失：

$$
\mathcal{L} = \sum_{\text{正对}} \max(0, \|f_i - f_j\|_2 - m_p) + \sum_{\text{负对}} \max(0, m_n - \|f_i - f_j\|_2)
$$
<!-- label: eq:fcgf-loss -->

使得对应点（正对）的特征距离小于 $m_p$，非对应点（负对）的特征距离大于 $m_n$。在 3DMatch 基准（阈值 $\tau_1=0.1\,\text{m}$、$\tau_2=0.05$）上，[Choy et al.](cite:choyFullyConvolutionalGeometric2019) 报告 32 维 FCGF 的 Feature Match Recall（FMR）为 0.952（STD 0.029），同表中 FPFH 的 FMR 为 0.359（STD 0.134）。在同一工作站上统计的特征提取耗时也给得很细：原文表 1 中按“每个特征”的时间计，FCGF 为 0.019 ms；按“每帧片段”的体素化提取计，2.5 cm 体素约 0.36 s、5 cm 体素约 0.17 s。

同一论文也把“跨场景/跨传感器”的落地成本摆在明面上：作者在 KITTI 上是单独训练并评测的，并把成功条件固定为 `RTE < 2 m` 且 `RRE < 5°`。在 hardest-contrastive 训练下，20 cm 体素的 FCGF + RANSAC 得到 RTE=4.881 cm、RRE=0.170°、成功率 97.83%；对比 3DFeat 的 RTE=25.9 cm、RRE=0.57°、成功率 95.97% [Choy et al.](cite:choyFullyConvolutionalGeometric2019)。

它的局限也正写在这组结果里：一旦场景、传感器或采样尺度变了，学习到的描述子往往需要重新适配。FCGF 比 FPFH 判别力强，但也更依赖训练分布，不能把“在 3DMatch/KITTI 上有效”直接等同于“换域后仍稳”。

### 3.6.3 RANSAC 与对应过滤

随机采样一致性（RANSAC）是将任意特征描述子与刚体变换估计对接的通用框架。每次从候选对应集随机选取 3 对点（最小子集），用 Kabsch/SVD 估计变换 $T_{\text{hypo}}$，统计与 $T_{\text{hypo}}$ 一致的内点数量，取最多内点的假设为最终结果：

$$
T^* = \arg\max_{T_{\text{hypo}}} \left|\left\{(p_i, q_j) : \|T_{\text{hypo}}(p_i) - q_j\| < \tau\right\}\right|
$$
<!-- label: eq:ransac -->

RANSAC 的迭代次数下界由外点率 $\epsilon$ 和目标成功率 $P$ 决定：

$$
k \geq \frac{\log(1-P)}{\log\!\left(1 - (1-\epsilon)^s\right)}
$$
<!-- label: eq:ransac-iters -->

其中 $s=3$ 为最小子集大小。该式表明：当外点比例升高时，达到固定置信度所需的迭代次数会快速增长，尽管假设评估可并行化，整体仍可能成为粗配准阶段的主要瓶颈。RANSAC 的优势是通用、实现简单且具备概率意义上的置信度控制；其局限在于高外点率场景下效率不稳定，并高度依赖候选对应集的质量。

### 3.6.4 快速全局配准（FGR）

**FGR（Fast Global Registration）** [Zhou et al.](cite:zhouFastGlobalRegistration2016) 规避了 RANSAC 的随机采样，直接以所有候选对应同时优化 Geman-McClure 鲁棒目标函数：

$$
\mathcal{E}_\text{FGR}(T) = \sum_k \Phi_\mu\!\left(\|T(p_k) - q_k\|\right), \quad \Phi_\mu(x) = \frac{\mu x^2}{\mu + x^2}
$$
<!-- label: eq:fgr-gmc -->

其中 $\Phi_\mu$ 为 Geman-McClure 函数，对大误差（外点）提供饱和损失，对小误差（内点）近似 $L_2$。FGR 采用渐进非凸化（GNC）策略：从 $\mu \to \infty$（近凸）逐步减小 $\mu$ 到目标值，每步以前一步结果热启动，避免陷入局部极小值。FGR 的关键性质：

1. **无初始化**：目标函数从 $\mu$ 大时的凸初始状态出发，无需初始位姿猜测。
2. **迭代结构规整**：内循环主要是矩阵运算（不更新对应关系），便于高效实现与并行化 [Zhou et al.](cite:zhouFastGlobalRegistration2016)。
3. **适合作为粗配准**：在候选对应质量可控时，FGR 常被用作 ICP 前的粗配准模块，为后续局部精修提供可用起点。

FGR 的实验设置给得比较“工程化”：在合成 range 数据上，点云规模约 8,868–19,749 点、重叠率 47%–90%，并添加噪声 $\sigma\\in\\{0, 0.0025, 0.005\\}$；在最高噪声 $\sigma=0.005$ 的设置下，作者给出的平均 RMSE 为 0.008、最大 RMSE 为 0.017 [Zhou et al.](cite:zhouFastGlobalRegistration2016)。在前述 UWA benchmark 上，0.05-recall=84%（最低重叠约 21%）；所有运行时间在 i7-5960X @ 3.0GHz 单线程下统计。

**局限性**：FGR 对候选对应集的质量敏感——当匹配集合被大量误配主导时，GNC 可能收敛到错误极小值或表现不稳定。

![FGR 渐进非凸化（GNC）收敛过程](../images/ch3-fgr-gnc-schedule.png)
<!-- caption: FGR 的渐进非凸化（GNC）过程示意。（a）Geman-McClure 函数族随参数 $\mu$ 由“大到小”变化：从近似二次（更接近凸）逐步过渡到饱和型损失（更强鲁棒性）；（b）随着 $\mu$ 收紧，目标函数景观逐渐变得更非凸，但优化轨迹以“热启动”的方式延续前一阶段结果，降低陷入新出现局部极小的风险；（c）以示意曲线展示随轮次推进内点一致性增强、残差下降的趋势（不对应具体数据）。 -->
<!-- label: fig:fgr-gnc-schedule -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Academic publication figure style for thesis/survey paper.
  White background, clean flat vector illustration, no photorealism, no 3D rendering, no poster style, no marketing style.
  Use conceptual diagram or mechanism illustration unless explicitly drawing a verified data figure from the paper.
  Emphasize structural clarity, strict alignment, readable hierarchy, balanced whitespace, crisp lines, and publication quality.
  Use consistent color mapping across all figures:
  - computation or processing units: deep blue #2B4C7E
  - storage, cache, or memory: teal blue #3C7A89
  - data flow, candidate flow, or intermediate states: orange #D17A22
  - valid region, retained path, or normal state: dark green #5B8C5A
  - conflict, bottleneck, pruned, or failed region: dark red #A23B2A
  - neutral text #333333, border #888888, light background block #EDEDED
  Limit total colors to 5-6 and keep the same semantic-to-color mapping across figures.
  Chinese-first labels, optional English in parentheses only when necessary.
  Use concise academic wording only; avoid promotional claims.
  Prefer multi-panel layout with consistent spacing and strict alignment.
  Rounded rectangles for modules, grid or bank layout for memory, horizontal chained blocks for pipelines, top-down layout for trees or hierarchies.
  Use dark red crosses, dashed lines, or fading for pruning, failure, and conflict.
  Place legend consistently at top-right or bottom-right.
  If no verified numeric data exist, do not show exact values, exact axes, exact ratios, exact timings, or fake statistics.
  Output should be suitable for thesis or survey paper.
  Chapter 3 figure mode: method-variant mechanism comparison.
  Focus on correspondence construction, outlier suppression, convergence acceleration, transform estimation, degeneracy handling, global initialization, deep registration, and solver structure.
  Use multi-panel comparative diagrams showing baseline step, modified step, failure condition, and effect on optimization path.
  If a figure is not redrawn from verified paper data, explicitly keep it conceptual and avoid exact numeric plots.
  Three-panel academic vector diagram explaining FGR's GNC schedule.
  White background, flat style, all in-figure text Chinese only.
  Panel (a) "损失函数族": plot several GM curves for decreasing "μ" showing transition from quadratic-like to saturated loss (no numeric axes).
  Panel (b) "景观演化": schematic 1D loss landscape becoming more non-convex as "μ" decreases; show a warm-to-cool optimization trajectory that stays near the global basin.
  Panel (c) "趋势示意": two schematic curves over rounds: "内点一致性" increases and "残差" decreases (no numeric values).
  Keep margins generous, labels minimal, consistent blue-orange palette.
-->

### 3.6.5 Go-ICP：分支定界全局最优

**Go-ICP** [Yang et al.](cite:yangGoICPGloballyOptimal2016) 通过分支定界（Branch-and-Bound，BnB）在完整 $SE(3)$ 运动空间上搜索全局最优，理论上保证找到 $L_2$ 意义下的全局最小：

$$
T^* = \arg\min_{T \in SE(3)} \sum_i \|Tp_i - q_{NN(Tp_i)}\|^2
$$
<!-- label: eq:go-icp -->

**关键技术**：BnB 将 $SO(3)$ 分解为嵌套超正方体，对每个子块计算旋转误差的下界 $\underline{e}(C)$（基于 Euclidean distance transform 对平移做内层 BnB）。若 $\underline{e}(C) >$ 当前最优值，则剪枝整个子块。子块越小，下界越紧，剪枝越有效。Go-ICP 将局部 ICP 集成到 BnB 中：在每个旋转子块的中心运行局部 ICP 以更新全局上界，加速剪枝 [Yang et al.](cite:yangGoICPGloballyOptimal2016)。

Go-ICP 的“代价边界”在论文里有一整组量化实验：以 Stanford bunny/dragon 的 10 个 partial scan 为数据点集、重建模型为目标点集，作者把搜索域设为 $[-\\pi,\\pi]^3\\times[-0.5,0.5]^3$，每次随机生成初始位姿做 100 次测试（总计 2,000 次任务），并统一采样 $N=1000$ 个 data points、收敛阈值设为 $\\epsilon=0.001\\times N$。在这组实验里，Go-ICP（DT 最近邻距离检索）实现了 100% 正确配准；旋转误差均 <2°，平移误差均 <0.01；平均/最长运行时间分别为 bunny 1.6 s / 22.3 s、dragon 1.5 s / 28.9 s；若把 DT 换成 kd-tree，运行时间通常会再长 40–50 倍 [Yang et al.](cite:yangGoICPGloballyOptimal2016)。

进一步在“部分重叠 + 修剪”的设置里，作者给出了不同修剪比例 $\\rho$ 下的 mean/max time：例如 bunny（$\\rho=10\\%$）为 0.81 s / 10.7 s，dragon（A→B 取 $\\rho=20\\%$）为 2.99 s / 43.5 s；这组测试中点集对的重叠率在 50%–95% 之间 [Yang et al.](cite:yangGoICPGloballyOptimal2016)。这些数字也解释了它的典型定位：精度和全局性强，但不太可能长期跑在高频前端循环里。

它的局限因此也很直接：保证来自系统性的全空间搜索，而全空间搜索本身就意味着时间预算难以下到实时前端的量级。点数再大、搜索域再宽、重叠再低，BnB 的代价都会迅速抬升。

### 3.6.6 TEASER：可验证的鲁棒全局配准

**TEASER（TEASER++）** [Yang et al.](cite:yangTEASERFastCertifiable2021) 主打两件事：一是 TLS 让优化对外点“钝化”，二是把“解是否足够好”做成可检查的最优性校验。论文里把对应对下采样到 $N=1000$（Bunny），把外点率从 95% 扫到 99% 做 Monte Carlo，对比 FGR / RANSAC 等基线；在这组实验里 TEASER / TEASER++ 在 99% 外点下仍保持稳定，而 RANSAC1min 需要 60s 超时预算才能扛到 98% 外点（约 106 次迭代）[Yang et al.](cite:yangTEASERFastCertifiable2021)。

从时延上看，作者在文中直接给出一句结论：TEASER++ 在普通笔记本上可在 <10 ms 内求解“大量外点”的实例；而用于旋转子问题的最优性校验器（DRS）平均需要 24 次迭代把相对次优界压到 <0.1%，并给出“每次迭代约 50 ms（C++）”的实现量级 [Yang et al.](cite:yangTEASERFastCertifiable2021)。

核心技术仍然是三段式：

1. **截断最小二乘（TLS）**：将对应集中的外点视为"截断点"，定义

   $$
   \mathcal{E}_\text{TLS}(T) = \sum_k \min\!\left(\|Tp_k - q_k\|^2,\, \bar{c}^2\right)
   $$
   <!-- label: eq:tls -->

   $\bar{c}$ 为截断阈值，使得误差超过 $\bar{c}$ 的对应（外点）贡献固定量 $\bar{c}^2$ 而非实际误差，不影响最优化。

2. **图论框架解耦**：在对应集的相容性图（compatibility graph）上寻找一致性强的子集（如最大团/超核心等），以批量剔除明显不相容的外点，再进行尺度-旋转-平移的级联估计，降低变量耦合带来的优化难度。

3. **旋转的 SDP 松弛与紧致性检查**：TLS 旋转估计可被松弛为半定规划（SDP），并通过对偶间隙等证据检查该松弛在当前实例上是否紧致（tight）。检查通过时，可以对“解是全局最优/或足够接近全局最优”做事后校验 [Yang et al.](cite:yangTEASERFastCertifiable2021)。

**TEASER++** 进一步用更高效的分裂/迭代策略替代直接 SDP 求解，并保留“可验证（certifiable）”的核心特性。[Yang et al.](cite:yangTEASERFastCertifiable2021) 的实验显示其在高外点占优的对应集合上依然具有较强鲁棒性，因此常被视作“实时可用的可认证全局配准”代表方法之一。

但它的局限也不能略过去：TEASER++ 的前提是你手里至少得有一批“虽然很脏，但还带着几何一致性”的候选对应。如果对应图本身已经被重复结构或差特征彻底搅乱，可认证求解也无从下手；另外，它通常更适合作为触发式粗初始化，而不是每一帧都全量跑一遍。

![TEASER++ 最大团剪枝与级联估计流程](../images/ch3-teaser-pipeline.png)
<!-- caption: TEASER++ 的“剪枝 + 级联估计 + 最优性校验”流程示意。（a）在相容性图上筛除不一致对应，保留几何一致性更强的子集；（b）将尺度、旋转、平移解耦为级联估计，降低变量耦合；（c）通过对偶间隙等证据检查当前解对应的松弛是否紧致，从而对解的最优性/次优界做事后校验（示意）。 -->
<!-- label: fig:teaser-pipeline -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Academic publication figure style for thesis/survey paper.
  White background, clean flat vector illustration, no photorealism, no 3D rendering, no poster style, no marketing style.
  Use conceptual diagram or mechanism illustration unless explicitly drawing a verified data figure from the paper.
  Emphasize structural clarity, strict alignment, readable hierarchy, balanced whitespace, crisp lines, and publication quality.
  Use consistent color mapping across all figures:
  - computation or processing units: deep blue #2B4C7E
  - storage, cache, or memory: teal blue #3C7A89
  - data flow, candidate flow, or intermediate states: orange #D17A22
  - valid region, retained path, or normal state: dark green #5B8C5A
  - conflict, bottleneck, pruned, or failed region: dark red #A23B2A
  - neutral text #333333, border #888888, light background block #EDEDED
  Limit total colors to 5-6 and keep the same semantic-to-color mapping across figures.
  Chinese-first labels, optional English in parentheses only when necessary.
  Use concise academic wording only; avoid promotional claims.
  Prefer multi-panel layout with consistent spacing and strict alignment.
  Rounded rectangles for modules, grid or bank layout for memory, horizontal chained blocks for pipelines, top-down layout for trees or hierarchies.
  Use dark red crosses, dashed lines, or fading for pruning, failure, and conflict.
  Place legend consistently at top-right or bottom-right.
  If no verified numeric data exist, do not show exact values, exact axes, exact ratios, exact timings, or fake statistics.
  Output should be suitable for thesis or survey paper.
  Chapter 3 figure mode: method-variant mechanism comparison.
  Focus on correspondence construction, outlier suppression, convergence acceleration, transform estimation, degeneracy handling, global initialization, deep registration, and solver structure.
  Use multi-panel comparative diagrams showing baseline step, modified step, failure condition, and effect on optimization path.
  If a figure is not redrawn from verified paper data, explicitly keep it conceptual and avoid exact numeric plots.
  Three-stage horizontal flowchart explaining TEASER++ global registration (schematic), publication-quality academic diagram.
  White background, flat vector style, all in-figure text Chinese only.

  Stage 1 (blue theme) title "一致性剪枝":
    Show an input compatibility graph with many nodes/edges (gray), highlight a consistent subset (green) after pruning.
    Labels: "输入对应集" → "一致性子集".

  Stage 2 (orange theme) title "级联估计":
    Three boxes connected left-to-right: "尺度估计" → "旋转估计" → "平移估计".
    Add a small note below: "解耦降低变量耦合".

  Stage 3 (green/red theme) title "最优性校验":
    Box "紧致性/对偶间隙检查" branching to:
      green branch "通过: 输出结果" (checkmark),
      red branch "未通过: 启动更强求解" (warning triangle).

  Keep margins generous, consistent iconography, minimal formulas (optional), no numeric runtime annotations.
-->

### 3.6.7 GeoTransformer：端到端 Transformer 配准

**GeoTransformer** [Qin et al.](cite:qinGeometricTransformerFast2022a) 代表了一类不依赖手工描述子、也不依赖 RANSAC 的端到端方法。其核心贡献是几何自注意力（Geometric Self-Attention）模块，显式编码点对距离和三元组角度：

$$
\mathbf{r}_{ij} = \mathbf{r}_{ij}^D \mathbf{W}^D + \max_x\!\left\{\mathbf{r}_{ijx}^A \mathbf{W}^A\right\}
$$
<!-- label: eq:geotransformer -->

其中 $\mathbf{r}_{ij}^D$ 为点对距离嵌入，$\mathbf{r}_{ijx}^A$ 为三元组角度嵌入。这种显式几何编码使得特征对刚体变换更稳定，并在低重叠、重复结构等困难设置下改善内点质量 [Qin et al.](cite:qinGeometricTransformerFast2022a)。

在 3DLoMatch 上，作者报告 Inlier Ratio 提升 17–30 个百分点、Registration Recall 提升超过 7 个百分点；由于对应集合更“干净”，其实现里用确定性的 LGR（Local-to-Global Registration）替代 RANSAC，可带来约 100× 的位姿求解加速 [Qin et al.](cite:qinGeometricTransformerFast2022a)。

这类方法的局限主要在训练域和评测协议绑定得更紧。GeoTransformer 能把对应做得更干净，但前提通常是训练数据里的重叠分布、噪声形态和真实部署场景不要差得太远；一旦域偏移明显，LGR 前提下“对应已经足够好”的假设也会随之变脆。

### 3.6.8 4PCS 与 Super4PCS：无特征全局配准

**4PCS（4-Points Congruent Sets）** [Aiger et al.](cite:aiger4pointsCongruentSets2008) 用“共面四点基”把搜索空间压到几何全等约束里，本质上仍是 generate-and-test，但因为用的是宽基（wide base），在噪声/外点下更稳。论文把鲁棒性条件写得很直接：在噪声最高到 $\sigma=4.0$、外点最高到 40%、重叠率降到 30%–40% 的设置下仍能完成配准（以 LCP 思路判定），同时给出了 $O(n^2+k)$ 的提取复杂度上界 [Aiger et al.](cite:aiger4pointsCongruentSets2008)。

**Super4PCS** [Mellado et al.](cite:melladoSuper4PCSFast2014) 主要是把 4PCS 的“找固定距离点对”做成 smart indexing，复杂度从 $O(n^2)$ 变为线性（$O(n+k)$，并且对输出敏感）。作者报告在保持配准精度的前提下获得约 3–10× 的加速，并展示其在约 25% 重叠、outlier margin 约 20% 的恶劣设置下仍可用 [Mellado et al.](cite:melladoSuper4PCSFast2014)。

它们的局限则在于一旦真实重叠太低、局部几何重复严重，或者噪声把宽基约束本身也破坏了，基于全等集合的筛选效率和稳定性都会下滑。它不依赖描述子是优势，但也意味着更多信息要从几何采样本身里硬挖出来。

### 3.6.9 方法综合对比

| 方法 | 代表论文 | 思路 | 全局/可认证保证 | 鲁棒性侧重点 | 主要适用场景 |
|------|----------|------|----------------|--------------|------------|
| FPFH + RANSAC | [Rusu et al.](cite:rusuFPFHFastPoint2009) | 描述子匹配 + 采样共识 | 否（概率） | 依赖候选匹配质量 | 工程易实现、通用粗配准 |
| FPFH + FGR | [Zhou et al.](cite:zhouFastGlobalRegistration2016) | 描述子匹配 + GNC 鲁棒优化 | 否（局部） | 以鲁棒损失抑制误配 | 速度与可实现性优先的粗配准 |
| FCGF + RANSAC | [Choy et al.](cite:choyFullyConvolutionalGeometric2019) | 学习型描述子 + 采样共识 | 否（概率） | 在低纹理/低重叠中改善匹配 | 有训练数据与算力的粗配准 |
| Go-ICP | [Yang et al.](cite:yangGoICPGloballyOptimal2016) | BnB 全局搜索 | 是（全局最优） | 在受控噪声/外点下保证性强 | 精度关键、规模受限的场景 |
| TEASER++ | [Yang et al.](cite:yangTEASERFastCertifiable2021) | TLS + 图剪枝 + 可认证验证 | 是（可认证） | 高外点占优下的鲁棒粗配准 | 需要鲁棒且可验证的全局初始化 |
| GeoTransformer | [Qin et al.](cite:qinGeometricTransformerFast2022a) | 端到端学习 + 几何注意力 | 否 | 以学习特征提升对应质量 | 低重叠、重复结构的学习型粗配准 |
| Super4PCS | [Mellado et al.](cite:melladoSuper4PCSFast2014) | 无特征的几何一致采样 | 否 | 不依赖特征、依赖几何全等 | 难以稳定提取特征的场景 |
<!-- caption: 第 3.6 节全局配准方法综合对比（定性）：思路、保证类型、鲁棒性侧重点与典型适用场景。 -->
<!-- label: tab:global-init-comparison -->

| 引用工作 | 数据集/场景（原文） | 指标/阈值（原文） | 代表性数值（原文） | 关键设置/平台（原文） |
|---|---|---|---|---|
| FPFH | bunny00 等点云（复杂度分析） | PFH 计算耗时对比 | 重排序+缓存使 PFH 计算时间降低约 75% | 以空间连续性重排索引，FIFO 缓存 [Rusu et al.](cite:rusuFPFHFastPoint2009) |
| FCGF | 3DMatch | FMR（$\tau_1=0.1$m, $\tau_2=0.05$） | 0.952 ± 0.029（32 维） | 原文表 1：0.019 ms/feature；5 cm 体素约 0.17 s/fragment [Choy et al.](cite:choyFullyConvolutionalGeometric2019) |
| FCGF | KITTI | 成功：RTE<2 m 且 RRE<5° | 20 cm：RTE 4.881 cm，RRE 0.170°，成功率 97.83% | hardest-contrastive；RANSAC 后端 [Choy et al.](cite:choyFullyConvolutionalGeometric2019) |
| FGR | UWA benchmark（50 场景、188 对，最低重叠约 21%） | 0.05-recall | 84% | i7-5960X@3.0GHz 单线程 [Zhou et al.](cite:zhouFastGlobalRegistration2016) |
| FGR | 合成 range 数据 | RMSE | 噪声 $\sigma=0.005$：平均 0.008，最大 0.017 | 点数 8,868–19,749；重叠 47%–90% [Zhou et al.](cite:zhouFastGlobalRegistration2016) |
| Go-ICP | Bunny/Dragon（Stanford partial scans） | 旋转/平移误差；运行时间 | 2000 任务：rot<2°、trans<0.01；bunny 1.6 s/22.3 s；dragon 1.5 s/28.9 s | N=1000；域 $[-\\pi,\\pi]^3\\times[-0.5,0.5]^3$；DT 检索 [Yang et al.](cite:yangGoICPGloballyOptimal2016) |
| TEASER/TEASER++ | Bunny（$N=1000$） | 95%–99% 外点：旋转/平移误差箱线图 | 99% 外点下仍稳定；<10 ms（TEASER++） | RANSAC1min 需 60 s 才能扛到 98% 外点 [Yang et al.](cite:yangTEASERFastCertifiable2021) |
| GeoTransformer | 3DLoMatch | IR, RR；位姿求解耗时 | IR +17–30 个百分点；RR +>7 个点；约 100× 加速 | RANSAC-free 的 LGR 后端 [Qin et al.](cite:qinGeometricTransformerFast2022a) |
| 4PCS / Super4PCS | 多组噪声/外点/重叠设置 | 成功配准（LCP）/运行时间 | 4PCS：$\sigma$ 到 4.0、外点到 40%、重叠到 30%–40%；Super4PCS：约 3–10× 加速 | 4PCS 复杂度 $O(n^2+k)$；Super4PCS 线性/输出敏感 [Aiger et al.](cite:aiger4pointsCongruentSets2008) [Mellado et al.](cite:melladoSuper4PCSFast2014) |
<!-- caption: 第 3.6 节数据汇总：本节每个引用工作在原文中明确给出的数据集、指标与代表性数值（便于复现与横向比较）。 -->
<!-- label: tab:global-init-data -->

### 3.6.10 工程选型建议

**在线 SLAM / 激光里程计**：优先选择“易实现、稳定、可控开销”的粗配准（如 FPFH+FGR 或轻量 RANSAC）再接局部精修；若具备 GPU 与训练数据，可引入学习型方法提升低重叠与重复结构下的匹配质量。

**离线精密重建**：可更偏向鲁棒性与可验证性（如 TEASER++）并结合更强的局部模型（如 GICP/概率方法）以获得更稳定的整体质量控制。

**工业检测（精度关键）**：当需要全局保证时可考虑 Go-ICP 等全局搜索类方法；当更关注吞吐与工程复杂度时，常用“全局粗配准 + 局部精修”的组合取得足够稳定的效果。

**资源受限平台**：倾向使用手工描述子 + 轻量鲁棒估计 + 多分辨率/早停等策略，在纯 CPU 上获得可控的实时性。

[第 3.7 节](ref:sec:dl-icp) 将讨论深度学习方法如何以端到端可训练的方式统一特征提取与变换估计，并说明这种做法在低重叠与重复结构场景中的收益和边界。
