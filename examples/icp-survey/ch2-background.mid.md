## 2. 背景与预备知识
<!-- label: sec:background -->

　　本节形式化定义点云配准问题，给出刚体变换的数学表示与基本目标函数，梳理标准 ICP 算法的步骤流程与收敛性质，并归纳典型失败模式与应对策略，为后续章节的变体分析与加速技术讨论奠定理论基础。

### 2.1 点云配准问题的数学形式化
<!-- label: sec:problem -->

#### 2.1.1 刚体变换的数学表示

　　给定源点云 $P = \{p_i\}_{i=1}^{N_p} \subset \mathbb{R}^3$ 与目标点云 $Q = \{q_j\}_{j=1}^{N_q} \subset \mathbb{R}^3$，点云配准旨在估计最优刚体变换 $T = (R, t) \in SE(3)$，使变换后的 $T(P) = \{Rp_i + t\}$ 与 $Q$ 在特定度量意义下达至最优贴合。刚体变换保持点间距离与手性不变，可统一表示为 $4\times 4$ 齐次变换矩阵：

$$
T = \begin{bmatrix} R & t \\ 0^\top & 1 \end{bmatrix}, \quad R \in SO(3), \; t \in \mathbb{R}^3
$$
<!-- label: eq:homogeneous -->

　　其中**特殊正交群** $SO(3) = \{R \in \mathbb{R}^{3\times3} \mid R^\top R = I,\, \det R = 1\}$ 刻画三维旋转，**特殊欧氏群** $SE(3)$ 则是旋转与平移的半直积，构成六维李群结构。

　　$SE(3)$ 完整描述了三维空间中刚体全部可能的位置与朝向——六个自由度中三个对应平移、三个对应旋转。齐次矩阵将旋转与平移整合于统一的 $4\times4$ 矩阵表示，连续多步变换可通过矩阵乘法 $T_2 \cdot T_1$ 直接串联，无需分开处理旋转与平移分量，显著简化复合变换的表达与计算。

　　旋转的两种主流参数化形式各具优势与适用场景。**旋转矩阵** $R \in \mathbb{R}^{3\times3}$ 满足九个约束条件（正交性约束与行列式约束），实际自由度为三；其主要优势在于与向量运算直接兼容，且 SVD 优化过程天然保持正交约束。**单位四元数** $\mathbf{q} = [q_w, q_x, q_y, q_z]^\top$（满足 $\|\mathbf{q}\| = 1$）使用四个参数表示旋转，有效避免欧拉角的万向节锁奇异性，在姿态估计与绝对定向问题中常作为旋转变量直接优化[Horn](cite:hornClosedformSolutionAbsolute1987)；旋转矩阵与四元数的转换关系由下式给出：

$$
R = \begin{bmatrix}
1-2(q_y^2+q_z^2) & 2(q_x q_y - q_w q_z) & 2(q_x q_z + q_w q_y) \\
2(q_x q_y + q_w q_z) & 1-2(q_x^2+q_z^2) & 2(q_y q_z - q_w q_x) \\
2(q_x q_z - q_w q_y) & 2(q_y q_z + q_w q_x) & 1-2(q_x^2+q_y^2)
\end{bmatrix}
$$
<!-- label: eq:quaternion-rotation -->

　　四元数从几何角度编码"绕某轴旋转某角度"的物理直觉：$q_w = \cos(\theta/2)$ 对应旋转幅度，$[q_x,q_y,q_z]^\top = \sin(\theta/2)\,\hat{u}$ 对应旋转轴 $\hat{u}$。与旋转矩阵九个元素（含六个正交性约束）相比，四元数仅需维护一个归一化约束，数值优化时更难"漂移出"合法旋转集合，因而成为惯性导航与姿态插值的首选参数化形式。

#### 2.1.2 目标函数定义

　　三维点云配准的主流目标函数可分为三类，分别对应不同的残差几何定义与优化特性。

　　**点对点（Point-to-Point, P2P）**度量直接最小化对应点间欧氏距离的平方和[Besl and McKay](cite:beslMethodRegistration3D1992)：

$$
\mathcal{E}_{\text{P2P}}(R, t) = \frac{1}{N_p}\sum_{i=1}^{N_p} \| R p_i + t - q_{\phi(i)} \|^2
$$
<!-- label: eq:p2p-objective -->

　　P2P 实现简洁，无需几何先验知识，适用范围广泛；其主要局限性在于光滑曲面上收敛速度较慢——源点沿目标曲面切线方向滑动同样可减小残差值，导致优化路径迂回曲折，而非径直朝向对齐方向收敛，迭代次数因此显著增加。

　　**点对面（Point-to-Plane, P2Pl）**度量将残差定义为源点到目标点切平面的有符号距离[Chen and Medioni](cite:chenObjectModellingRegistration1992)：

$$
\mathcal{E}_{\text{P2Pl}}(R, t) = \sum_{i=1}^{N_p} \left( \mathbf{n}_{q_{\phi(i)}}^\top (R p_i + t - q_{\phi(i)}) \right)^2
$$
<!-- label: eq:p2pl-objective -->

　　其中 $\mathbf{n}_{q_j}$ 为目标点 $q_j$ 处的单位法向量。P2Pl 允许源点沿切平面方向无惩罚滑动，等价于只保留法向方向的约束，因此在局部曲面已较稳定时更容易比 P2P 收敛更快。但它的收益建立在两个前提上：一是目标点法向估计足够稳定，二是局部曲面近似能够成立。若法向本身受噪声、稀疏采样或边界效应影响，最先出问题的就是法向投影这一步，随后法方程会沿错误法向累积偏差。[Pomerleau 等](cite:pomerleauComparingICPVariants2013)的系统评测也指出，P2Pl 的表现高度依赖场景几何结构与法向估计质量。

　　**点到分布（Point-to-Distribution, NDT）**度量将目标区域建模为局部概率分布，计算源点与分布均值的马氏距离[Biber and Stra{\ss}er](cite:biberNormalDistributionsTransform2003a)[Magnusson et al.](cite:magnussonThreeDimensionalNormalDistributions2009)：

$$
\mathcal{E}_{\text{P2D}}(R, t) = \sum_{i=1}^{N_p} (R p_i + t - \mu_{\phi(i)})^\top \Sigma_{\phi(i)}^{-1} (R p_i + t - \mu_{\phi(i)})
$$
<!-- label: eq:p2d-objective -->

　　其中 $\mu_{\phi(i)}$ 与 $\Sigma_{\phi(i)}$ 分别为目标体素内点集的高斯分布参数。NDT 最初针对二维激光匹配提出，随后扩展至三维点云配准领域；其核心思想是以体素级高斯分布替代离散点对，从而在稀疏扫描或强噪声条件下仍能提供更平滑的梯度方向，但代价在于需要预先构建体素格网结构，且格网分辨率一旦选得不合适，最先失真的是局部协方差估计，随后马氏距离会把本不应合并的局部结构一起“平均化”[Biber and Stra{\ss}er](cite:biberNormalDistributionsTransform2003a)[Magnusson et al.](cite:magnussonThreeDimensionalNormalDistributions2009)。以上三类度量在 [第 3 节](ref:sec:variants) 中还会继续展开。

　　三类残差度量并非彼此割裂独立。Generalized ICP（GICP）可被视为 P2P 与 P2Pl 之间的统一框架：该算法为每个点建立局部协方差模型，残差以两侧不确定性的加权形式表达，从而在刚性点云配准任务中兼顾收敛速度与建模鲁棒性[Segal et al.](cite:segalGeneralizedICP2009)。

#### 2.1.3 已知对应关系时的闭式解

　　当对应关系 $\phi$ 已知时，P2P 目标函数存在解析闭式解。核心技巧在于**质心解耦**：令 $\bar{p} = \frac{1}{N_p}\sum_i p_i$、$\bar{q} = \frac{1}{N_p}\sum_i q_{\phi(i)}$ 分别为源点云与目标点云的质心，$\hat{p}_i = p_i - \bar{p}$、$\hat{q}_i = q_{\phi(i)} - \bar{q}$ 为去质心后的点坐标，则最优平移由 $t^* = \bar{q} - R^*\bar{p}$ 给出，最优旋转由协方差矩阵 $W$ 的奇异值分解（SVD）确定：

$$
W = \sum_{i=1}^{N_p} \hat{q}_i \hat{p}_i^\top = U\Sigma V^\top \;\Rightarrow\; R^* = U \cdot \operatorname{diag}(1,1,\det(UV^\top)) \cdot V^\top
$$
<!-- label: eq:svd-solution -->

　　$\operatorname{diag}(1,1,\det(UV^\top))$ 修正项保证 $\det R^* = +1$（正常旋转），防止数据呈反射对称时得到镜像解。此 SVD 闭式解由 [Arun 等](cite:arunLeastSquaresFittingTwo1987)于 1987 年提出；基于单位四元数的闭式解则将问题转化为 $4\times4$ 对称矩阵的特征值问题，二者同属绝对定向（absolute orientation）问题的经典解法[Horn](cite:hornClosedformSolutionAbsolute1987)。两类解法的计算复杂度均为 $O(N_p)$（对固定维度的矩阵分解视为常数级运算），其关键技巧在于"先归零、再对准"：将两组点云各自平移至质心后，旋转与平移问题实现完全解耦。

　　然而**实际应用中对应关系 $\phi$ 在多数情况下未知**，旋转、平移与对应关系三者相互耦合，使直接求解面临指数级组合搜索空间。ICP 的核心贡献就在于把这个联合问题拆成高效的交替迭代：先利用当前变换猜测对应，再在固定对应下求解最优变换。[Besl 与 McKay](cite:beslMethodRegistration3D1992) 与 [Rusinkiewicz 与 Levoy](cite:rusinkiewiczEfficientVariantsICP2001) 都强调，这种拆分之所以实用，不是因为它消除了非凸性，而是因为它把原本难以直接求解的联合优化分解为两个可反复高效求解的子问题。

| 度量 | 约束对象 | 适合的局部几何 | 先失效的步骤 | 后果 |
|---|---|---|---|---|
| P2P | 对应点的欧氏距离 | 点分布较均匀、无需法向先验 | 最近邻把切向滑动误当成有效改进 | 收敛慢，易在平滑曲面上反复“贴边走” |
| P2Pl | 目标点法向方向距离 | 局部曲面近似稳定、法向可可靠估计 | 法向估计或法向投影失真 | 法方程沿错误法向累积偏差，局部更新失稳 |
| P2D / NDT | 点到局部高斯分布的马氏距离 | 稀疏扫描、噪声较大、希望目标更平滑 | 体素尺度不当导致局部统计失真 | 局部结构被过度平均，细节和边界约束变弱 |
<!-- caption: 第 2.1 节三类基础目标函数的适用条件与失效位置。 -->
<!-- label: tab:objective-conditions -->

![刚体变换与三类目标函数残差示意](../images/ch2-objectives.png)
<!-- caption: （左）刚体变换 $T=(R,t)$ 将源点云（红色）变换至目标点云（蓝色）坐标系；（中）三类主流目标函数残差几何定义：P2P 为点到点欧氏距离、P2Pl 为点到切平面有符号距离、P2D 为点到体素高斯分布的马氏距离（图角落给出颜色图例）；（右）SVD 质心解耦：去质心后协方差矩阵 $W$ 的奇异值分解直接给出最优旋转 $R^*$。 -->
<!-- label: fig:objectives -->
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
  Chapter 2 figure mode: background mechanism illustration.
  Focus on rigid transform representation, objective geometry, ICP iteration loop, convergence intuition, and challenge-to-failure chain.
  Each panel should explain one core relation only: geometry, optimization step, or failure mechanism.
  Do not depict unverified convergence basins or performance curves as real measured data; render them as qualitative conceptual illustrations.
  Three-panel academic diagram, white background, clean vector style, bilingual labels.
  Use a consistent palette: source points red, target points blue. Residual types color-coded:
  P2P in red, P2Pl in green, P2D/NDT in purple. Include a small legend box in the middle panel.
  Left panel (rigid transform): show two 3D point clouds as sparse dots. Red source points on left
  labeled "源点云 $P$", transformed via curved arrow labeled "$T=(R,t)$" to overlap the blue target points
  on right labeled "目标点云 $Q$". Annotate the arrow with "旋转 $R$" and "平移 $t$".
  Middle panel (three residuals): zoomed-in local geometry around one target point.
  - P2P: a red line segment from a transformed source point to its nearest blue target point, label "P2P".
  - P2Pl: draw a small dashed tangent plane patch at the target point (light gray) with normal vector arrow;
    show a green perpendicular distance from the source point to the plane, label "P2Pl".
  - P2D/NDT: show a voxel cell (light gray cube outline) containing several blue points; draw a purple
    Gaussian ellipsoid centered at mu inside the voxel, label "μ, Σ"; show a purple Mahalanobis distance
    arrow from source point toward the ellipsoid center, label "P2D/NDT".
  Right panel (SVD solution): depict two de-centered point sets "hat{P}" and "hat{Q}" with their centroids
  as stars; show the covariance matrix as a small block "W", then "W = U Σ V^T" and output formula
  "R* = U diag(1,1,det(UV^T)) V^T". Keep text minimal and readable at print size.
-->

### 2.2 经典 ICP 原始算法
<!-- label: sec:standard-icp -->

　　1992 年，[Besl 与 McKay](cite:beslMethodRegistration3D1992)（通用汽车研究实验室）与 [Chen 与 Medioni](cite:chenObjectModellingRegistration1992)（USC 信号与图像处理研究所）同年独立发表了 ICP 算法，分别面向工业零件精密检测与多视角深度图像融合场景。

#### 2.2.1 算法步骤

　　给定初始变换 $T^{(0)}$，第 $k$ 次迭代依次执行以下三个步骤。

　　**Step 1（最近点对应）** 对当前变换后的源点 $p_i^{(k)} = R^{(k)} p_i + t^{(k)}$，在目标点云中搜索欧氏最近邻：

$$
\phi^{(k)}(i) = \arg\min_{j \in \{1,\ldots,N_q\}} \| p_i^{(k)} - q_j \|_2
$$
<!-- label: eq:nn-step -->

　　**Step 2（变换求解）** 利用[式](ref:eq:svd-solution)的 SVD 闭式解，对当前对应点对 $\{(p_i,\,q_{\phi^{(k)}(i)})\}$ 求解最优变换 $(R^{(k+1)}, t^{(k+1)})$。Chen 与 Medioni 的变体在此步骤以 P2Pl 目标函数替代 P2P，利用线性化（小角度近似）求解法向约束下的最优变换。

　　**Step 3（收敛判断）** 若变换增量 $\|T^{(k+1)} - T^{(k)}\|_F < \varepsilon_T$ 或目标函数变化量 $|\mathcal{E}^{(k+1)} - \mathcal{E}^{(k)}| < \varepsilon_E$，算法停止；否则令 $k \leftarrow k+1$ 并返回 Step 1。

　　三步构成"猜测对应 → 求解变换 → 检验收敛"的闭环迭代结构：Step 1 在当前近似对齐状态下猜测点对对应关系，Step 2 在固定对应关系下求解最小二乘意义的最优刚体变换，Step 3 判断本轮迭代改进是否足够显著；一旦连续两轮变换变化量低于阈值，算法进入稳定区间，输出当前配准结果[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001)。

![ICP 迭代流程与 KD 树最近邻搜索](../images/ch2-icp-pipeline.png)
<!-- caption: （左）ICP 算法迭代循环：初始化 $T^{(0)}$ 后交替执行最近邻对应（Step 1）、SVD 变换求解（Step 2）、收敛判断（Step 3），直至满足终止条件；（右）KD 树二维示意：空间递归分割为轴对齐子盒子，查询点（红星）仅需搜索相邻少数叶节点（橙色高亮）而非全体目标点，将搜索复杂度从 $O(N^2)$ 降至 $O(N\log N)$。 -->
<!-- label: fig:icp-pipeline -->
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
  Chapter 2 figure mode: background mechanism illustration.
  Focus on rigid transform representation, objective geometry, ICP iteration loop, convergence intuition, and challenge-to-failure chain.
  Each panel should explain one core relation only: geometry, optimization step, or failure mechanism.
  Do not depict unverified convergence basins or performance curves as real measured data; render them as qualitative conceptual illustrations.
  Two-panel technical diagram, white background, clean flat design.
  Left panel: circular flow diagram for ICP iteration loop with four nodes connected by clockwise arrows:
  "初始化 $T^{(0)}$" (gray) → "Step 1: 最近邻对应" (blue) → "Step 2: 变换求解 (SVD)" (blue) →
  "Step 3: 收敛判断" (diamond). From the diamond, one green exit arrow labeled "收敛" and one red loop
  arrow labeled "未收敛" returning to Step 1. Keep node text short and aligned.
  Right panel: KD-tree nearest neighbor search in 2D emphasizing pruning/backtracking.
  Show a point set (blue dots) with KD-tree split lines (thin gray). Draw leaf cell rectangles.
  Query point is a red star. Highlight visited leaf cells in orange. Mark pruned cells with a light-gray
  cross-hatch overlay and label "剪枝 (prune)". Show a dashed backtracking arrow from one visited leaf to
  a sibling cell (label "回溯 (backtrack)"). Connect query to final nearest neighbor with a solid red line.
  Add a tiny annotation comparing "全搜索 O(N^2)" vs "KD 树 O(N log N)".
-->

#### 2.2.2 计算复杂度

　　Step 1（最近点对应）是整个 ICP 流水线的计算瓶颈。朴素实现的单步最近邻搜索复杂度为 $O(N_p \cdot N_q)$；以 KD 树预处理目标点云后，平均复杂度降至 $O(N_p \log N_q)$，但最坏情形（高维空间或退化分布）仍可回退到 $O(N_p \cdot N_q)$。[Xu 等](cite:xuTigrisArchitectureAlgorithms2019a)对点云配准流水线的实测也表明，KD 树查询是最主要的时间消耗来源之一。这里首先暴露短板的不是 SVD 这类小规模线性代数，而是树结构遍历带来的不规则访存；因此后续很多软件与硬件优化都优先针对 Step 1，而不是 Step 2。

| 步骤 | 朴素实现 | KD 树加速 |
|:-----|:---------|:---------|
| 最近邻搜索（Step 1）| $O(N_p N_q)$ | $O(N_p \log N_q)$ |
| 变换求解（Step 2）| $O(N_p)$ | $O(N_p)$ |
| 每轮迭代 | $O(N_p N_q)$ | $O(N_p \log N_q)$ |
<!-- caption: ICP 各步骤计算复杂度（$N_p \approx N_q = N$） -->
<!-- label: tab:complexity -->

#### 2.2.3 单调收敛性定理

　　[Besl 与 McKay](cite:beslMethodRegistration3D1992)严格证明了 ICP 在 P2P 度量下的单调收敛性，证明过程基于两个核心引理。

<!-- begin: theorem -->
**定理 1（P2P-ICP 的单调收敛）** 令 $\mathcal{E}(T,\phi)$ 为 P2P ICP 的目标函数。若每次迭代首先在固定 $T^{(k)}$ 下利用最近邻准则更新对应关系 $\phi^{(k+1)}$，随后在固定 $\phi^{(k+1)}$ 下利用闭式解更新变换 $T^{(k+1)}$，则目标函数序列 $\{\mathcal{E}^{(k)}\}$ 单调非增并收敛[Besl and McKay](cite:beslMethodRegistration3D1992)。
<!-- end: theorem -->

　　**引理 1（对应步不增）** 固定变换 $T^{(k)}$，重新计算最近邻对应关系时有：

$$
\mathcal{E}(T^{(k)},\,\phi^{(k+1)}) \;\leq\; \mathcal{E}(T^{(k)},\,\phi^{(k)})
$$

　　最近邻的定义保证 $\|p_i^{(k)} - q_{\phi^{(k+1)}(i)}\| \leq \|p_i^{(k)} - q_{\phi^{(k)}(i)}\|$，逐点不等式对全局目标函数依然成立。

　　**引理 2（变换步不增）** 固定对应关系 $\phi^{(k+1)}$，SVD 给出该对应下的全局最优变换，因此：

$$
\mathcal{E}(T^{(k+1)},\,\phi^{(k+1)}) \;\leq\; \mathcal{E}(T^{(k)},\,\phi^{(k+1)})
$$

　　两引理合并得到全局单调性：

$$
\mathcal{E}^{(k+1)} \;\leq\; \mathcal{E}(T^{(k)},\,\phi^{(k+1)}) \;\leq\; \mathcal{E}^{(k)}
$$
<!-- label: eq:monotone -->

　　序列 $\{\mathcal{E}^{(k)}\}$ 单调非增且有下界 0，由单调有界定理可知其收敛。

　　该证明仅依赖朴素的单调性观察：每步迭代均做出局部最优决策——最近邻对应是当前变换状态下的最优配对方式，SVD 是当前对应关系下的最优变换方式；两个"不会变差"的决策叠加，保证整体目标函数单调下降。目标函数具有自然下界 0，单调且有下界的序列因此收敛。

![ICP 收敛性证明：两个引理的几何直觉](../images/ch2-convergence-proof.png)
<!-- caption: ICP 单调收敛证明的两步直觉。（左）引理 1（对应步不增）：固定变换 $T^{(k)}$ 后重选最近邻，每个源点的对应距离只会减小或不变（灰色旧对应 → 蓝色新对应），全局目标函数因此下降。（右）引理 2（变换步不增）：固定对应后，SVD 给出该对应下的全局最优变换（蓝色最优位置 < 橙色旧位置），目标函数再次下降。右上角 inset 给出 $\mathcal{E}^{(k)}$ 随迭代的单调下降示意。 -->
<!-- label: fig:convergence-proof -->
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
  Chapter 2 figure mode: background mechanism illustration.
  Focus on rigid transform representation, objective geometry, ICP iteration loop, convergence intuition, and challenge-to-failure chain.
  Each panel should explain one core relation only: geometry, optimization step, or failure mechanism.
  Do not depict unverified convergence basins or performance curves as real measured data; render them as qualitative conceptual illustrations.
  Two-panel diagram illustrating ICP monotone decrease, white background, clean academic style.
  Left panel (Lemma 1 - correspondence step): 2D scatter plot with blue target points (circles) and one
  transformed source point (orange star). Show two correspondence lines:
  - gray dashed line to the old nearest neighbor labeled "旧对应: d_old"
  - solid blue line to the new nearest neighbor labeled "新对应: d_new ≤ d_old"
  Add a short annotation "最近邻定义 ⇒ d_new ≤ d_old". Title: "引理 1: 对应步不增".
  Right panel (Lemma 2 - transform step): show a small source fragment in two poses:
  orange semi-transparent at old pose labeled "T^(k)" and blue at improved pose labeled "T^(k+1)".
  Target points in light gray. Add a downward arrow labeled "闭式解 / 最小二乘最优".
  Title: "引理 2: 变换步不增".
  Add a small inset plot at the top-right corner: line chart of E^(k) vs iteration k with 6 points
  strictly decreasing, y-axis "E^(k)", x-axis "k", caption "单调下降". Keep inset minimal.
-->

#### 2.2.4 收敛盆地与局部最优

　　**ICP 仅保证收敛至局部极小值，不保证全局最优性**。这是标准 ICP 最重要的理论局限之一 [Besl and McKay](cite:beslMethodRegistration3D1992)，[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001)。收敛结果高度依赖初始变换 $T^{(0)}$ 的质量：当 $T^{(0)}$ 落在正确对齐的收敛盆内时，ICP 可能收敛到期望解；否则容易停在与真值相差显著的局部极小值。对称形状、重复几何结构以及部分重叠都会让这种盆地结构变得更碎，从而使“最近邻 + 最小二乘”这套局部机制在一开始就偏离正确方向[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。

　　针对此理论局限，[Yang 等](cite:yangGoICPGloballyOptimal2016)提出了 Go-ICP，在分支定界（Branch-and-Bound）框架下搜索完整的 $SE(3)$ 空间：对旋转和平移分别建立不确定包围盒，利用误差上下界做剪枝，并把局部 ICP 作为子程序嵌入搜索过程。根据该文实验总结，在 Stanford 数据与合成数据上，即使初始化随机扰动较大，Go-ICP 仍能稳定得到可靠结果；对包含部分重叠和外点的设置，结合修剪策略后可达到 100\% 配准成功率。代价也很明确：它通过扩大搜索范围换取全局性，因此运行时间比局部 ICP 高出一个甚至多个数量级，更适合作为困难帧初始化或精度上界参考，而不是高频在线前端。

![ICP 收敛盆地与局部极小值示意](../images/ch2-convergence-basin.png)
<!-- caption: （左）标准 P2P ICP 的收敛盆地（basin of convergence）：以旋转偏差 $\Delta\theta$ 为横轴，目标函数值 $\mathcal{E}$ 为纵轴，灰色区域为正确收敛盆，圆形标记为多个局部极小值；初始变换落在盆内（蓝箭头）则收敛至全局最优，落在盆外（红箭头）则陷入局部极小。（右）Go-ICP 的 $SE(3)$ 分支定界搜索示意：将旋转空间划分为立方体包围盒并递归剪枝，灰色盒子为已剪枝区域（下界高于当前全局上界），绿色标记为最终最优区间。 -->
<!-- label: fig:convergence-basin -->
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
  Chapter 2 figure mode: background mechanism illustration.
  Focus on rigid transform representation, objective geometry, ICP iteration loop, convergence intuition, and challenge-to-failure chain.
  Each panel should explain one core relation only: geometry, optimization step, or failure mechanism.
  Do not depict unverified convergence basins or performance curves as real measured data; render them as qualitative conceptual illustrations.
  Two-panel academic diagram, white background, clean vector style.
  Left panel (convergence basin as heatmap + trajectories): show a 2D heatmap of objective landscape
  over axes x="初始旋转偏差 Δθ" (0..180 deg) and y="初始平移偏差 Δt" (0..1.0 m). Use darker colors for
  higher loss, lighter for lower loss. Mark one global minimum region with a star and label "全局最优".
  Mark two local minima with small circles and label "局部极小值". Draw two short trajectory arrows:
  blue arrow starting inside the basin region converging to the star labeled "初始化成功";
  red arrow starting outside converging to a local minimum labeled "初始化失败". Add a thin boundary
  contour line around the basin labeled "收敛盆地".
  Right panel (BnB search): show a 2D grid of boxes representing discretized rotation space. Shade many
  boxes in gray with cross-hatch labeled "已剪枝". Highlight the surviving best interval as a green box
  labeled "最优区间". Include a tiny recursion tree icon to indicate splitting.
  Title above right panel: "Go-ICP (BnB 搜索)".
-->

### 2.3 ICP 的核心挑战
<!-- label: sec:challenges -->

　　尽管 ICP 算法已发展三十余年，以下五类挑战在实际工程部署中依然存在，且相互关联、彼此制约：

　　**（1）局部极小值问题**。ICP 目标函数具有非凸特性，最近邻对应关系的离散跳变产生大量局部极小值，使算法结果强烈依赖初始变换 $T^{(0)}$ 的质量。在含高度对称结构或周期性纹理的场景中，即使初始误差仅有数度旋转偏差，也可能导致算法收敛至完全错误的解。

　　**（2）对初始位姿的敏感性**。局部 ICP 的收敛盆本来就有限[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。当初始扰动过大时，最先被破坏的是最近邻对应：源点会先落到错误表面上，随后最小二乘更新沿着错误对应继续收敛，最终得到一个数值上稳定但几何上错误的解。因此，粗配准或全局初始化不是附加组件，而是把问题送入局部收敛区间的前置条件；相关方法见 [第 3.6 节](ref:sec:global-init)。

　　**（3）噪声与外点鲁棒性**。动态目标、遮挡和传感器噪声会生成错误对应。标准 ICP 对所有对应等权处理，因此坏对应一旦进入法方程，就会直接拉偏位姿更新。[Chetverikov 等](cite:chetverikovTrimmedIterativeClosest2002)讨论部分重叠与外点时已经说明，外点比例上升后，首先失效的是“最近的就是对的”这一前提，随后误差最小化阶段会把这些伪对应当成真约束。更细的鲁棒化机制见 [第 3.2 节](ref:sec:outlier)。

　　**（4）部分重叠（Partial Overlap）**。两次扫描常常只有部分区域重合，未重叠区域中的点天然找不到正确匹配，其“最近邻”只是距离最近的伪对应。这类误差不是随机噪声，而是带方向性的系统偏差：未重叠区域越大，位姿更新就越容易被拖向错误区域。[Chetverikov 等](cite:chetverikovTrimmedIterativeClosest2002)针对这一问题提出截断思想，实质上就是先减少未重叠区域对目标函数的支配，再谈局部优化。

　　**（5）计算效率瓶颈**。最近邻搜索常是配准流水线中最耗时的部分[Xu et al.](cite:xuTigrisArchitectureAlgorithms2019a)。在需要持续在线运行的系统里，最先超预算的多半也是这一步，而不是位姿更新本身。软件层面的 KD 树优化、近似最近邻与 GPU 并行化只能部分缓解这一问题；当访存不规则、点数持续增长或功耗预算过低时，系统会进一步转向专用加速器，如 Tigris、HA-BFNN 和 PICK。对应的软件与硬件路径分别见 [第 4 节](ref:sec:software) 与 [第 5 节](ref:sec:hardware)。

| 挑战 | 触发条件 | 最先失效的步骤 | 直接后果 | 主要应对方向 |
|---|---|---|---|---|
| 局部极小值 | 初始位姿偏差大、结构对称或重复 | 最近邻落入错误盆地 | 收敛到错误局部解 | [第 3.6 节](ref:sec:global-init) 的全局初始化 |
| 初始位姿敏感 | IMU 漂移、回环前位姿不准、大角度旋转 | 对应建立先错 | 后续最小二乘在错误对应上稳定收敛 | 粗配准、多分辨率、两阶段框架 |
| 外点鲁棒性 | 动态目标、遮挡、离群噪声 | 坏对应进入法方程 | 位姿更新被系统性拉偏 | [第 3.2 节](ref:sec:outlier) 的鲁棒核、截断和剪枝 |
| 部分重叠 | 未重叠区域占比高 | 非重叠点被当成近邻 | 目标函数被伪对应主导 | 截断、重叠估计、前置过滤 |
| 计算效率 | 点数大、频率高、功耗受限 | 最近邻搜索与访存 | 无法进入实时回路 | [第 4 节](ref:sec:software) 与 [第 5 节](ref:sec:hardware) |
<!-- caption: 第 2.3 节五类核心挑战的“触发条件—失效位置—后果”对应关系。 -->
<!-- label: tab:challenge-failure-chain -->

![ICP 五类核心挑战与对应解决路径](../images/ch2-challenges.png)
<!-- caption: ICP 五类核心挑战及各章节的应对策略概览。每行为一类挑战，右侧箭头指向对应的解决方向：局部极小值 → [第 3.6 节](ref:sec:global-init)；初始位姿敏感性 → [第 3.3 节](ref:sec:convergence) 与 [第 3.6 节](ref:sec:global-init)；外点鲁棒性 → [第 3.2 节](ref:sec:outlier)；部分重叠 → [第 3.2 节](ref:sec:outlier)；计算效率 → [第 4 节](ref:sec:software) 与 [第 5 节](ref:sec:hardware)。 -->
<!-- label: fig:challenges -->
<!-- width: 0.88\textwidth -->
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
  Chapter 2 figure mode: background mechanism illustration.
  Focus on rigid transform representation, objective geometry, ICP iteration loop, convergence intuition, and challenge-to-failure chain.
  Each panel should explain one core relation only: geometry, optimization step, or failure mechanism.
  Do not depict unverified convergence basins or performance curves as real measured data; render them as qualitative conceptual illustrations.
  Academic summary diagram, white background, minimal flat design, five-row table layout.
  Each row: (left) colored badge with a simple icon + Chinese challenge name; (right) one or two blue
  solution boxes with section references. Keep text short and aligned, no extra paragraphs.
  Use a consistent icon set (line icons).
  Row 1 badge orange with non-convex loss icon: "（1）局部极小值" → solution box "全局初始化 第3.6节".
  Row 2 badge orange with target-crosshair icon: "（2）初始位姿敏感性" → solution box "粗配准 + 多分辨率 第3.3节/第3.6节".
  Row 3 badge red with outlier-dots icon: "（3）外点鲁棒性" → solution box "鲁棒估计 第3.2节".
  Row 4 badge red with overlap-venn icon: "（4）部分重叠" → solution box "截断策略 第3.2节".
  Row 5 badge purple with memory/clock icon: "（5）计算效率" → two stacked solution boxes "软件加速 第4节" and "硬件加速 第5节".
  Add a tiny legend at bottom explaining badge colors: geometry/optimization (orange), data issues (red),
  system constraints (purple).
-->
