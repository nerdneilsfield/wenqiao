## 3.1 对应关系建立策略 (Correspondence Strategy)
<!-- label: sec:correspondence -->

对应关系建立是 ICP 每次迭代的起点，对应的可靠性几乎直接决定了位姿更新的稳定性与收敛域。[Pomerleau et al.](cite:pomerleauReviewPointCloud2015) 用一篇长篇综述（pp. 1–110）把配准流程拆成**数据滤波 → 关联求解 → 外点剔除 → 误差最小化**四个可独立替换的模块；在其移动机器人案例里，为了卡进实时预算，甚至会直接把每帧参与匹配的点压到“几千量级”（例如随机采样 5000 点再做匹配与优化）[Pomerleau et al.](cite:pomerleauReviewPointCloud2015)。在这套框架下，“关联求解”（association solver）逐渐固化出六类常见策略。它们的差异大体可从两个维度理解：一是**用何种度量刻画源点与目标的“接近程度”**（欧氏距离、切平面距离、概率密度、几何特征相似度、语义一致性等）；二是**对应如何被建立并施加约束**（单向最近邻、双向互惠一致、软对应概率矩阵等）。

![六类 ICP 对应关系建立策略几何示意](../images/ch3-correspondence-overview.png)
<!-- caption: ICP 对应关系建立的六类策略几何示意。（a）点到点（P2P）：源点（红星）与目标最近邻（蓝点）的连线为残差；（b）点到面（P2Pl）：源点到目标切平面的有符号距离为残差；（c）对称 ICP：双侧法向量平均方向上的投影差；（d）点到线（P2L）：源点到目标线段的垂直距离（2D LiDAR 场景）；（e）NDT：目标空间划分为体素，每体素拟合高斯分布，残差为马氏距离；（f）语义引导（BSC-ICP）：仅在相同语义类别内搜索最近邻，双向互惠约束过滤歧义配对。 -->
<!-- label: fig:correspondence-overview -->
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
  Six-panel academic diagram titled "ICP 对应关系建立策略 (Correspondence Strategies)",
  white background, clean vector style, blue-orange-green palette, arranged in 2×3 grid.
  Panel (a) "P2P (点到点)": blue target points (circles) with one red source point (star),
  red dashed arrow from source to its nearest target point, label "残差 = 点间距离".
  Panel (b) "P2Pl (点到面)": blue target point with gray dashed tangent plane extending
  horizontally below it, red source point above, green perpendicular arrow from source down
  to tangent plane surface, label "残差 = 法向距离".
  Panel (c) "对称 ICP": source point (red) and target point (blue), both with outward normal
  vectors (red arrow up-left and blue arrow up-right), dashed bisector of both normals shown
  in purple, green projection arrow along bisector, label "双侧法向平均".
  Panel (d) "P2L (点到线, 2D)": horizontal blue line segment representing a wall, red source
  point above, green perpendicular drop arrow to the line, label "残差 = 到线段距离".
  Panel (e) "NDT (点到分布)": gray voxel grid, one cell highlighted blue with a 2D Gaussian
  ellipse inside (labels "μ_c" and "Σ_c"), red source point with Mahalanobis distance dashed
  arrow to ellipse center, label "残差 = 马氏距离".
  Panel (f) "语义引导 BSC-ICP": three clusters of points colored differently (blue road,
  orange pedestrian, green vehicle), arrows only within same-color clusters, double-headed
  arrows for bidirectional reciprocal matches, label "同类搜索 + 双向互惠".
  Each panel labeled "(a)"–"(f)" top-left and Chinese name at bottom center.
-->

### 3.1.1 点到点、点到面与对称 ICP

标准 ICP 的两种原始形式都基于单向最近邻。**点到点（P2P）**[Besl and McKay](cite:beslMethodRegistration3D1992) 以欧氏最近邻为对应，最小化点间距离平方和：

$$
\mathcal{E}_\text{P2P} = \frac{1}{N}\sum_{i=1}^{N} \|Rp_i + t - q_{j^*}\|^2
$$
<!-- label: eq:p2p-ch3 -->

P2P 形式上朴素，但它的工程直觉很清楚：每轮只需要做一次最近邻查询，再解一个 $SE(3)$ 的刚体最小二乘（等价于更新 6 个自由度）。在奠基论文里，[Besl and McKay](cite:beslMethodRegistration3D1992) 用几组“量级很小、但口径很具体”的实验把这件事说透了：点集示例里，8 个数据点对 11 个模型点，只跑 6 次迭代，整次 ICP 用时不到 1 s；曲线示例把一条 3D 样条用 64 个点的折线近似，并给每个点加高斯噪声，作者用 12 个初始旋转与 6 个初始平移（共 72 个初值）做全局尝试，最终在约 6 min 找到正确对齐；在“扫描对模型”的表面示例里，mask 模型用 2546 个点近似，作者用 24 个初始旋转、每个初值跑 6 次迭代，约 10 min 得到 RMS 0.59 的对齐结果[Besl and McKay](cite:beslMethodRegistration3D1992)。这些数字的价值不在于“能不能更快”，而在于它把 ICP 的算力去向摊开了：最近邻查询与初值枚举往往比后端求解更吃预算，后面很多加速与鲁棒化工作，本质上都是在改这两块的常数项。

**点到面（P2Pl）**[Chen and Medioni](cite:chenObjectModellingRegistration1992) 将残差替换为源点到目标切平面的有符号距离，即只在法向方向施加约束，从而允许点在切平面内“滑动”而不受惩罚。其原始动机是“多视角范围图建模”：在 ICRA 1991 的实现里，他们以 Mozart bust 的范围图为例展示配准流程，并在 wood blob、plaster tooth 的建模实验中采用 8 个侧视角，顶/底再补 6–8 个视角，相邻侧视角间隔约 $45^{\\circ}$；这些视角数与旋转步长决定了相邻帧的重叠比例，也解释了 P2Pl 为什么更适合做局部细化：只要重叠足够，法向方向那一条约束就能把两帧“拧”到一起[Chen and Medioni](cite:chenObjectModelingRegistration1991)。在更晚的系统对比中，[Pomerleau et al.](cite:pomerleauComparingICPVariants2013) 在 `libpointmatcher` 里给出了两条可复现的基线链（原文表 5），并在 “Challenging Laser Registration” 的 6 个真实场景（Apartment、Stairs、ETH、Gazebo、Wood、Plain）上对比 P2P 与 P2Pl。两条链共享的设置包括：先用 `MinDist` 去掉 1 m 内近距离点；对待配准点云（reading）用 `RandomSampling` 随机保留 5% 点；对应搜索用 KD-tree（近似常数 $\epsilon=3.16$）；外点用 `TrimmedDist` 做比例截断；终止条件为最多 150 次迭代或增量低于 1 cm / 0.001 rad。两者的差异主要在参考点云（reference）侧：P2P 同样随机保留 5% 点，并保留最近 75% 的对应；P2Pl 则用 `SamplingSurfaceNormal` 将下采样与法向估计合并（约 7× 下采样，阈值 7 点），并保留最近 70% 的对应。以单核 2.2 GHz Core i7 的单次配准耗时计，作者报告 P2P 的中位用时为 1.45 s、P2Pl 为 2.58 s；据此指出，P2Pl 额外的法向估计开销并未被迭代次数减少完全抵消[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。两者的目标函数推导与收敛性分析已在 [第 2.1.2 节](ref:sec:problem) 中给出，本节不再重复。

P2Pl 仅利用目标侧法向量，忽略了源点自身的法向信息。[Rusinkiewicz](cite:rusinkiewiczSymmetricObjectiveFunction2019) 于 2019 年提出**对称 ICP（Symmetric ICP）**，将残差定义为对应点对双侧法向量之和方向上的投影差：

$$
\mathcal{E}_\text{sym} = \sum_{i=1}^{N} \Bigl[ (Rp_i + t - q_i) \cdot (n_{p_i} + n_{q_i}) \Bigr]^2
$$
<!-- label: eq:symmetric-icp -->

对称目标函数线性化后可沿用与 P2Pl 相同的闭式求解器，计算开销几乎不增加。它的关键不在“多了一个法向”，而在零残差集合被扩展了：点对落在二次曲面（常曲率片）上时，对称目标依然可以做到零残差，允许配准在曲面上更自由地“贴着走”，从而把可收敛的初值范围往外推[Rusinkiewicz](cite:rusinkiewiczSymmetricObjectiveFunction2019)。作者在 Bunny 的初值盆实验里把这件事做成了可复现的数字口径：选取 `bun000` 与 `bun090` 两帧扫描（两者 IOU 约 23%），将初始误差离散成“旋转角 × 平移幅值（按模型尺寸归一化）”的二维网格，并在每个网格点上采样 1000 个随机初始变换；随后分别统计在 20/100/500 次迭代内成功收敛的比例热图（论文 Fig. 5）[Rusinkiewicz](cite:rusinkiewiczSymmetricObjectiveFunction2019)。

更关键的是，这种“收敛域更宽”并不是一句空话。[Rusinkiewicz](cite:rusinkiewiczSymmetricObjectiveFunction2019) 在 Bunny 扫描数据上把初值难度离散成二维网格（初始旋转角度、初始平移幅值，平移幅值按模型尺寸归一化），并对每个网格点采样 1000 个随机初始变换；随后分别统计在 20 次、100 次、500 次迭代内收敛的成功比例（原文图 5）。对称目标在这些热力图上的高成功率区域明显外扩，直观解释了它为什么更不容易被初值误差锁死在错误盆地：二阶曲面上残差为零，使得优化更接近“贴着曲面走”，而不是被单侧切平面强行拉回。

### 3.1.2 点到线对应（2D LiDAR 变体）

当传感器为 2D 激光雷达（SICK LMS、Hokuyo 等）时，环境可建模为平面线段集合而非三维点集。**点到线（P2L）**将残差定义为源点到最近目标线段的垂直距离：

$$
e_i = d(p_i,\; l_{j^*}), \quad l_{j^*} = \arg\min_{l_j} d(p_i, l_j)
$$
<!-- label: eq:p2l -->

[Pomerleau et al.](cite:pomerleauComparingICPVariants2013) 在 `libpointmatcher` 框架中对 P2L 进行了系统实现与对比，指出其在走廊、房间等高度结构化的 2D 场景中，收敛速度可与 P2Pl 相当，且不依赖三维法向量估计，因而更适合算力受限的平台。其主要局限在于线段提取对传感器噪声与遮挡更敏感；在植被覆盖或非结构化室外地形中，线段质量下降后，P2L 常会退回到与 P2P 类似的行为，性能优势随之减弱。

### 3.1.3 点到分布对应（Normal Distributions Transform）

**正态分布变换（NDT）**由 [Biber and Straßer](cite:biberNormalDistributionsTransform2003a) 在 IROS 2003 提出，从根本上摆脱了"显式点对点对应"的范式。其核心思路是将目标空间划分为均匀体素格网，对每个体素 $c$ 内的局部点集拟合高斯分布 $\mathcal{N}(\mu_c, \Sigma_c)$，源点的匹配代价定义为其在概率密度场中的负对数似然之和：

$$
\mathcal{E}_\text{NDT} = -\sum_{i} \exp\!\left(-\frac{(p_i' - \mu_{c(i)})^\top \Sigma_{c(i)}^{-1}(p_i' - \mu_{c(i)})}{2}\right)
$$
<!-- label: eq:ndt -->

其中 $p_i' = Rp_i + t$，$c(i)$ 为变换后源点所在体素。NDT 有两个突出优势。其一，目标函数对 $T$ 分段连续可微，可用 Newton 类方法直接优化，**无需维护显式的点对点对应列表**；体素索引可通过网格地址直接定位候选分布，从而把“对应搜索”转化为“查表 + 局部评估”。其二，对点云稀疏性更鲁棒：协方差矩阵将局部几何建模为连续分布，能够在一定程度上缓解最近邻在稀疏区域的歧义配对。为降低体素边界导致的梯度不连续，[Biber and Straßer](cite:biberNormalDistributionsTransform2003a) 采用四个互相偏移的重叠格网以平滑代价景观。

NDT 的工程说服力来自它在“没有里程计”的真实数据上仍能跑得动。[Biber and Straßer](cite:biberNormalDistributionsTransform2003a) 记录了一段室内行走数据：机器人 20 分钟行进约 83 m、共采集 28430 帧 2D 激光扫描（SICK，180° 视场，1° 角分辨率），实验中为模拟更高速度只取每 5 帧 1 帧；在 1.4 GHz 机器的 Java 实现里，单帧 NDT 构建约 10 ms、一次 Newton 迭代约 2 ms，离线处理全序列用时 58 s（约 97 scans/s）。这些数字背后对应的是它把“对应搜索”从最近邻查询替换成“体素索引 + 解析梯度/Hessian”，从而能用更少的内存随机访问换来更稳定的吞吐。

NDT 与 GICP [Segal et al.](cite:segalGeneralizedICP2009) 的本质差异在于不确定性建模的粒度：GICP 为**每个点**赋予协方差矩阵（设为各向同性时退化为 P2P，设为平面方向时退化为 P2Pl），NDT 则对**整个体素**估计一个协方差；两者共同构成了"以何种分辨率建模目标几何不确定性"这一设计轴的两端。

[Segal et al.](cite:segalGeneralizedICP2009) 的实验设置也能看出它更接近“点级概率模型 + 仍保持 ICP 的工程骨架”：对应仍用欧氏最近邻（便于 KD-tree），但在更新步里把两侧局部平面结构都写进协方差里，试图从“点到面”走向“面到面”。论文在对比中把标准 ICP 的迭代上限设为 250，而点到面与 GICP 只跑到 50 次迭代（收敛更快，且更容易在这个预算内拉开差别）；真实数据还包含 Velodyne 车载扫描的配对示例，描述为两帧扫描约 30 m 间隔、量测范围约 70–100 m 的室外场景[Segal et al.](cite:segalGeneralizedICP2009)。这些细节并不直接等价于“误差提升多少”，但它们指向 GICP 的两类收益：同样的迭代预算下更快进入稳定区；对最大匹配距离阈值 $d_{max}$ 的敏感性下降，使参数更好调。

![NDT 体素格网与高斯分布拟合示意](../images/ch3-ndt-voxel.png)
<!-- caption: NDT 对应建立原理。（左）目标点云被均匀体素格网划分（灰色网格），每个非空体素内点集拟合为二维高斯分布（蓝色椭圆），椭圆形状反映局部几何的各向异性；（中）Biber & Straßer 采用的四重偏移重叠格网（四种颜色），消除体素边界处的梯度跳变；（右）源点（红星）在体素格网中的匹配代价：落在高斯椭圆内部的点代价低（匹配概率高），远离中心的点代价高，优化目标是最大化所有源点的总匹配概率。 -->
<!-- label: fig:ndt-voxel -->
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
  Three-panel technical diagram for NDT (Normal Distributions Transform), white background,
  clean academic style, blue-gray-red color scheme.
  Left panel title "单格网 NDT": 2D scatter of blue dots (target point cloud) overlaid with
  a dashed gray grid (voxels, 4x4). In two non-empty voxels draw 2D Gaussian ellipses:
  one elongated horizontally (wall-like, anisotropic), one roughly circular (corner-like).
  Label each ellipse with "μ_c" at center and "Σ_c" next to the shape.
  Middle panel title "四重偏移格网": same blue point cloud with four overlapping grids
  in different light colors (light blue, light orange, light green, light purple),
  each offset by half a voxel width. Show offset arrows labeled "Δ/2" at the top.
  Right panel title "匹配代价": one voxel with blue Gaussian ellipse, a red star inside
  the ellipse labeled "高匹配概率 (低代价)" and another red star far outside the ellipse
  labeled "低匹配概率 (高代价)". Show dashed Mahalanobis distance arrows from both stars
  to the ellipse center. Write cost formula "-exp(-Δ^T Σ^{-1} Δ / 2)" at the bottom.
-->

### 3.1.4 特征加权对应（Geometric Feature Optimization）

标准最近邻以纯欧氏距离确定对应，在点密度不均或曲率变化剧烈的区域容易引入大量误配。典型例子是平坦区域：点在切向方向天然“模糊”，“距离近”并不等价于“几何约束强”。**GFOICP**（Geometric Feature Optimized ICP）由 [He et al.](cite:heGFOICPGeometricFeature2023)（IEEE TGRS 2023）提出，在对应建立全流程中引入**法向量角、曲率、点间距**三类几何特征，通过采样、匹配、过滤三层机制将“几何可靠性”融入目标函数。

**采样层**：以三类特征的交叉熵统计量筛选几何稳定的注册点，剔除平坦区域的冗余采样，保留曲率/法向突变的高信息量区域。**动态匹配层**：为避免“初期阈值过严导致找不到对应”，作者把距离阈值做成迭代自适应：第 $I$ 次迭代的阈值 $d^{(I)}_{TH}$ 取上一轮中对应距离的最大值，用它来过滤本轮过远的候选对应[He et al.](cite:heGFOICPGeometricFeature2023)。**特征过滤层**：以 Sigmoid 函数把几何特征相似度映射为软权重 $w_i$，再将 $w_i$ 带入目标函数：

$$
\mathcal{E}_\text{GFOICP} = \sum_i w_i\,\|Rp_i + t - q_j^*\|^2
$$
<!-- label: eq:gfoicp -->

权重函数让“看起来更像一回事”的对应更主导更新：几何特征相似度高的点对权重大，平坦或模糊区域的点对即使距离近也会被压低。论文在 Bunny 的噪声实验里给了一个很直观的量化切片：固定 $k=8$ 时，把阈值系数 $\\delta$ 从 0.05 增到 0.2，会把源/目标的注册点数从 821/1513 拉到 7707/11078，对应运行时间从 0.541 s 增到 0.840 s，但旋转/平移误差（表头标注为 $\\times 10^{-3}$）可从 2.153/0.196 降到 0.099/0.011（原文表 II）[He et al.](cite:heGFOICPGeometricFeature2023)。这类结果的含义很明确：GFOICP 的收益并不靠“更复杂的求解器”，而是靠把算力投入到更有效的约束点上；代价也同样清晰，三类特征估计需要 $k$ 近邻，在极稀疏点云或对实时性极敏感的系统里会成为预处理瓶颈。

### 3.1.5 语义引导对应（Semantic Correspondence）

仅依赖几何距离的对应，在动态场景（行人、车辆）或高度重复结构（走廊、隧道）中往往难以区分“近”与“对”。例如，行人点云的几何最近邻可能落到路面上；走廊墙面的最近邻也可能指向几何上相似、但语义上并不对应的位置。**BSC-ICP**（Bivariate Semantic Correntropy ICP）由 [Du et al.](cite:duRobustPointCloud2025)（*Fundamental Research* 2025）提出，在统一框架内融合语义标签、双向距离约束与最大相关熵准则（Maximum Correntropy Criterion, MCC）。

对应建立可概括为三步。第一步，点 $p_i$ 仅在目标点云中与其语义类别相同的子集内搜索最近邻，将搜索空间从全量 $N_q$ 收缩到同类子集，减少跨类误配。第二步，在正向匹配 $p_i \to q_{c(i)}$ 之后进行反向搜索 $q_j \to p_{d(j)}$，仅保留双向互惠一致的对应对，用互惠约束压制歧义配对。第三步，以 MCC 核加权双向联合目标函数：

$$
\max_{R,t}\;\sum_{i} \exp\!\left(-\frac{\|Rx_i + t - y_{c(i)}\|^2 + \phi(s_i - s_{c(i)})^2}{2\sigma^2}\right) + \sum_{j} \exp\!\left(-\frac{\|Rx_{d(j)} + t - y_j\|^2 + \phi(s_{d(j)} - s_j)^2}{2\sigma^2}\right)
$$
<!-- label: eq:bsc-icp -->

其中 $\phi$ 为语义惩罚系数，$\sigma$ 为带宽参数控制核的宽度。MCC 核对大残差的权重指数衰减，因此无需手动设定硬性外点阈值，噪声点与离群点常会因残差过大而被自然压低权重。[Du et al.](cite:duRobustPointCloud2025) 在语义数据集与行业场景数据上报告了更高的成功率以及更小的 RTE/RRE。其限制也很直接：语义引导对应依赖上游点云分割结果，分割误差会传导为配准失败或偏置。

[Du et al.](cite:duRobustPointCloud2025) 给出了两组能直接对上“语义约束到底值不值”的表格：在 Semantic-KITTI 上，他们报告 BSC-ICP 的 recall 为 95.7%，RTE/RRE 为 0.07 m / 0.24°，单次配准耗时 498.5 ms；对照的 ICP(P2P) recall 只有 14.3%（472.2 ms），ICP(P2Pl) 为 33.5%（461.7 ms），FGR 为 39.4%（506.1 ms）（原文表 1）。在自建煤矿数据上，BSC-ICP 的 recall 为 93.1%，RTE/RRE 为 0.02 m / 0.19°，耗时 501.5 ms；FGR 的 recall 为 78.5%，ICP(P2Pl) 为 57.9%（原文表 2）[Du et al.](cite:duRobustPointCloud2025)。这些数字有个容易被忽略的点：BSC-ICP 的时间几乎和传统 ICP 在一个量级，差别主要体现在“成功率”上，语义把那些几何上很近、但物理上不该配到一起的对应（例如车对路面、人对背景）挡在搜索阶段之外，避免了后端优化在错误对应上越迭代越偏。

### 3.1.6 对应唯一性、双向一致性与过滤策略

上述各策略均面临一个共同问题：即使找到了"最近"对应，在对称结构、重复图案或部分重叠场景中该对应仍可能存在歧义。三类过滤机制可进一步提升对应质量。

**双向一致性（Bidirectional/Reciprocal Consistency）** 要求对应 $(p_i, q_j)$ 满足互惠条件：$q_j = \arg\min_{q} \|p_i - q\|$ 且 $p_i = \arg\min_{p} \|q_j - p\|$，即双向最近邻均指向对方。这一约束又称"Picky ICP"[Pomerleau et al.](cite:pomerleauReviewPointCloud2015)，在对称形状和重复几何场景中可显著降低歧义配对率；代价是每次迭代需执行额外的最近邻搜索，计算开销会增加。

**距离阈值过滤** 用硬阈值 $d_\text{max}$ 直接丢弃距离过大的对应。[Pomerleau et al.](cite:pomerleauComparingICPVariants2013) 系统对比了硬距离阈值与比例截断策略（TrimmedDist：保留最近 $\rho$ 比例的对应），指出 TrimmedDist 对尺度变化更稳健，但需要预先给出重叠率的先验。**法向一致性过滤** 主要用于抑制跨平面误配：当对应点对两侧（reading 与 reference）估计的表面法向夹角超过 $\theta_\text{max}$ 时，直接丢弃该对应；[Pomerleau et al.](cite:pomerleauComparingICPVariants2013) 在其 7-floor mapping 的应用链中取 $\theta_\text{max}=45°$，用来避免跨楼层的错误匹配。工程实现里也常在 $30°$–$45°$ 之间取值。

**法线空间均匀采样（Normal-Space Sampling）** 针对采样策略的一个常见问题：随机采样虽高效，但采样点可能集中在法线方向相近的区域，从而对部分旋转自由度约束不足。[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001) 提出在法向方向空间中做均匀抽取，使各旋转分量都有相对均衡的约束来源。该策略在含大片平坦区域的近似平面网格（如铭刻表面、光滑金属零件）上尤其有效，常能以更少迭代更快收敛[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001)。

这篇工作还把“采样是否只是工程技巧”说得很具体：他们在 Wave、Fractal landscape、Incised plane 三个合成场景上做了受控对比（每个场景约 100k 点），每轮迭代固定抽取 2000 个点做匹配与更新；并在 550 MHz Pentium III Xeon 的 C++ 实现上展示，通过组合投影匹配、点到面误差与法线空间采样等变体，两帧 range image 的配准可以压到几十毫秒量级[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001)。这里的要点不是“某个参数取多少”，而是它把速度瓶颈拆成了可控的几个部件：采样率决定每轮算多少，匹配方式决定访存模式，误差度量决定要不要额外算法向与 Jacobian。

---

| 策略类型 | 代表方法 | 对应度量 | 优点 | 局限 |
|:---------|:---------|:---------|:-----|:-----|
| 点到点 | Besl-McKay ICP | $\|Rp_i+t-q_j\|^2$ | 实现简单，无需预计算 | 光滑曲面收敛慢 |
| 点到面 | Chen-Medioni ICP | $(n_{q_j}^\top(Rp_i+t-q_j))^2$ | 收敛更快 [Pomerleau et al.](cite:pomerleauComparingICPVariants2013) | 依赖目标法向量质量 |
| 对称 ICP | Rusinkiewicz 2019 | 双侧法向平均方向投影 | 更宽收敛域，同等计算量 | 需双侧法向量估计 |
| 点到线 | 2D LiDAR ICP | $d(p_i, l_j)^2$ | 无需三维法向量 | 局限于结构化 2D 场景 |
| 点到分布 | NDT | $-\exp(-\Delta^\top\Sigma^{-1}\Delta/2)$ | 无显式点对列表，适合稀疏点云 | 体素分辨率敏感 |
| 特征加权 | GFOICP | 几何特征 Sigmoid 权重 | 高信息区域强化约束 | 特征估计额外开销 |
| 语义引导 | BSC-ICP | MCC + 语义类别一致性 | 动态场景鲁棒 | 依赖点云分割精度 |
<!-- caption: ICP 对应关系建立策略对比 -->
<!-- label: tab:correspondence -->

| 文献 | 场景/数据集 | 指标口径 | 结果（数值） | 关键设定（便于复现） |
|------|-------------|----------|--------------|-----------------------|
| [Besl and McKay](cite:beslMethodRegistration3D1992) | 点集 / 曲线 / 曲面（论文实验小例子） | 迭代次数、初值枚举规模、端到端用时与 RMS | 点集：8 点对 11 点，6 次迭代，< 1 s；曲线：折线 64 点 + 高斯噪声，12 旋转 × 6 平移初值，约 6 min；mask 曲面：模型 2546 点，24 个初始旋转，每个初值 6 次迭代，约 10 min 得到 RMS 0.59 | 以“先枚举初值，再跑局部 ICP”的方式做全局化尝试；例子覆盖点、曲线与曲面三类表示 |
| [Pomerleau et al.](cite:pomerleauComparingICPVariants2013) | “Challenging Laser Registration” 6 场景（Apartment、Stairs、ETH、Gazebo、Wood、Plain） | 单次配准总耗时（达到终止条件） | P2P：中位 1.45 s；P2Pl：中位 2.58 s（单核 2.2 GHz Core i7） | `MinDist`（去 1 m 内点）+ `RandomSampling`（reading 保留 5%；P2P 参考端也保留 5%；P2Pl 参考端 `SamplingSurfaceNormal` 约 7×、阈值 7 点）+ KD-tree（$\epsilon=3.16$）+ `TrimmedDist`（P2P 75%，P2Pl 70%）+ 终止条件（≤150 次或 $\Delta t<1$ cm、$\Delta r<0.001$ rad） |
| [Chen and Medioni](cite:chenObjectModellingRegistration1992) | 多视角范围图建模（ICRA 1991 版实验）[Chen and Medioni](cite:chenObjectModelingRegistration1991) | 视角数、旋转步长（影响重叠与可配准性） | 侧面 8 视角 + 顶/底 6–8 视角；相邻侧视角旋转间隔约 $45^{\\circ}$ | 点到面距离最小化（避免显式点对点匹配）；要求相邻帧有足够重叠（由采样视角与步长保障） |
| [Rusinkiewicz](cite:rusinkiewiczSymmetricObjectiveFunction2019) | Bunny 扫描对（`bun000` vs `bun090`，IOU 约 23%） | 成功率：在给定迭代预算内成功收敛的比例 | 每个“初始旋转角 × 初始平移幅值（按模型尺寸归一化）”网格点采样 1000 个随机初值；分别统计在 20/100/500 次迭代内的成功率热图（Fig. 5） | 固定对应搜索 + 三种目标（P2P/P2Pl/对称）；以“收敛盆热图”对比不同目标的可用初值范围 |
| [Biber and Straßer](cite:biberNormalDistributionsTransform2003a) | 室内真实 2D 激光序列 | 处理吞吐（scans/s）与端到端耗时 | 28430 帧、20 min、约 83 m；离线处理 58 s（约 97 scans/s），NDT 构建约 10 ms/scan，Newton 单次迭代约 2 ms（1.4 GHz，Java） | SICK 180°，1° 分辨率；只取每 5 帧 1 帧；无里程计初始化（用上一步线性外推） |
| [He et al.](cite:heGFOICPGeometricFeature2023) | Bunny（噪声实验；原文表 II） | 旋转误差 ER(rad)、平移误差 Et(m)（表头标注为 ×$10^{-3}$）与时间 | 例：$k=8,\\delta=0.05$：ER 2.153、Et 0.196、0.541 s、注册点 821/1513；$k=8,\\delta=0.2$：ER 0.099、Et 0.011、0.840 s、注册点 7707/11078 | 通过 $k$ 邻域估计法向/曲率；交叉熵筛点；距离阈值按迭代自适应（取上一轮最大对应距离）+ 几何特征相似度 Sigmoid 过滤 |
| [Du et al.](cite:duRobustPointCloud2025) | Semantic-KITTI + 煤矿场景 | RTE(m)/RRE(deg)/Recall/Time(ms) | Semantic-KITTI：Ours 0.07/0.24/95.7%/498.5 ms；ICP(P2P) 0.04/0.11/14.3%/472.2 ms；FGR 0.93/0.96/39.4%/506.1 ms。煤矿：Ours 0.02/0.19/93.1%/501.5 ms；FGR 0.06/0.28/78.5%/491.6 ms | 语义同类搜索 + 双向互惠 + MCC；语义权重 $\\phi$ 与带宽 $\\sigma$ 在论文中给出经验范围并有消融曲线 |
| [Segal et al.](cite:segalGeneralizedICP2009) | 模拟扫描 + Velodyne 实测扫描对 | 迭代预算与场景尺度（实验设置层面） | 标准 ICP 最大 250 次迭代；点到面与 GICP 最大 50 次迭代；真实示例包含两帧扫描约 30 m 间隔、量测范围约 70–100 m 的室外点云对 | 对应仍用欧氏最近邻（KD-tree 友好）；更新步使用双侧局部平面协方差（“面到面”意义下的概率模型），并讨论了 $d_{max}$ 参数敏感性降低 |
<!-- caption: 第 3.1 节代表性“可复现设置 + 定量结果”汇总（仅摘录文中明确报数且口径清晰的结果）。 -->
<!-- label: tab:correspondence-data -->

对应策略的选择与场景特性密切耦合：结构化室内 2D 环境首选 P2L，稀疏车载 LiDAR 场景优先考虑 NDT 或对称 ICP，含动态目标的开放场景需 BSC-ICP 的语义过滤。外点处理与截断对应的系统分析见 [第 3.2 节](ref:sec:outlier)。
