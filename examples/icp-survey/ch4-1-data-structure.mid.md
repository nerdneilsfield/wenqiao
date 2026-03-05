### 4.1 数据结构优化 (Data Structure Optimization)
<!-- label: sec:data-structure -->
<!-- label: sec:software -->

ICP 的内循环在每次迭代中对源点云 $\mathcal{P}$ 中的全部 $n$ 个点各执行一次最近邻查询（KNN，$k=1$），总查询量为 $n \times I$ 次（$I$ 为迭代次数）。当点数进入 $10^5$ 量级后，单次迭代就需要处理数百万次三维距离计算，最近邻搜索因此成为软件实现中最先触及内存访问瓶颈的环节。[Xu et al.](cite:xuTigrisArchitectureAlgorithms2019) 将这一问题作为点云处理器设计的核心负载之一，说明数据结构的选型不仅影响算法复杂度，还会改变缓存命中、访存规则性以及后续并行化空间。本节据此比较 KD-Tree、体素哈希（Voxel Hashing）与 Octree 三类主流结构，并以 ikd-Tree 说明动态地图场景下为什么需要“可维护”的索引而不只是“可查询”的索引。

![三种近邻搜索数据结构示意](figures/ds-comparison.png)
<!-- caption: 三种近邻搜索数据结构示意。左：KD-Tree 的二叉空间划分，查询时沿树路径剪枝；中：体素哈希将空间均匀量化为三维格，$O(1)$ 哈希定位候选体素；右：Octree 自适应八叉划分，密集区域细分更深。颜色深浅表示子节点点云密度。 -->
<!-- label: fig:ds-comparison -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style for all panels: white background, flat vector illustration, no realistic rendering, no 3D shading, no poster or marketing aesthetics. Treat this as a conceptual mechanism diagram rather than a measured chart unless verified data are explicitly provided. Do not fabricate exact statistics, timings, ratios, or axis values. Use consistent color mapping across all figures: compute/process modules = #2B4C7E, storage/cache/memory = #3C7A89, data flow/candidate flow = #D17A22, retained/active/valid regions = #5B8C5A, bottleneck/pruned/conflict/failure = #A23B2A, text = #333333, borders = #888888, light gray blocks = #EDEDED. Chinese-first labels with concise academic wording, rounded rectangles for modules, aligned multi-panel layout, clear arrows, minimal line crossings, crisp lines, balanced whitespace, suitable for thesis or survey paper.
  Three-panel academic diagram comparing 3D nearest neighbor data structures for ICP.
  Left panel "KD-Tree": 2D projection showing binary space partitioning with alternating
  horizontal/vertical split lines. Points shown as blue dots. Query point shown as orange star
  with search ball. Active search path highlighted in red on the binary tree structure below.
  Label: "KD-Tree O(log n) 期望查询".
  Middle panel "体素哈希 Voxel Hashing": 3D grid of colored cubes (voxels), query point
  shown with hash function symbol → direct table lookup arrow → candidate voxel highlighted.
  27 neighboring voxels shown in lighter color for exhaustive check. Label: "体素哈希 O(1) 均摊".
  Right panel "Octree": 3D recursive octant subdivision, deeper levels shown for dense regions
  (small cubes), shallow levels for sparse regions (large cubes). Query path from root to leaf
  highlighted. Label: "Octree O(log n) 自适应".
  Clean white background, consistent blue/orange color scheme, academic publication quality,
  axis labels and depth indicators included.
-->

#### 4.1.1 KD-Tree：标准实现与性能分析

KD-Tree（$k$-dimensional tree）由 Bentley 于 1975 年提出，通过在每个节点沿方差最大的坐标轴对点集进行二叉划分，构建出一棵平衡二叉搜索树。在三维点云中（$k=3$），构建过程如下：

1. 选择当前点集中方差最大的坐标轴 $d^* = \arg\max_d \text{Var}(x_d)$。
2. 取该轴的中位数 $m$ 作为分割值，将点集划分为左子树 $\{p : p_{d^*} \leq m\}$ 和右子树 $\{p : p_{d^*} > m\}$。
3. 递归地对每个子集重复，直到子集大小 $\leq$ 叶节点容量（常设为 1—10）。

构建时间为 $O(n\log n)$（含中位数选取），树高为 $O(\log n)$，空间占用 $O(n)$。单次最近邻查询的期望时间为 $O(\log n)$，但在最坏情形（点云极度非均匀分布）下退化为 $O(n)$。

**查询算法**（最佳优先搜索）：从根节点出发，根据查询点 $q$ 与分割平面的位置优先进入"更可能"的子树，同时维护当前最近邻候选和对应距离 $d_\text{best}$。在回溯时，若当前节点所在超平面到查询点的距离 $|q_{d^*} - m|$ 小于 $d_\text{best}$，则必须进入另一子树；否则整棵子树可剪枝。KD-Tree 的优势在于大多数查询只访问少量节点，但这一优势依赖点云分布与分裂轴选择。当场景近似均匀、树保持平衡时，查询路径较短；当场景退化为走廊、隧道或长条结构时，分裂平面难以快速排除候选区域，回溯次数会上升，查询时延也随之扩大。

**批量查询优化**：ICP 每次迭代需对 $n$ 个源点批量查询。若先按空间邻近度对源点分组，相邻查询多会访问相似的树路径，缓存复用会明显改善。因此，KD-Tree 在 CPU 上是否高效，不只取决于树本身是否平衡，也取决于查询顺序是否尽量减少随机访存。[Nuchter et al.](cite:nuchterCachedKdTree2007) 提出的 cached $k$-d tree 正是利用了这一点：作者在室内杂乱环境、户外场景、废弃矿井、救援竞技场和面部扫描五类数据上比较标准 $k$-d tree、近似 $k$-d tree 与缓存搜索，报告在保持精确最近邻的前提下平均约 50\% 的搜索加速。它成立的条件是相邻 ICP 迭代之间的位姿变化足够小，缓存叶节点仍具有延续性；若初值偏差大或场景切换过快，缓存命中优势会先消失。

**PCL 和 nanoflann 实现对比**：PCL（Point Cloud Library）的 KD-Tree 基于 FLANN [Muja and Lowe](cite:mujaScalableNearestNeighbor2014)，便于直接接入近似搜索与多线程查询；nanoflann 则保留更轻的模板实现，适合点云维度固定、部署环境受限的场景。前者适合快速验证与算法切换，后者更适合把查询路径和内存布局一起做细化优化。

![KD-Tree 最近邻查询剪枝过程可视化](figures/kdtree-query-pruning.png)
<!-- caption: KD-Tree 最近邻查询的分支界定（Branch-and-Bound）剪枝过程示意。左：二维 8 点的树结构与分割平面；中：查询点 $q$ 的回溯与剪枝步骤；右：用均匀分布、线性结构与聚类分布对比说明，点云几何一旦退化，KD-Tree 的回溯深度会增加。该图为机制示意，不对应具体测量数值。 -->
<!-- label: fig:kdtree-query-pruning -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style for all panels: white background, flat vector illustration, no realistic rendering, no 3D shading, no poster or marketing aesthetics. Treat this as a conceptual mechanism diagram rather than a measured chart unless verified data are explicitly provided. Do not fabricate exact statistics, timings, ratios, or axis values. Use consistent color mapping across all figures: compute/process modules = #2B4C7E, storage/cache/memory = #3C7A89, data flow/candidate flow = #D17A22, retained/active/valid regions = #5B8C5A, bottleneck/pruned/conflict/failure = #A23B2A, text = #333333, borders = #888888, light gray blocks = #EDEDED. Chinese-first labels with concise academic wording, rounded rectangles for modules, aligned multi-panel layout, clear arrows, minimal line crossings, crisp lines, balanced whitespace, suitable for thesis or survey paper.
  Three-section academic diagram explaining KD-Tree nearest-neighbor query with branch-and-bound pruning.
  Left: a small 2D point set with binary split planes and the corresponding balanced KD-Tree.
  Middle: query point q enters one branch first, reaches a leaf, then backtracks to test whether the opposite branch can be pruned.
  Right: compare uniform, corridor-like, and clustered point layouts to show that query depth and backtracking depend on geometric distribution.
  Clean academic style, white background, blue/orange color scheme, bilingual labels, mechanism illustration only, no measured percentages.
-->

#### 4.1.2 ikd-Tree：支持动态更新的增量式 KD-Tree

标准 KD-Tree 在树构建后不支持高效插入/删除。对离线配准，这一限制并不突出，因为目标点云多为固定；但对 LiDAR 里程计和建图，地图会随着机器人运动持续变化，若每次加入新点都整体重建，索引维护本身就会吞掉实时预算。

[Xu et al.](cite:xuFASTLIO2FastDirect2022) 在 FAST-LIO2 中提出 **ikd-Tree**（Incremental KD-Tree），目的不是改变 ICP 的匹配准则，而是在动态地图上把“查询”和“维护”合并到同一套索引中。FAST-LIO2 在 19 个公开序列上评测，覆盖旋转式与固态 LiDAR、无人机与手持平台，并报告了大场景中 100 Hz 的里程计与建图频率，以及最高 $1000~\mathrm{deg/s}$ 旋转条件下仍可稳定估计位姿。这些结果说明，ikd-Tree 的价值主要体现在持续更新地图时仍能保持查询可用，而不是单次静态查询一定优于所有 KD-Tree 实现。其动态操作包括：

- **增量插入**：维护部分不平衡状态，插入新点时只更新受影响路径，并在局部失衡时触发局部重平衡。这样做的理由是把维护代价限制在局部子树，而不是把实时系统拖回整树重建。
- **增量删除**（懒删除）：不立即从树中移除节点，而是先将节点标记为"已删除"，查询时跳过这些节点，待局部无效节点堆积后再统一重建。这样可以避免在每帧小幅视角变化时频繁触发重排。
- **动态重平衡**：局部重建仅在不平衡子树上进行，时间与子树大小成正比，不影响整棵树。

与 Octree、$R^*$-Tree 和静态 KD-Tree 的对比中，[Xu et al.](cite:xuFASTLIO2FastDirect2022) 将 ikd-Tree 描述为在增量更新场景下总体更均衡的方案：查询性能保持在 KD-Tree 量级，而插入、删除和局部重建不再迫使系统每帧整树重建。它成立的前提是场景以连续运动为主、每次更新只改变局部地图；若环境快速进出大量动态物体，懒删除节点会持续累积，局部重建频率上升，维护收益就会下降。

![ikd-Tree 增量更新机制](figures/ikd-tree.png)
<!-- caption: ikd-Tree 增量更新机制示意。左：新点插入后仅在局部子树重平衡；中：懒删除节点保留到批量清理；右：用归一化曲线说明连续更新场景下，局部维护比逐帧整树重建更稳定。该图为机制示意，不对应具体测量数值。 -->
<!-- label: fig:ikd-tree -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style for all panels: white background, flat vector illustration, no realistic rendering, no 3D shading, no poster or marketing aesthetics. Treat this as a conceptual mechanism diagram rather than a measured chart unless verified data are explicitly provided. Do not fabricate exact statistics, timings, ratios, or axis values. Use consistent color mapping across all figures: compute/process modules = #2B4C7E, storage/cache/memory = #3C7A89, data flow/candidate flow = #D17A22, retained/active/valid regions = #5B8C5A, bottleneck/pruned/conflict/failure = #A23B2A, text = #333333, borders = #888888, light gray blocks = #EDEDED. Chinese-first labels with concise academic wording, rounded rectangles for modules, aligned multi-panel layout, clear arrows, minimal line crossings, crisp lines, balanced whitespace, suitable for thesis or survey paper.
  Three-panel academic diagram illustrating ikd-Tree incremental update mechanism.
  Left panel "增量插入 (Incremental Insertion)": binary tree diagram where new nodes shown in green
  are being inserted. Subtree needing rebalance highlighted in orange with alpha imbalance ratio
  formula shown: α = |N_L - N_R|/(N_L + N_R) > 0.3. Rebalancing arrows in orange.
  Middle panel "懒删除 (Lazy Deletion)": same tree with some nodes marked with grey X symbols
  (deleted nodes). Query path shown skipping deleted nodes. Threshold β_th shown with counter.
  Right panel "性能对比 (Performance Comparison)": line chart showing query time (normalized)
  vs number of frames (1-100). Three lines:
  - Static KD-Tree rebuilt each frame: starts at 1.0, increases to ~8x after 100 frames
  - Octree: starts at 1.0, increases to ~5x
  - ikd-Tree: flat near 1.0-1.2x throughout
  X-axis: "帧数 (Frames)", Y-axis: "归一化查询时间 (Normalized Query Time)".
  White background, clean publication style, blue/orange/green colors for each method.
-->

#### 4.1.3 体素哈希（Voxel Hashing）

体素哈希将三维空间均匀量化为边长 $r$ 的立方体体素，用哈希表（或固定大小的 bucket 数组）存储每个体素内的点集：

$$
\text{key}(p) = \left(\left\lfloor \frac{p_x}{r} \right\rfloor,\ \left\lfloor \frac{p_y}{r} \right\rfloor,\ \left\lfloor \frac{p_z}{r} \right\rfloor\right)
$$
<!-- label: eq:voxel-key -->

查询时，计算查询点 $q$ 所在体素坐标，通过哈希函数 $h(\text{key})$ 在 $O(1)$ 时间内定位该体素及其 $3^3-1=26$ 个面、棱、角邻域体素（共 27 个），再对这 27 个体素内的所有点暴力搜索最近邻。体素哈希的关键优势在于：

1. **插入/删除 $O(1)$**：新点直接插入对应体素的桶（bucket），无需重建树结构，天然支持动态 LiDAR 点云地图。
2. **内存访问规律**：27 个邻域体素在哈希表中的访问模式固定，GPU 可预取（prefetch）邻域数据，缓存友好度高于 KD-Tree 的随机树遍历。
3. **并行化极为简单**：每个查询点的 27 个体素检索相互独立，直接分派到 GPU 线程。

体素哈希的主要劣势在于精度受分辨率 $r$ 约束：若 $r$ 过大，候选集会把多个几何结构混入同一体素，最近邻分辨率下降；若 $r$ 过小，哈希表会过稀，访存与管理开销反而上升。因此，体素哈希并不是“总比 KD-Tree 快”，而是只在查询半径、点间距和硬件访存模式相互匹配时才真正占优。

对于室内或实验室环境这类点密度相对均匀的场景，体素哈希更容易保持固定的候选规模；但在室外 LiDAR 扫描中，点密度随距离迅速衰减，远处体素可能几乎没有有效候选，此时查询质量更依赖体素尺度是否随距离调整，否则对应关系会先在稀疏区域失真。

![体素哈希 27 邻域访问模式与 GPU 线程映射](figures/voxelhash-gpu-access.png)
<!-- caption: 体素哈希的 27 邻域访问模式及其与 GPU 并行架构的对应关系。左：查询点落入中心体素后，只需检查固定邻域中的候选体素；右：每个查询点可映射到独立线程，说明这种规则访问模式比树遍历更容易在 GPU 上保持同步执行。该图为机制示意，不对应具体 GPU 利用率数值。 -->
<!-- label: fig:voxelhash-gpu-access -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style for all panels: white background, flat vector illustration, no realistic rendering, no 3D shading, no poster or marketing aesthetics. Treat this as a conceptual mechanism diagram rather than a measured chart unless verified data are explicitly provided. Do not fabricate exact statistics, timings, ratios, or axis values. Use consistent color mapping across all figures: compute/process modules = #2B4C7E, storage/cache/memory = #3C7A89, data flow/candidate flow = #D17A22, retained/active/valid regions = #5B8C5A, bottleneck/pruned/conflict/failure = #A23B2A, text = #333333, borders = #888888, light gray blocks = #EDEDED. Chinese-first labels with concise academic wording, rounded rectangles for modules, aligned multi-panel layout, clear arrows, minimal line crossings, crisp lines, balanced whitespace, suitable for thesis or survey paper.
  Two-section academic diagram explaining voxel hashing 27-neighbor access pattern and GPU thread mapping.
  Left: a 3D voxel grid showing the center voxel of query point q and its 27-neighbor candidate region, with a schematic hash table lookup.
  Right: map one query point to one GPU thread and show that all threads in the same warp execute the same fixed neighbor-check loop, contrasting this with irregular tree traversal.
  White background, consistent orange/green/blue color scheme, bilingual labels, mechanism illustration only, no measured utilization numbers.
-->

#### 4.1.4 Octree：自适应空间分解

Octree 将空间递归地八等分，直到每个叶节点的包含点数低于阈值 $N_\text{leaf}$（工程上多设为 1—8）。与 KD-Tree 的随机维度划分不同，Octree 的划分轴固定为三个坐标轴的中点，使得每层的划分线形成规则的三维网格，树结构更均匀。

Octree 的主要特性：

- **空间感知**：Octree 的节点天然对应空间区域，便于基于空间范围的批量查询（例如查找半径 $r$ 内所有点）——ICP 在法向量计算、曲率估计等前处理步骤中需要此类查询。
- **自适应分辨率**：稠密区域节点深度大（分辨率高），稀疏区域节点深度小（节省内存），对非均匀 LiDAR 点云有良好的空间利用率。
- **GPU 并行友好**：Octree 节点的 8 路分支因子与 GPU 硬件的 warp/wavefront（32/64 线程）不匹配，需要用 SIMD 宽度设计特殊的打包方式；相比之下，体素哈希的规则访问模式在 GPU 上更高效。

PCL 和 Open3D 均提供 Octree 实现；[Bakhshalipour and Gibbons](cite:bakhshalipourTartanMicroarchitectingRobotic2024) 讨论专用机器人处理器时，也将规则化访存视为点云处理加速的重要前提。这类工作提示了 Octree 的一个现实价值：它不一定在单次查询上最优，但更容易与专用缓存策略和片上数据流协同设计。

#### 4.1.5 各数据结构综合对比与选型建议

| 数据结构 | 构建时间 | KNN 查询期望 | 动态插入/删除 | GPU 并行友好 | 内存占用 | 最适场景 |
|---------|---------|------------|-------------|------------|---------|---------|
| 静态 KD-Tree | $O(n\log n)$ | $O(\log n)$ | 差（重建 $O(n)$） | 低（不规则遍历） | $O(n)$ | 离线配准，密度均匀 |
| ikd-Tree | $O(n\log n)$（初始） | $O(\log n)$ | 好（均摊 $O(\log n)$）| 低 | $O(n)$ | LiDAR 里程计增量建图 |
| 体素哈希 | $O(n)$ | $O(1)$ 均摊 | 极好（$O(1)$） | 极高 | $O(n/r^3)$ | GPU 加速，动态地图 |
| Octree | $O(n\log n)$ | $O(\log n)$ | 中（局部更新） | 中 | $O(n)$ | 范围查询，非均匀密度 |
| Approx. KD-Forest | $O(Tn\log n)$ | $O(T\log n)$ | 差 | 低 | $O(Tn)$ | 高维特征 KNN |
<!-- caption: [第 4.1 节](ref:sec:data-structure)中近邻搜索数据结构的综合对比：各维度定性评估。 -->
<!-- label: tab:data-structure-comparison -->

**选型决策树**：

- 离线配准（无实时约束）$\Rightarrow$ 静态 KD-Tree + FLANN 近似搜索。
- 实时 LiDAR SLAM（CPU 部署）$\Rightarrow$ ikd-Tree（增量更新）。
- GPU 加速 ICP $\Rightarrow$ 体素哈希（规则访问 + $O(1)$ 查询）。
- 点云密度高度非均匀（航空 LiDAR） $\Rightarrow$ Octree（自适应分辨率）。

数据结构的选型不仅影响 KNN 搜索速度，还直接决定下游加速策略是否成立。[并行化一节](ref:sec:parallelism) 会进一步说明，GPU 更依赖规则访问的候选组织方式；而面向专用硬件时，HA-BFNN-ICP [Liu et al.](cite:liuHABFNNICPStreamingFPGA2025) 与 Tigris [Xu et al.](cite:xuTigrisArchitectureAlgorithms2019) 分别代表两种思路：前者用顺序流式搜索换取稳定的数据通路，后者尝试把 KD-Tree 的不规则遍历拆解成硬件可调度的细粒度操作。它们都说明，索引结构不是前处理细节，而是后续体系结构设计的输入约束。
