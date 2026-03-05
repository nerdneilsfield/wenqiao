## 3.8 优化求解器视角

<!-- label: sec:opt-solvers -->

SVD 是 ICP 位姿求解的起点，却不是终点。点到平面残差的非线性结构、鲁棒 M-估计器的加权迭代、稀疏范数的变量分裂，以及因子图的增量平滑，均要求超越闭合解的迭代优化框架。本节以统一的最小二乘视角梳理这些求解器，并揭示它们与[第 3.2 节](ref:sec:outlier)（异常值处理）、[第 3.4 节](ref:sec:transform)（变换估计）和[第 3.5 节](ref:sec:degeneracy)（退化感知）各节的内在联系。

### 3.8.1 最小二乘统一框架

<!-- label: sec:opt-framework -->

ICP 的位姿求解可统一表述为加权非线性最小二乘（NLS）问题。设源点 $p_i$、目标点 $q_i$，变换 $T = (R, t) \in SE(3)$，残差 $e_i(T)$ 随度量类型而异：

$$
\min_{T \in SE(3)} \sum_{i=1}^{n} \rho\!\left(\|e_i(T)\|^2\right)
$$

<!-- label: eq:nls-icp -->

三种主流残差的具体形式为：P2P 残差 $e_i = Rp_i + t - q_i$；P2Pl 残差 $e_i = n_i^\top (Rp_i + t - q_i)$（$n_i$ 为目标点法向量）；Symmetric-ICP 残差 $e_i = (n_i + m_i)^\top (Rp_i + t - q_i)/2$，其中 $m_i$ 为源点法向量。

当 $\rho(s) = s$（无鲁棒核）时，对 $T$ 在当前估计 $T_0$ 处做左扰动 $T' = \exp(\hat{\xi}) \cdot T_0$（$\xi \in \mathfrak{se}(3)$），一阶 Taylor 展开给出线性化残差 $e_i(T') \approx e_i(T_0) + J_i \xi$，其中 $J_i \in \mathbb{R}^{k \times 6}$ 为 Jacobian。令梯度为零得正规方程：

$$
\underbrace{J^\top W J}_{H} \,\xi^* = -J^\top W e
$$

<!-- label: eq:normal-eq -->

其中 $W = \text{diag}(w_1, \ldots, w_n)$ 为权重矩阵，$J$ 和 $e$ 是各残差的堆叠。P2P 情形下 $H$ 具有特殊的解析结构，可用 SVD 精确求解，这正是[第 3.4 节](ref:sec:transform) Kabsch 算法的来源，也是[式](ref:eq:normal-eq)在 $W = I$、$k = 3$ 时的特例 [Sola 等](cite:solaMicroLieTheory2018)。P2Pl 情形下 $H \in \mathbb{R}^{6 \times 6}$，无闭合解，须迭代求解。

### 3.8.2 Gauss-Newton 与 Levenberg-Marquardt

<!-- label: sec:gn-lm -->

**Gauss-Newton（GN）** 用 $H = J^\top W J$ 近似 Hessian，解线性系统得到增量 $\delta\xi$：
$$
H\,\delta\xi = -J^\top W e.
$$
对 ICP 而言，关键不是“会不会解线性系统”，而是 **Jacobian 到底长什么样**。以点到面残差为例，
$
r_i(T)=n_i^\top(Rp_i+t-q_i)
$
（$n_i$ 为目标点法向），对当前估计 $(R,t)$ 做小扰动 $(\delta\theta,\delta t)$，有一阶近似：
$$
r_i(T') \approx r_i(T) + 
\underbrace{\begin{bmatrix}
(Rp_i\times n_i)^\top & n_i^\top
\end{bmatrix}}_{J_i}\!
\begin{bmatrix}\delta\theta\\ \delta t\end{bmatrix}.
$$
于是每个对应点对都只往一个 $6\times6$ 的 $H=\sum_i w_i J_i^\top J_i$ 和 $g=\sum_i w_i J_i^\top r_i$ 里“加一笔”，最后解 $H\,\delta\xi=-g$。这里真正的开销在于遍历点对装配（$O(n)$），而不是求解本身（Cholesky 分解只是常数规模）。GN 在接近最优解时收敛快，但它对初值的依赖很强：一旦线性化偏离真实残差形状（重叠不足、外点占比高、退化方向明显），就容易走偏甚至发散。

**Levenberg-Marquardt（LM）** 引入阻尼项将正规方程改为：

$$
(J^\top W J + \lambda I)\,\delta\xi = -J^\top W e
$$

<!-- label: eq:lm-update -->

$\lambda > 0$ 时可把它理解为“带正则的 GN”，或者更直白一点：**先把一步走得过大的风险压下去**。$\lambda$ 大时更像梯度下降（收敛盆更大，但步子小），$\lambda \to 0$ 时恢复 GN 的二次收敛速率。工程上 LM 的价值主要体现在两点：一是当 $H$ 条件数很差、甚至接近奇异（走廊、平面等退化结构）时，$\lambda I$ 往往能把系统“扶正”，避免数值崩掉；二是配合信赖域策略（根据“这一步带来多大真实下降”来调 $\lambda$），能在“快”和“稳”之间自动切换。

KISS-ICP 的位姿求解核心就是 LM：它用 $\lambda$ 和数据关联阈值一起自适应调节更新强度，把前端的抖动压到能稳定跑实时的范围里 [Vizzo 等](cite:vizzoKISSICPDefensePointtoPoint2022)。论文把系统参数写得很简洁，全系统只有 7 个自由参数（原文表 I），其中包括初始关联阈值 $\tau_0=2\\,\\text{m}$、最小位移阈值 $\\delta_{min}=0.1\\,\\text{m}$、每体素点数上限 $N_{max}=20$、ICP 收敛阈值 $\\gamma=10^{-4}$；在 KITTI-raw 上，含 deskewing 的运行频率约为 38 Hz[Vizzo 等](cite:vizzoKISSICPDefensePointtoPoint2022)。这里能看出的事实是：LM 用阻尼项控制更新步长，所以在 Hessian 条件数差、对应抖动或初值偏差中等时，迭代还能继续走下去；但它不能扩大收敛域。初值一旦落入错误盆地，或者对应关系已经系统性出错，LM 只会在错误方向上收敛。

![GN 与 LM 收敛行为对比](../images/ch3-gn-lm-convergence.png)
<!-- caption: （a）P2P 与 P2Pl 目标函数在切空间的损失曲面示意：P2P 往往“更圆”（条件更好），P2Pl 在某些结构场景下更“狭长”（更病态）；（b）GN 与不同阻尼强度的 LM 从同一初始点出发的迭代轨迹：弱阻尼更接近 GN（收敛快但更依赖初值），强阻尼更接近梯度下降（更稳但更慢）；（c）不同度量构造的 Hessian 条件性对数值求解难度的影响示意（定性）。 -->
<!-- label: fig:gn-lm-convergence -->
<!-- width: 0.95\textwidth -->
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
  Three-panel academic diagram (schematic) comparing GN and LM behavior in ICP optimization.
  White background, clean vector style, all in-figure text Chinese only.

  Panel (a): 2D contour plot overlay:
  - Blue contours labeled "P2P 损失面" as a wide, round basin.
  - Orange contours labeled "P2Pl 损失面" as a long, narrow basin (ill-conditioned).
  - Axes labeled "切空间方向 1" and "切空间方向 2" (no units).
  - Mark the minimum with a star labeled "最优".

  Panel (b): Same landscape with three trajectories from the same start point:
  - "GN" (blue): short path, turns sharply near the minimum.
  - "LM（弱阻尼）" (orange): between GN and GD.
  - "LM（强阻尼）" (green): long, smooth path that first behaves like gradient descent then refines.
  - Add arrowheads for steps, no numeric annotations.

  Panel (c): Qualitative grouped bar chart "数值条件性（定性）":
  - Three groups: "平面", "走廊", "一般".
  - Three bars per group: "P2P", "P2Pl", "对称 ICP".
  - Heights are qualitative (e.g., P2Pl lower in corridor), no numeric axis.
-->

### 3.8.3 IRLS 与 M-估计器

<!-- label: sec:irls -->

当 $\rho(\cdot)$ 为鲁棒函数（如 Huber、Cauchy、Geman-McClure）时，目标函数不再是标准 LS，无法直接套用 GN。**迭代加权最小二乘（IRLS）** 将非 LS 问题转化为一系列加权 LS 子问题：固定当前估计 $T_k$，计算权重：

$$
w_i = \frac{\rho'\!\left(\|e_i(T_k)\|\right)}{2\|e_i(T_k)\|}
$$

<!-- label: eq:irls-weight -->

然后以 $W_k = \text{diag}(w_i)$ 解加权正规方程得 $T_{k+1}$，再重新计算权重，循环至收敛。三种常用核的权函数：Huber 核 $w_i = \min(1, \delta/|e_i|)$；Cauchy 核 $w_i = 1/(1 + e_i^2/c^2)$；Geman-McClure 核 $w_i = \sigma^2/(\sigma^2 + e_i^2)^2$。

IRLS 的收敛性由 **half-quadratic（HQ）松弛**保证：引入辅助变量 $z_i$，将原问题等价改写为 $\min_{T, z} \sum_i [z_i \|e_i\|^2/2 + \psi(z_i)]$，其中 $\psi(\cdot)$ 为对偶势函数。交替最小化 $z_i$（闭合解：$z_i^* = h(e_i)$）和 $T$（加权 LS）保证单调下降。[第 3.2 节](ref:sec:outlier) 中所有基于加权对应关系的方法（TrICP 的重叠权重、M-ICP 的 Huber 权重）均可统一纳入此框架，IRLS 是它们共同的求解引擎。

从工程上看，IRLS 的好处是改动小，现有的 GN/LM 框架都可以直接接上权重更新；但它的短板也同样明确。权重函数若过硬，真实内点中那些残差偏大的对应会被一起压低；尺度参数若过松，外点又会重新主导法方程。IRLS 只改变每个对应在当前迭代里的权重，不改变初始化、重叠率和几何可观性，因此它不能处理大初值误差、低重叠和退化结构。

### 3.8.4 ADMM 与近端方法

<!-- label: sec:admm -->

IRLS 通过加权解耦了鲁棒性与求解，但当损失函数非光滑时（$\ell_p$ 范数，$p < 1$），权重 $w_i$ 在零处奇异，IRLS 失效。**Sparse ICP** [Bouaziz 等](cite:bouazizSparseIterativeClosest2013) 引入变量分裂，将配准问题表述为：

$$
\min_{R \in SO(3),\, t,\, z_i} \sum_{i=1}^n \|z_i\|_2^p \quad \text{s.t.} \quad Rp_i + t - q_i = z_i, \quad p \in [0, 1]
$$

<!-- label: eq:sparse-icp -->

ADMM 对增广 Lagrangian $\mathcal{L}_\rho = \sum_i \|z_i\|^p + (\rho/2)\|Rp_i + t - q_i - z_i + u_i\|^2$ 交替极小化，分解为三个独立子步骤：

**步骤 1（位姿更新）：** 固定 $z, u$，对 $(R, t)$ 最小化。$\ell_2^2$ 惩罚项使此子问题退化为加权 P2P，可用 SVD 精确求解。

**步骤 2（近端算子）：** 固定 $(R, t)$ 更新 $z_i$，解 $\min_{z_i} \|z_i\|^p + (\rho/2)\|r_i - z_i\|^2$（$r_i = Rp_i + t - q_i + u_i$）。此为 $\ell_p$ **软阈值（soft-thresholding）**问题，对 $p = 1$ 有 $z_i^* = \text{sign}(r_i) \max(|r_i| - 1/\rho, 0)$；对 $p < 1$ 可用广义软阈值迭代近似。

**步骤 3（对偶更新）：** $u_i \leftarrow u_i + Rp_i + t - q_i - z_i$。

ADMM 的核心洞察在于将**刚体几何约束**（步骤 1，SE(3) 流形上的 SVD）与**稀疏诱导范数**（步骤 2，近端算子）完全解耦——IRLS 做不到这一点，因为它假设损失函数可微。一般而言，$p$ 越小目标越“稀疏/非凸”，优化越困难，ADMM 收敛也更慢。

这套“稀疏 + 近端”到底值不值，原文给过一组很典型的数字：在 “owl” 虚拟扫描对齐（原文图 4）里，粗初值的 RMSE 为 $4.0\\times 10^{-1}$；传统 $\\ell_2$（$p=2$）再配一个距离阈值剔除时，$d_{th}=5\\%$ 仍有 $4.1\\times 10^{-1}$，$d_{th}=10\\%$ 可降到 $2.9\\times 10^{-2}$，但 $d_{th}=20\\%$ 又回升到 $7.5\\times 10^{-2}$（$d_{th}$ 按包围盒对角线百分比定义）；换成 $\\ell_1$（$p=1$）后可做到 $1.6\\times 10^{-2}$；再把范数压到 $p=0.4$，RMSE 进一步降到 $4.8\\times 10^{-4}$[Bouaziz 等](cite:bouazizSparseIterativeClosest2013)。这组结果真正说明的是：硬阈值很容易跟着尺度和初值一起飘，而稀疏范数把“删掉谁、保留谁”变成了连续过程，阈值不再是最容易失手的那一刀。

**Efficient Sparse ICP** [Mavridis 等](cite:mavridisEfficientSparseICP2015) 则更偏实现层面。作者把瓶颈拆成两部分：一部分来自 $\ell_p$（尤其 $p\\ll1$）本身的强非凸，另一部分来自最近邻和距离查询的常数开销。对应地，求解也分成两段：先用全局探索把位姿拖到更靠谱的区域，再切回 ADMM 做精配准；实现上则用 OpenVDB 的层次体素做距离查询，配合并行和均匀降采样压低常数项。论文在 Intel i7-3820 @ 3.6 GHz（4 核，最多 8 线程）上给出的时间很具体（原文表 1，单位 s；目标点数约 155k）：VDB 的查询开销 $T_p=1.9$，源点 154k/77k/38k/9k 时总耗时分别为 25.5/9.3/4.1/1.8；ANN 的 $T_p=0.01$，但总耗时为 78.4/22.8/9.1/2.4；kd-tree 也是 $T_p=0.01$，总耗时却高达 890.6/236.8/67.6/8.5[ Mavridis 等](cite:mavridisEfficientSparseICP2015)。同文还报告，在其示例数据上端到端对齐约需 11 s，相对 Sparse ICP 可提速约 31 倍（原文图 7）；内存占用约 30–90 MB，默认使用 $\\ell_{0.4}$ 范数与 VDB 体素边长 3[Mavridis 等](cite:mavridisEfficientSparseICP2015)。

这类方法更适合离线或重精度场景。$p$ 取得越小，目标函数的非凸性越强，罚参数、终止条件和初始化就越敏感；再加上 ADMM 迭代、距离场构建和全局探索都会增加时延，这类方法不能直接承担高频里程计前端。

![近端方法与 IRLS 的求解器对比](../images/ch3-opt-solver-comparison.png)
<!-- caption: （a）IRLS 通过权重函数把“鲁棒损失”转化为一系列加权最小二乘；（b）Sparse ICP 以 ADMM 变量分裂把“刚体几何”与“稀疏/非光滑先验”解耦；（c）当目标从更接近 $\ell_2$ 逐步走向更稀疏的设定时，优化难度上升，混合策略可缓解收敛困难（定性示意）。 -->
<!-- label: fig:opt-solver-comparison -->
<!-- width: 0.95\textwidth -->
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
  Academic diagram (schematic) comparing IRLS and ADMM-based solvers for robust ICP. Three panels.
  White background, clean vector style, all in-figure text Chinese only.

  Panel (a) "IRLS 权重函数":
  - Plot 3 weight curves labeled "Huber / Cauchy / Geman-McClure".
  - x-axis "残差大小", y-axis "权重".
  - No numeric ticks; keep only qualitative shapes (Huber saturates, others downweight outliers more).

  Panel (b) "ADMM 变量分裂（Sparse ICP）":
  - Three boxes in a cycle: "位姿更新（SVD）" -> "近端更新（软阈值）" -> "对偶更新".
  - A header box "增广拉格朗日" pointing to the cycle.
  - Use color to emphasize geometry vs sparsity (blue vs red), no equations inside boxes beyond short symbols.

  Panel (c) "稀疏程度与优化难度（定性）":
  - A grouped bar chart with three groups: "更接近 ℓ2" / "中等稀疏" / "更强稀疏".
  - Two bars per group: "Sparse ICP" and "Efficient Sparse ICP".
  - Heights are qualitative: both increase with sparsity, Efficient variant lower; no numeric axis.
-->

### 3.8.5 $SE(3)$ 流形优化

<!-- label: sec:lie-opt -->

欧拉角参数化的奇异性（万向锁）和四元数的单位约束均会给迭代优化引入额外复杂性。直接在 $SE(3)$ 流形上做优化可完全规避这两个问题 [Sola 等](cite:solaMicroLieTheory2018)。

$SE(3)$ 元素 $T = (R, t)$ 的**左扰动**模型为 $T' = \exp(\hat{\xi}) \cdot T$，其中 $\xi = (\phi, \rho) \in \mathfrak{se}(3)$，旋转分量 $\phi \in \mathbb{R}^3$，平移分量 $\rho \in \mathbb{R}^3$。指数映射由 Rodrigues 公式计算：

$$
\exp(\hat{\phi}) = I + \frac{\sin\|\phi\|}{\|\phi\|}\,\hat{\phi} + \frac{1-\cos\|\phi\|}{\|\phi\|^2}\,\hat{\phi}^2
$$

<!-- label: eq:rodrigues -->

**左 vs 右扰动的工程选择：** 左扰动 $\exp(\hat{\xi}) \cdot T$ 对应世界系中的增量，Jacobian 形式更简洁；右扰动 $T \cdot \exp(\hat{\xi})$ 对应体系中的增量，在 IMU 预积分中更自然。KISS-ICP [Vizzo 等](cite:vizzoKISSICPDefensePointtoPoint2022) 采用右扰动以配合恒速运动模型的运动补偿；LIO-SAM [Shan 等](cite:shanLIOSAMTightlyCoupled2020) 采用左扰动对接 GTSAM 因子图。

KISS-ICP 的“极简”不是口号：它基本就靠 P2P 残差、Lie 群扰动、自适应数据关联阈值和 Cauchy 鲁棒核把前端跑稳 [Vizzo 等](cite:vizzoKISSICPDefensePointtoPoint2022)。具体到参数，关联阈值从 $\tau_0=2\\,\\text{m}$ 起步，再随运动强度自调上界。论文在 KITTI benchmark（使用已做运动补偿的数据）上给出 00–10 序列平均平移误差 0.50%，11–21 为 0.61%（原文表 II）；换到 KITTI-raw，不做 deskewing 时频率约 51 Hz，但误差会上升到 0.91%/0.27；加入 deskewing 后频率约 38 Hz，平移/旋转误差为 0.49%/0.16（常速模型）或 0.51%/0.19（用 IMU）[Vizzo 等](cite:vizzoKISSICPDefensePointtoPoint2022)。这些数字说明，右扰动配合 LM 和鲁棒核，确实能把优化稳定性和系统节拍同时兜住。

但流形优化本身并不会消掉问题的不可观性。若场景只有单平面、长走廊或局部几何过弱，把参数从欧拉角换成 $se(3)$ 只会消除参数化奇异性，不会增加观测约束；遇到大角度错位或错误对应占主导时，流形上的 GN/LM 仍然收敛到错误解。

![$SE(3)$ 流形扰动模型与参数化对比](../images/ch3-lie-group-se3.png)
<!-- caption: （a）$SE(3)$ 流形与切空间示意：$T_0$ 处的切平面 $\mathfrak{se}(3)$ 用六维坐标表示旋转与平移增量；左扰动（世界系增量）与右扰动（体系增量）对应不同的“把增量乘到哪里”。（b）Rodrigues 公式的几何直观：旋转向量的方向决定旋转轴，模长决定旋转幅度，点 $p$ 沿圆弧映射到 $Rp$。（c）旋转参数化对比：欧拉角存在万向锁；四元数需单位约束且存在双覆盖；$\mathfrak{so}(3)$ 向量更新自然但需注意大角度时的映射性质。 -->
<!-- label: fig:lie-group-se3 -->
<!-- width: 0.95\textwidth -->
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
  Three-panel academic diagram (schematic) about SE(3) Lie group optimization for ICP.
  White background, clean vector style, all in-figure text Chinese only.

  Panel (a) "流形与扰动":
  - Draw a curved gray surface as "SE(3) 流形" with a point labeled "T0".
  - Draw a beige tangent plane labeled "se(3) 切空间" with two groups of axes labeled "旋转增量" and "平移增量" (no subscripts).
  - Show a blue arrow labeled "左扰动" and an orange arrow labeled "右扰动" reaching a nearby point "T1".

  Panel (b) "Rodrigues 直观":
  - Show a rotation axis (red arrow) and a point p moving along an arc to Rp.
  - Label the arc "旋转幅度" and add a small text "Rodrigues 公式" (no explicit numeric angles).

  Panel (c) "参数化对比":
  - Three columns labeled "欧拉角 / 四元数 / so(3) 向量".
  - For Euler: show a simple gimbal-like icon with a red cross labeled "万向锁风险".
  - For Quaternion: show a unit sphere icon with a double-arrow labeled "双覆盖" and a small note "需单位约束".
  - For so(3): show a tangent vector icon with a green check labeled "更新自然" and a small note "大角度需注意映射".
-->

### 3.8.6 可认证与全局最优方法

<!-- label: sec:certifiable -->

当初始位姿误差较大或外点比例极高时，GN/LM 和 IRLS 均可能收敛到局部极小。可认证方法（certifiable methods）通过松弛或连续化策略在理论上保证全局最优性。

**GNC（Graduated Non-Convexity）** [Yang 等](cite:yangGraduatedNonConvexityRobust2020) 从 Black-Rangarajan 对偶性出发，将鲁棒估计转化为带权重的 LS 序列。其核心是构造一族代理损失 $\rho_\mu(\cdot)$（参数 $\mu$ 控制非凸程度），$\mu$ 较大时 $\rho_\mu$ 近似为凸函数，随 $\mu$ 逐渐减小趋近目标鲁棒函数。每个 $\mu$ 值下的权重可用闭合公式计算（TLS 核情形可写为 $w_i = \max(0, 1 - (r_i/\mu)^2)^2$）。

这套“从易到难”的连续化过程到底能扛多少外点，原文给过一组很清楚的小实验：以 Stanford Bunny 为例，模型先缩放到单位立方体，再从对应集中采样 $N=100$ 个点对，内点叠加高斯噪声 $\\sigma=0.01$，外点比例从 60% 一直扫到 95%[Yang 等](cite:yangGraduatedNonConvexityRobust2020)。在该文的位姿图实验里，外点比例到 80% 时，RANSAC 约需 218 ms，而 GNC-GM 和 GNC-TLS 分别约为 22 ms 和 23 ms。这里更值得注意的不是“谁更快”，而是 GNC 把鲁棒估计改写成一串连续加权问题以后，原来大量靠随机试错消耗的时间被省掉了 [Yang 等](cite:yangGraduatedNonConvexityRobust2020)。

GNC 仍然要处理路径调度问题。$\mu$ 降得过快，优化会在还没进入正确盆地时就面对强非凸目标；$\mu$ 降得过慢，迭代次数和调参成本都会显著增加。它本质上仍是局部优化，只是把原来的单个非凸问题拆成一串更容易求的子问题。

**TEASER++** [Yang 等](cite:yangTEASERFastCertifiable2021) 以截断最小二乘（TLS）代价 $\min \sum_i \min(\|e_i\|^2, \bar{c}^2)$ 为起点，通过**图论解耦**把配准拆成三个级联子问题：尺度估计（投票）→ 平移估计（投票）→ 旋转估计（松弛 + 检验）。对应层面先做最大团剪枝，把明显不一致的外点从候选集合里删掉；旋转部分用 GNC 求解，并用 Douglas–Rachford splitting（DRS）做后验检验：检验通过时，解的最优性可以直接被验证。论文在标准基准与 3DMatch 扫描匹配上评测，并给出两条“很硬”的结论：尺度已知时对外点比例可鲁棒到 >99%，且 TEASER++ 的单次求解可在毫秒级完成[Yang 等](cite:yangTEASERFastCertifiable2021)。

TEASER++ 最突出的地方是它对极端外点的承受能力。原文给出的结果是：尺度已知时，外点比例超过 $99\\%$ 仍可恢复；尺度未知时，外点比例到 $90\\%$ 也还有成功案例 [Yang 等](cite:yangTEASERFastCertifiable2021)。在作者的实现里，单次求解可做到 $<10\\,\\text{ms}$。但它要求输入对应中仍保留一组几何上自洽的内点；如果对应已经被重复结构或描述子失配完全打散，最大团剪枝和后续旋转估计都不会成功。因此，TEASER++ 适合做困难帧初始化、回环精配准或离线配准，不适合替代每一帧的常规前端。

**SE-Sync** [Rosen 等](cite:rosenSESyncCertifiablyCorrect2019) 面向的是位姿图 SLAM 里的旋转同步问题。它把 MLE 写成半定松弛（SDP），再用流形上的截断 Newton 信赖域去解，并给出“什么时候松弛是紧的”这类可认证条件。论文里最有说服力的是那张运行时间表（原文表 1）：在 sphere（2500 poses / 4949 measurements）上，Gauss-Newton 为 14.98 s，SE-Sync 为 2.81 s；torus（5000/9048）为 31.94 s vs 5.67 s；grid（8000/22236）为 130.35 s vs 22.37 s；rim（10195/29743）为 575.42 s vs 36.66 s，总体加速大致在 3.3 倍到 15.7 倍之间 [Rosen 等](cite:rosenSESyncCertifiablyCorrect2019)。这些结果说明，可认证松弛并不一定天然比传统迭代慢。

但 SE-Sync 的适用边界也很明确：它针对的是整个位姿图层面的同步问题，不是单帧点到点配准前端。它需要的是多帧之间的相对位姿约束图，而不是一对点云的对应集合，因此不能直接替代单帧 ICP 求解器。

三类方法的核心差异在于：GNC 是把非凸目标沿一条连续路径慢慢引入；TEASER++ 是把尺度、平移、旋转拆开以后分别求，并在旋转部分附上松弛检验；SE-Sync 则直接在图层面做整体松弛。Go-ICP（见[第 3.6 节](ref:sec:global-init)）的分支定界在外点受控时也能做到全局最优，但外点一多复杂度就会迅速失控；相比之下，TEASER++ 更强调的是“对应很脏时还能给出一个可验证的解”。

![可认证方法比较](../images/ch3-certifiable-methods.png)
<!-- caption: （a）GNC 连续化路径示意：代理损失从更“凸/平滑”逐步演变为目标鲁棒损失，权重更新与加权 LS 交替进行；（b）TEASER++ 级联求解与松弛检验流程示意：对应剪枝 → 解耦投票 → 旋转松弛 → 松弛检验；（c）从“鲁棒性”到“计算代价”的二维视角比较：GNC、TEASER++、SE-Sync 在不同问题难度下的适用区间（定性示意）。 -->
<!-- label: fig:certifiable-methods -->
<!-- width: 0.95\textwidth -->
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
  Academic comparison diagram (schematic) of certifiable registration methods. Three panels.
  White background, clean vector style, all in-figure text Chinese only.

  Panel (a) "GNC 连续化":
  - Plot three surrogate loss curves labeled "μ 大 / μ 中 / μ 小" (no numbers).
  - x-axis "残差", y-axis "损失".
  - Add a small inset of corresponding weight curves labeled "权重".
  - Qualitative labels: "更接近凸" on the left curve and "更非凸/更鲁棒" on the right curve.

  Panel (b) "TEASER++ 流程":
  - Flowchart: "对应关系" -> "最大团剪枝" -> two boxes "尺度/平移投票" and "旋转松弛" -> "松弛检验" -> "输出变换".
  - Use color to group: decoupled (blue), relaxation (orange), certificate (green). No performance claims.

  Panel (c) "适用区间（定性）":
  - 2D scatter-like diagram with x-axis "鲁棒性需求（低→高）", y-axis "计算代价（低→高）".
  - Place labeled markers "GNC", "TEASER++", "SE-Sync", "Go-ICP" in plausible regions (qualitative only).
-->

### 3.8.7 因子图与 SLAM 集成

<!-- label: sec:factor-graph -->

ICP 位姿估计的误差不均匀，走廊场景的轴向漂移（见[第 3.5 节](ref:sec:degeneracy)）和回环时的累计误差都会要求将单帧 ICP 结果纳入全局一致优化。因子图（factor graph）将 ICP 残差建模为两帧位姿之间的**二元约束因子**，与 IMU 预积分因子、回环检测因子并列优化。

全局位姿估计问题可表述为非线性最小二乘：

$$
x^* = \arg\min_{x} \sum_{(i,j) \in \mathcal{E}} e_{ij}(x_i, x_j)^\top \Omega_{ij}\, e_{ij}(x_i, x_j)
$$

<!-- label: eq:factor-graph -->

其中 $e_{ij} = \log(T_{ij}^{-1} \cdot T_i^{-1} T_j)$（相对位姿残差），$\Omega_{ij}$ 为信息矩阵。ICP 给出的 $\Omega_{ij} = J^\top \Sigma^{-1} J$（Hessian）与[第 3.5 节](ref:sec:degeneracy)中的 Hessian 秩分析直接对应：当配准在退化方向缺乏约束时，$\Omega_{ij}$ 在对应行列接近零，[Hinduja 等](cite:hindujaDegeneracyAwareFactorsApplications2019)在该节讨论的退化感知因子正是在此基础上只提交约束充分的方向的因子边。

**g2o** [Kümmerle 等](cite:kummerleG2oGeneralFramework2011) 是通用图优化框架，它把位姿图的稀疏雅可比直接落到稀疏线性系统上，支持 GN、LM 和 Dogleg 等求解器。论文里有一张很能说明问题的表（原文表 II）：在单核 i7-930 @ 2.8 GHz 上，Venice BA 的每次迭代若用 CHOLMOD 约为 1.86 s，CSparse 约 39.1 s，而 PCG 为 $0.287\\pm0.135$ s；New College 上，CHOLMOD 约 6.19 s，CSparse 约 200.6 s，PCG 为 $0.778\\pm0.201$ s[Kümmerle 等](cite:kummerleG2oGeneralFramework2011)。这些数字说明，后端图优化的瓶颈经常落在线性求解器上，而不是 GN、LM 或 Dogleg 这些外层迭代形式上。

因此，因子图优化的短板主要在图质量和数值实现。前端若持续送入带偏因子、回环约束若包含假阳性，或者线性化点长期偏离真实轨迹，后端优化会把这份误差继续传播到整张图上。

**GTSAM + iSAM2** [Dellaert 等](cite:dellaertFactorGraphsRobot2017)，[Kaess 等](cite:kaessISAM2IncrementalSmoothing2012) 引入 Bayes 树数据结构，将增量式重线性化限制在受影响的子树节点上。iSAM2 的表格同样很直白：例如 Manhattan（3500 poses）每步平均约 2.44 ms，总计 8.54 s；City20000（20000 poses）每步平均约 16.1 ms，但最坏一步可到 1125 ms（原文表 1）[Kaess 等](cite:kaessISAM2IncrementalSmoothing2012)。这说明 iSAM2 的平均时延很低，但遇到大规模重线性化时，单步延迟会出现尖峰。

**LIO-SAM** [Shan 等](cite:shanLIOSAMTightlyCoupled2020) 以 iSAM2 为后端，同时注册三类因子：LiDAR 里程计因子（本节 ICP 结果，$6\\times6$ 信息矩阵）、IMU 预积分因子（15 维状态）、GPS 因子（选配）与回环因子（ICP 精配准结果）。作者把信息矩阵“怎么来”说得很直接：LiDAR 因子用 P2Pl ICP 的 Hessian $H$ 直接构造信息矩阵，退化场景下（如走廊）$H$ 秩亏，对应方向权重自动变弱。

这套链路在论文的结果里也能直接看出来：在 i7-10710U 笔记本上（CPU-only），LIO-SAM 在 Campus、Park、Amsterdam 等序列上的平均耗时约为 97.8、100.5 和 79.3 ms per scan（原文表 IV）；终端轨迹误差的差距更明显，例如 Campus 上 LOAM 为 192.43 m，而 LIO-SAM 为 0.12 m，Park 上 LOAM 为 121.74 m，而 LIO-SAM 只有 0.04 m（原文表 II）[Shan 等](cite:shanLIOSAMTightlyCoupled2020)。这些数字放到求解器视角里，其实是在说明一个更结构性的事实：前端每帧的 ICP 不是孤立的局部最小二乘，它的 Hessian 会继续传到后端，成为因子图中那条边的权重和置信度。

但这种“前后端一体”的风险也很直接。前端若长期在退化场景里输出带偏 Hessian，后端会把这份偏置当作可信信息继续累计；若回环检测再引入错误约束，整张图都会被一起拉偏。

![因子图结构与 LIO-SAM 架构](../images/ch3-factor-graph-liosam.png)
<!-- caption: （a）LiDAR SLAM 因子图结构：圆形节点为位姿变量 $x_i$；蓝色实线为 LiDAR 里程计因子（由 ICP Hessian/信息矩阵给权），橙色虚线为 IMU 预积分因子，绿色粗线为回环因子；退化帧的 ICP 因子以“部分约束”形式提交（对应[第 3.5 节](ref:sec:degeneracy)）。（b）信息矩阵热力图对比：正常场景约束更完整；退化场景在某些自由度方向上约束显著变弱。（c）iSAM2 Bayes 树增量更新示意：新因子到来时只重线性化受影响的子树节点，避免反复全量批优化。 -->
<!-- label: fig:factor-graph-liosam -->
<!-- width: 0.95\textwidth -->
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
  Three-panel academic diagram (schematic) of factor graphs for LiDAR SLAM.
  White background, clean vector style, all in-figure text Chinese only.

  Panel (a) "因子图":
  - Pose nodes x1..x6 as circles in a row.
  - Blue solid edges between consecutive nodes labeled "激光里程计因子".
  - Orange dashed edges above labeled "IMU 因子".
  - A thick green edge between two distant nodes labeled "回环因子".
  - One corridor edge is drawn as a red "半边" factor labeled "部分约束（退化）".

  Panel (b) "信息矩阵热力图":
  - Two small heatmaps side-by-side labeled "正常" and "退化".
  - The "退化" one has one row/column much lighter to indicate weak constraint direction.
  - Axes labeled "自由度" (no numeric ticks).

  Panel (c) "增量更新":
  - A Bayes tree diagram where only a subtree is highlighted in orange labeled "重线性化".
  - The rest stays blue labeled "保持不变".
-->

### 3.8.8 综合对比

<!-- label: sec:opt-compare -->

<!-- begin: raw -->
\begin{table}[htbp]
\centering
\caption{ICP 优化求解器综合对比}
\label{tab:opt-solver-compare}
\begin{tabular}{llllll}
\hline
\textbf{方法} & \textbf{类别} & \textbf{收敛域} & \textbf{全局最优} & \textbf{外点鲁棒} & \textbf{SLAM 就绪} \\
\hline
Gauss-Newton & 一阶 NLS & 局部（强依赖初值） & 否 & 弱（需配鲁棒核） & 是（g2o/GTSAM） \\
Levenberg-Marquardt & 信赖域 NLS & 局部（更稳） & 否 & 弱（需配鲁棒核） & 是 \\
IRLS & 加权 LS 序列 & 局部（依赖权重） & 否 & 中（核/权重决定） & 是 \\
Sparse ICP (ADMM) & 近端/变量分裂 & 局部 & 否 & 强（非光滑/稀疏先验） & 否（通常为离线模块） \\
Efficient Sparse ICP & 全局探索 + ADMM & 更宽（经验上） & 否 & 强（依赖设定） & 否 \\
GNC & 连续松弛 & 宽（经验上） & 近似/可认证（视问题） & 强（鲁棒核驱动） & 可用（位姿图/因子图） \\
TEASER++ & TLS + SDP + 图论 & 宽（初值弱依赖） & 可证明（可检验） & 强（对外点更友好） & 有限（离线/触发式） \\
SE-Sync & 流形 SDP & 全局（旋转同步） & 可证明（可检验） & 噪声受控场景更稳 & 位姿图专用 \\
\hline
\end{tabular}
\end{table}
<!-- end: raw -->

求解器的选择由场景需求主导：实时系统（自动驾驶、UAV SLAM）通常以 GN/LM + Lie 群扰动为主循环，IRLS 或 GNC 提供在线外点鲁棒性，iSAM2 因子图支撑全局一致性；离线精配准或初始位姿完全未知时，TEASER++ 或 GNC 的全局搜索能力不可或缺。Sparse ICP 的 ADMM 框架在形状建模和曲面重建领域独树一帜，其近端分裂思路正向连续优化（Proximal Gradient Descent）和深度展开（Algorithm Unrolling）扩展。
