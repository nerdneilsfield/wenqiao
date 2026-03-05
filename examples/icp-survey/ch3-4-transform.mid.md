## 3.4 变换估计方法 (Transformation Estimation)
<!-- label: sec:transform -->

ICP 两步交替框架的第二步是：给定固定的对应集 $\{(p_i,q_{j(i)})\}_{i=1}^n$，求解最优刚体变换 $(R^*,t^*)$ 使加权距离平方和最小。这一子问题本身数学上是闭式可解的（封闭形式解），但不同参数化方案（旋转矩阵 SVD、单位四元数、李代数 $se(3)$、对偶四元数）在数值稳定性、与更新规则的兼容性和不确定性传播能力上有显著差异。本节系统梳理五类方法，以及从统计学角度统一它们的概率框架。

![ICP 变换估计方法的参数化空间对比](../images/ch3-transform-parameterization.png)
<!-- caption: 三种旋转参数化方案的几何示意。左：SVD 闭式解将交叉协方差矩阵 $H$ 分解为 $H = U\Sigma V^\top$，最优旋转 $R^* = VU^\top$，行列式检查确保真旋转。中：单位四元数将旋转编码为三维单位超球面 $S^3$ 上的点，球面测地距离对应旋转角，SLERP 在球面大圆弧上插值。右：对偶四元数 $\hat{q} = q_r + \varepsilon q_d$ 将旋转（实部）与平移（对偶部）统一为单个代数结构，表示螺旋运动。 -->
<!-- label: fig:transform-parameterization -->
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
  Three-panel academic diagram comparing rotation parameterization methods for ICP.
  Left panel "SVD 闭式解 (SVD)":
    Show 3x3 matrix H being decomposed: H -> U*Sigma*V^T via SVD arrow.
    Then R* = V*U^T shown below with det(R*) = +1 check (green checkmark for +1, red X for -1).
    Small annotation: "cross-covariance matrix", "3x3 SVD".
    Background: light blue tint.
  Middle panel "单位四元数 (Quaternion)":
    Show a 3D unit sphere (S^3 projected to 2D circle). Point q=(q0,u) on surface.
    Rotation axis n shown as arrow through center, angle theta labeled.
    Formula: q = (cos(θ/2), sin(θ/2)n) shown.
    SLERP path shown as arc on sphere surface.
    Background: light orange tint.
  Right panel "对偶四元数 (Dual Quaternion)":
    Show 3D helix representing screw motion - rotation + translation combined.
    Formula: q_hat = q_r + epsilon*q_d shown.
    Note: epsilon^2 = 0.
    Background: light green tint.
  Clean academic style, white background between panels, consistent font size, publication quality.
-->

### 3.4.1 问题形式化

ICP 变换估计步的标准形式为：给定 $n$ 个加权对应点对 $\{(p_i, q_i, \omega_i)\}$，求解

$$
(R^*, t^*) = \arg\min_{R \in SO(3),\, t \in \mathbb{R}^3} \sum_{i=1}^{n} \omega_i \|Rp_i + t - q_i\|_2^2
$$
<!-- label: eq:transform-objective -->

其中 $\omega_i \geq 0$ 为第 $i$ 个对应点对的权重（在鲁棒 ICP 中由 M-估计器动态确定，在 P2P ICP 中均为 1）。注意到目标函数关于 $t$ 是强凸的——固定 $R$ 时最优平移为 $t^* = \bar{q} - R\bar{p}$，其中 $\bar{p} = \frac{\sum \omega_i p_i}{\sum \omega_i}$，$\bar{q} = \frac{\sum \omega_i q_i}{\sum \omega_i}$ 为加权质心。去均值后问题化简为纯旋转估计，是各方法的核心区别所在。

### 3.4.2 SVD 闭式解（Kabsch 算法）

去均值后构造加权交叉协方差矩阵：

$$
H = \sum_{i=1}^{n} \omega_i (p_i - \bar{p})(q_i - \bar{q})^\top \in \mathbb{R}^{3\times 3}
$$
<!-- label: eq:cross-covariance -->

对 $H$ 做奇异值分解 $H = U\Sigma V^\top$，最优旋转与平移为

$$
R^* = V U^\top, \qquad t^* = \bar{q} - R^* \bar{p}
$$
<!-- label: eq:kabsch -->

**奇异性处理**：当 $\det(VU^\top) = -1$ 时，SVD 给出的是反射（reflection）而非旋转，需将 $V$ 的最后一列取反：

$$
R^* = V \begin{pmatrix} 1 & 0 & 0 \\ 0 & 1 & 0 \\ 0 & 0 & \det(VU^\top) \end{pmatrix} U^\top
$$
<!-- label: eq:kabsch-correction -->

[Arun et al.](cite:arunLeastSquaresFittingTwo1987) 于 1987 年给出了完整的 SVD 推导和奇异性处理，证明了该解法在 $L_2$ 意义下的全局最优性，以及当 $H$ 的最小奇异值为零（点集严格共面）时退化的处理方法。SVD 更新的一个重要工程优势是：位姿求解本身计算代价很低、数值稳定性好，因而在多数实现中并非瓶颈；ICP 的主要耗时通常来自近邻查询与残差/雅可比的批量评估。

这件事在他们给出的计时对比里也很直观：[Arun et al.](cite:arunLeastSquaresFittingTwo1987) 在 VAX 11/780 上，对比了 SVD 法、四元数法与迭代法的端到端计算时间（包含构造 $H$、分解与求解）。以点对数 $N=7/11/16/20/30$ 为例，SVD 法约为 37.0/40.0/39.2/40.4/44.2 ms，四元数法约为 26.6/32.8/39.9/45.2/48.3 ms；迭代法则约为 94.2/110.8/120.5/135.0/111.0 ms，对应迭代次数分别为 5/7/10/6/6 次（论文表格直接报数）[Arun et al.](cite:arunLeastSquaresFittingTwo1987)。因此，对“固定对应、解一次最小二乘”这一步来说，真正值得优化的通常不是 3×3 SVD 或 4×4 特征分解，而是更前面的对应建立与更后面的鲁棒权重更新。

SVD 法的局限也正好来自它的“纯净”：它默认输入的对应已经足够可靠、权重也已经合理。一旦对应集里混入大量外点，或者几何本身明显退化，闭式解会很干脆地给出一个同样“闭式”的错误答案。换句话说，它解的是一个干净的刚体最小二乘子问题，并不负责替你判断这个子问题是否建对了。

![Kabsch SVD 算法完整步骤图解](../images/ch3-kabsch-svd-steps.png)
<!-- caption: Kabsch（SVD）闭式解的五步骤图解（示意）：去均值 → 构造交叉协方差 $H$ → SVD 分解 → 行列式检查（防反射）→ 得到 $R^*,t^*$ 并将源点对齐到目标点。 -->
<!-- label: fig:kabsch-svd-steps -->
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
  Five-step academic diagram (schematic) explaining the Kabsch SVD algorithm for rigid registration.
  White background, clean vector style, all in-figure text Chinese only.
  Use a small 2D toy example (few point pairs) but keep formulas in standard symbols.

  Step 1 "去均值":
  - Show source points (red) and target points (blue) with their centroids p_bar and q_bar.
  - Show dashed translation arrows to centered points p' and q'.
  - Display a short formula line: "p'_i = p_i - p_bar,  q'_i = q_i - q_bar".

  Step 2 "构造 H":
  - Show a 3×3 matrix heatmap labeled "H" with symbolic entries (no concrete numbers).
  - Display formula: "H = Σ ω_i p'_i q'_i^T".

  Step 3 "SVD 分解":
  - Show "H = U Σ V^T" as three blocks; Σ is diagonal with symbolic σ1≥σ2≥σ3 (no numeric values).

  Step 4 "行列式检查":
  - Branch diagram: det(VU^T)=+1 -> "真旋转" and det(VU^T)=-1 -> "反射（需修正）".
  - Show corrected form schematically: flip last column of V, then compute R*.

  Step 5 "对齐结果":
  - Before/after scatter: before misaligned, after aligned; short residual arrows.
  - Annotation: "残差显著减小" and "t* = q_bar - R* p_bar".
-->

**Horn 同年的等价结果**：[Horn](cite:hornClosedformSolutionAbsolute1987) 基于四元数方法独立得出等价结论，其推导路径不同但最终给出的旋转矩阵与 Arun 的 SVD 方法完全一致。两种方法的等价性说明 SVD 和四元数特征分解在数学上描述的是同一个问题结构。

### 3.4.3 单位四元数法

[Horn](cite:hornClosedformSolutionAbsolute1987) 将旋转 $R$ 参数化为单位四元数 $\mathbf{q}=(q_0, q_1, q_2, q_3)^\top$，$\|\mathbf{q}\|=1$，构造对称 $4\times 4$ 矩阵 $N$（由交叉协方差矩阵 $H$ 的元素组成）：

$$
N = \begin{pmatrix}
H_{xx}+H_{yy}+H_{zz} & H_{yz}-H_{zy} & H_{zx}-H_{xz} & H_{xy}-H_{yx} \\
H_{yz}-H_{zy} & H_{xx}-H_{yy}-H_{zz} & H_{xy}+H_{yx} & H_{zx}+H_{xz} \\
H_{zx}-H_{xz} & H_{xy}+H_{yx} & -H_{xx}+H_{yy}-H_{zz} & H_{yz}+H_{zy} \\
H_{xy}-H_{yx} & H_{zx}+H_{xz} & H_{yz}+H_{zy} & -H_{xx}-H_{yy}+H_{zz}
\end{pmatrix}
$$
<!-- label: eq:horn-matrix -->

最优旋转四元数 $\mathbf{q}^*$ 是 $N$ 的**最大特征值**对应的特征向量。四元数表示的核心优势：

1. **无奇异性**：欧拉角存在万向锁（gimbal lock），四元数无此问题。
2. **插值友好**：SLERP（Spherical Linear Interpolation）在单位球面 $S^3$ 上做测地线插值，保持旋转的连续性，适合位姿滤波（卡尔曼滤波、粒子滤波）。
3. **计算量相当**：$4\times 4$ 特征分解比 $3\times 3$ SVD 略重，实践中差异可忽略。

从“什么条件下能解”这一点看，四元数法与 SVD 法并无本质差别：都需要至少 3 对不共线的对应点才能约束出完整的三维旋转；一旦点集退化为严格共线/共面，$H$ 的秩会下降，旋转的某些自由度就会变得不可观，[Horn](cite:hornClosedformSolutionAbsolute1987) 与 [Arun et al.](cite:arunLeastSquaresFittingTwo1987) 都在推导里专门讨论了这类退化情形。

**与 SVD 等价性的深层含义**：两种方法的“分解部分”确实是固定大小矩阵（3×3 SVD 或 4×4 特征分解），代价基本可视为常数；但不要把它误读成“与点数无关”。构造质心与交叉协方差 $H$ 仍是 $O(n)$ 的线性遍历，只是这一步的常数非常小，通常远小于一次 KD-tree 最近邻查询的开销。在多数工程实现里，变换估计步很少是瓶颈，瓶颈更常出现在对应搜索、法向/协方差估计或鲁棒核的权重更新上。

四元数法的局限并不在“算得慢”，而在它解决的问题和 SVD 一样，仍然只是固定对应下的闭式刚体估计。换成四元数，并不会自动提升对坏对应或退化结构的鲁棒性；它主要赢在表示层面更适合插值、滤波与连续旋转处理。

### 3.4.4 李代数参数化与 $SE(3)$ 直接优化

在 FRICP [Zhang et al.](cite:zhangFastRobustIterative2022) 和许多现代 SLAM 框架中，旋转以李代数 $se(3)$ 参数化代替旋转矩阵，主要优势是在 Anderson 加速和梯度下降中可以进行"加法更新"：

$$
\boldsymbol{\xi} = (\boldsymbol{\omega}, \boldsymbol{v}) \in \mathbb{R}^6, \quad T = \exp(\hat{\boldsymbol{\xi}}) \in SE(3)
$$
<!-- label: eq:lie-algebra -->

其中 $\hat{\boldsymbol{\xi}}$ 为 $se(3)$ 矩阵，$\exp$ 为矩阵指数（可通过 Rodrigues 公式解析计算）。李代数参数化使得迭代更新为

$$
\boldsymbol{\xi}^{(k+1)} = \boldsymbol{\xi}^{(k)} + \Delta\boldsymbol{\xi}, \quad T^{(k+1)} = \exp(\hat{\Delta\boldsymbol{\xi}}) \cdot T^{(k)}
$$
<!-- label: eq:lie-update -->

这一线性化更新与 Anderson 加速天然兼容（可以在 $\mathbb{R}^6$ 空间直接做线性组合），而旋转矩阵本身不在线性空间中，直接做 $R_1 + R_2$ 会破坏正交性约束。FRICP 正是通过将 Anderson 加速应用于 $se(3)$ 参数化的 $\boldsymbol{\xi}$，避免了原始 AA-ICP 在欧拉角参数化下的万向锁奇异性 [Zhang et al.](cite:zhangFastRobustIterative2022)。更关键的是，这并不是“好看”的数学表达：他们在实验设置里把 ICP / ICP-l / AA-ICP 的终止条件统一为“最多 1000 次迭代，或两次迭代的变换差满足 $\|\Delta T\|_F<10^{-5}$”，从而能直接比较不同更新规则在同一停止口径下的收敛表现[Zhang et al.](cite:zhangFastRobustIterative2022)。

但李代数参数化也不是“用了就更稳”。它解决的是表示和更新规则的兼容性问题，不是观测可观性问题；如果 Hessian 本身病态，换成 $se(3)$ 只是让你更方便地写出更新，不会凭空补回缺失约束。大角度初值下，指数映射与局部线性化的有效范围也仍然要靠更好的初值或多分辨率策略来兜住。

### 3.4.5 对偶四元数法与 Sim(3) 扩展

对偶四元数（Dual Quaternion）以 $\hat{\mathbf{q}} = \mathbf{q}_r + \varepsilon \mathbf{q}_d$（$\varepsilon^2=0$）将旋转四元数 $\mathbf{q}_r$ 和平移四元数 $\mathbf{q}_d$ 合并。其代数运算：

$$
\hat{\mathbf{q}}_1 \otimes \hat{\mathbf{q}}_2 = \mathbf{q}_{r1}\mathbf{q}_{r2} + \varepsilon\!\left(\mathbf{q}_{r1}\mathbf{q}_{d2} + \mathbf{q}_{d1}\mathbf{q}_{r2}\right)
$$
<!-- label: eq:dual-quaternion -->

天然处理旋转与平移的耦合，表示"螺旋运动"（screw motion）——绕轴旋转同时沿轴平移，是 $SE(3)$ 的 Plücker 坐标表示。

[Xia et al.](cite:xiaScalingIterativeClosest2017) 将对偶四元数框架扩展以引入各向同性缩放因子 $s$，将变换群从 $SE(3)$ 扩展到相似变换群 $\text{Sim}(3)$。从参数维度上看，$SE(3)$ 是 6 自由度，而 $\text{Sim}(3)$ 变为 7 自由度（多了 1 个尺度）；从实现上看，对偶四元数用 8 维向量表示（实部四元数 4 维 + 对偶部 4 维），再配上单位范数等约束把自由度压回到“刚体/相似变换”该有的维数。这类表示在“尺度误差不可忽略”的场景里很有用：例如跨传感器标定、不同扫描分辨率的点云拼接、或三维重建存在尺度漂移时，刚体模型会把尺度误差硬塞到平移与旋转里，误差会以系统性偏置的形式扩散到整条轨迹。

在实验数据层面，[Xia et al.](cite:xiaScalingIterativeClosest2017) 明确提到在模拟 3D 曲线与真实点云上验证，并点名使用 Princeton Shape Benchmark 与 Stanford 3D Scanning Repository（Bunny）作为真实点云来源；这些数据集选择的含义也很直接：前者提供了尺度变化更容易“做坏”的形状族，后者则是点云配准最常见的公开基准之一（便于横向对比与复现实验链路）[Xia et al.](cite:xiaScalingIterativeClosest2017)。具体地，目标函数扩展为：

$$
(R^*, s^*, t^*) = \arg\min_{R,s,t} \sum_{i} \omega_i \|sRp_i + t - q_i\|^2
$$
<!-- label: eq:sim3-obj -->

其中尺度 $s > 0$ 的最优解有闭式表达式 $s^* = \frac{\text{tr}(\Sigma_W R^{*\top})}{\text{tr}(W\Sigma_p)}$，可与 SVD 一步联立求解。$\text{Sim}(3)$ 配准适用于跨传感器标定、多视角点云拼接（不同扫描头分辨率差异）和稀疏-稠密激光雷达融合场景，是医学影像配准（CT 与 MRI 分辨率差异）的标准工具。

它的局限是把问题从 6 自由度抬到 7 自由度之后，尺度会和旋转、平移产生更强耦合。若真实场景其实没有明显尺度误差，或者对应本身就不稳，额外引入尺度自由度反而可能把噪声吸收到 $s$ 里，造成看似拟合更好、实则物理解释更差的结果。因此 Sim(3) 更适合确实存在尺度漂移或跨模态比例差异的场景，而不是刚体配准的默认替代品。

### 3.4.6 广义 ICP：概率框架的统一

广义 ICP（Generalized ICP，GICP）[Segal et al.](cite:segalGeneralizedICP2009) 为每个点分配由局部邻域协方差矩阵确定的不确定性 $\Sigma_p^i, \Sigma_q^j$，将 P2P 目标改写为马氏距离形式：

$$
\mathcal{E}_\text{GICP} = \sum_i \mathbf{d}_i^\top \left(R\Sigma_p^i R^\top + \Sigma_q^{j(i)}\right)^{-1} \mathbf{d}_i, \quad \mathbf{d}_i = Rp_i + t - q_{j(i)}
$$
<!-- label: eq:gicp -->

协方差矩阵 $\Sigma_p^i$ 通过点 $p_i$ 的 $k$ 个近邻点估计得到，其特征值结构反映局部几何：平面区域 $\Sigma$ 的最小特征值接近零（法向方向不确定性小），边缘区域 $\Sigma$ 接近均匀（各向同性）。在 [Segal et al.](cite:segalGeneralizedICP2009) 的实现细节里，邻域规模给得很具体：用每个点的 20 个最近邻来做经验协方差的特征分解；而在对比设置中，标准 ICP 的迭代上限设为 250，而点到面与 GICP 设为 50 次迭代。真实数据部分还给出车载 Velodyne 的配对示例，描述为两帧扫描约 30 m 间隔、量测范围约 70–100 m 的室外场景[Segal et al.](cite:segalGeneralizedICP2009)。这些数字很“朴素”，但它们说明两点：GICP 不是靠更复杂的后端求解器取胜，而是靠“每个点的局部几何”把权重分布改得更像真实噪声；代价则是你必须支付邻域统计与矩阵分解的那部分常数开销。

**三种对应度量的统一**：当 $\Sigma_p^i = \Sigma_q^i = I$ 时，GICP 退化为 P2P ICP；当 $\Sigma_p^i = 0$，$\Sigma_q^j$ 为切平面投影矩阵（沿法向的单位矩阵，切向为零）时，退化为 P2Pl ICP；GICP 的完整协方差矩阵形式则在两者之间做自适应加权，由局部曲率自动决定 [Segal et al.](cite:segalGeneralizedICP2009)。这一统一视角明确了 P2P 和 P2Pl 在统计学意义上的关系：P2Pl 假设目标点云是理想平面，P2P 假设各向同性噪声，而 GICP 使用真实的各向异性噪声估计，因此精度更高。

**GICP 的最优化**：内层最优化（固定对应，求 $(R,t)$）可用 Gauss-Newton 或 LM 法在 $se(3)$ 上迭代求解，因为协方差权重使该问题不再有 Kabsch 那样的线性闭式解。由于需要估计协方差并求解加权非线性问题，单次迭代代价往往高于 P2P；但在几何与噪声更符合其假设时也可能以更少迭代达到稳定解，因此总耗时与收敛质量依赖实现细节与场景分布。

GICP 的局限也恰恰埋在它最强的地方：局部协方差如果估得不准，统计模型就会把错误的几何假设一并放大。稀疏点云、邻域选择不合适、法向/曲率本身噪声很大时，协方差椭球未必比简单的 P2P/P2Pl 更可信；这时你付出了更高的建模和求解成本，却未必得到更稳的结果。

![GICP 各向异性协方差几何示意](../images/ch3-gicp-covariance-geometry.png)
<!-- caption: GICP 中三种距离度量的几何解释对比（示意）。左（P2P）：各向同性噪声假设对应球形误差，对曲面处的切向偏移更敏感。中（P2Pl）：切平面投影对应“法向强约束、切向更松”。右（GICP）：用局部协方差自适应权重，不同几何处（平面/边缘/角点）的误差椭球形状不同，从而在统计意义上折中 P2P 与 P2Pl。底部用定性条形对比强调：三者在误差与鲁棒性上的取舍随场景而变。 -->
<!-- label: fig:gicp-covariance -->
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
  Three-column academic diagram (schematic) comparing P2P, P2Pl, and GICP metrics via covariance geometry.
  White background, clean vector style, all in-figure text Chinese only.
  Use the same curved target surface cross-section (blue arc) in all three columns.

  Left column "P2P（各向同性）":
  - Show a few source points (red) slightly off the surface.
  - Draw spherical error blobs (light red) to indicate isotropic uncertainty.
  - Show nearest-point dashed arrows; add a short note "对切向偏移更敏感".

  Middle column "P2Pl（切平面投影）":
  - Draw flat disk-like error ellipses aligned with the tangent plane; add surface normals.
  - Show only the normal component as strong constraint; tangential as weak/loose.
  - Note "法向强约束，切向较松".

  Right column "GICP（各向异性自适应）":
  - Use different ellipsoid shapes for points on smooth plane/edge/corner regions.
  - Indicate the Mahalanobis metric qualitatively with weighted arrows.
  - Note "随局部几何自适应".

  Bottom strip: a qualitative horizontal comparison bar labeled "权衡（定性）" with three bars P2P/P2Pl/GICP (no numbers).
-->

**闭式协方差估计**是另一条常用的不确定性建模路线：在收敛附近对 ICP 目标做小扰动线性化，并结合测量噪声模型，可推导位姿估计协方差的闭式表达。[Censi](cite:censiAccurateClosedformEstimate2007) 给出了经典推导，并用几组“欠约束/可观测性”很强的场景把误差口径对齐。例如在一个 10 m 边长的正方形环境里，设置真值位姿增量为 $x=(0.1\\text{ m},0,2^{\\circ})$，论文报告定位误差的“真值标准差”约为 $(5.3\\text{ mm},5.3\\text{ mm},0.039^{\\circ})$，闭式估计给出 $(5.4\\text{ mm},5.4\\text{ mm},0.042^{\\circ})$；而在 scan-matching 口径下，真值约为 $(7.6\\text{ mm},7.8\\text{ mm},0.058^{\\circ})$，闭式估计为 $(7.7\\text{ mm},7.7\\text{ mm},0.060^{\\circ})$（论文表格直接对照）[Censi](cite:censiAccurateClosedformEstimate2007)。这类对比的意义在于：当线性化点合理、噪声模型不过分离谱时，闭式协方差并不是“拍脑袋的 Hessian 逆”，它能在毫米/百分之一度的量级上把统计量对齐。与 Stein ICP 的粒子后验相比，闭式协方差计算更轻量、易于在线集成，但它也更依赖噪声假设与收敛附近的线性化前提。

因此闭式协方差更适合回答“在当前单峰近似下，不确定性大概有多大”，并不擅长处理明显多模态、强非线性或数据关联本身不确定的情形。它很实用，但不能把它误当成完整后验。

### 3.4.7 Stein ICP：后验分布估计

Stein ICP [Maken et al.](cite:makenSteinICPUncertainty2022) 将变换估计从点估计（MAP）扩展到完整后验分布估计 $p(R,t|\mathcal{P},\mathcal{Q})$。采用 Stein 变分梯度下降（SVGD），维护一组粒子 $\{\boldsymbol{\xi}_k\}_{k=1}^K$（每个粒子代表一个候选变换），通过下式同时最大化每个粒子的似然并保持粒子间多样性：

$$
\dot{\boldsymbol{\xi}}_k = \frac{1}{K}\sum_{j=1}^K \left[k(\boldsymbol{\xi}_j,\boldsymbol{\xi}_k)\nabla_{\boldsymbol{\xi}_j}\log p(\boldsymbol{\xi}_j|\mathcal{P},\mathcal{Q}) + \nabla_{\boldsymbol{\xi}_j}k(\boldsymbol{\xi}_j,\boldsymbol{\xi}_k)\right]
$$
<!-- label: eq:svgd -->

其中 $k(\cdot,\cdot)$ 为 RBF 核。右侧第一项驱动粒子向高概率区域移动（类似梯度上升），第二项通过核梯度产生粒子间排斥力以保持多样性，避免所有粒子塌缩到同一模式。Stein ICP 的输出是一个粒子集而非单一变换，可直接用于后续的安全决策（如自动驾驶避障）和传感器融合（如将 ICP 输出的位姿不确定性输入 EKF）。

在对称场景（如走廊、圆柱形容器）中，ICP 的目标函数可能有多个等效极小值。Stein ICP 能识别并表示这种多模态分布，而点估计方法只返回其中一个，可能是错误的那个 [Maken et al.](cite:makenSteinICPUncertainty2022)。

这篇论文把“粒子后验到底有没有用”用两组数字说得很实在。[Maken et al.](cite:makenSteinICPUncertainty2022) 在 challenging 数据集上用 KL 散度和重叠系数（overlap，OVL）评价后验拟合质量，并在粒子数消融后取 $K=100$ 作为默认设置；对照的 Bayesian ICP 需要 1000 个样本。定量对比表里，Stein ICP 的 KL（中位数）大致落在 0.6–5.7，OVL 在 0.7–0.9；Closed-form ICP 的 OVL 近乎为 0（几乎不重叠，说明“高斯 + 忽略数据关联不确定性”的假设在这些场景下非常乐观）[Maken et al.](cite:makenSteinICPUncertainty2022)。效率方面，作者在 GPU 上对运行时做了组件分解：Stein ICP 的总耗时约为 Bayesian ICP 的 1/8–1/5，并报告“超过 5 倍”的整体加速。这些数值背后对应的是算法结构差异：SVGD 可以按粒子并行更新，而 MCMC 链式采样天然串行，硬件利用率拉不开就只能用样本数硬堆。

即便如此，Stein ICP 的局限仍然很重：它终究要维护一批粒子，计算和显存开销都远高于单解方法；核带宽、粒子数和初始化分布也会直接影响后验质量。对实时前端来说，它通常更像分析工具或高安全需求模块，而不是默认的每帧求解器。

![Stein ICP SVGD 粒子演化与多模态后验表示](../images/ch3-stein-icp-particles.png)
<!-- caption: Stein ICP 以 Stein 变分梯度下降（SVGD）维护一组粒子来近似位姿后验，从而能表达对称/重复几何导致的多模态不确定性。上行：初始粒子在参数空间中分散；中行：在“梯度吸引 + 核排斥”作用下粒子向多个高概率模式移动但不塌缩；下行：与点估计对比，粒子集可以同时覆盖多个等价解，避免把多模态问题强行压缩为单一解。 -->
<!-- label: fig:stein-icp-particles -->
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
  Three-row academic vector figure illustrating SVGD particles capturing a bimodal pose posterior.
  White background, flat style, all in-figure text Chinese only.
  Use a 1D parameter axis labeled "旋转参数 θ" and a y-axis labeled "后验密度".
  Posterior curve: smooth blue bimodal curve with two peaks of equal height (no numeric ticks).
  Row 1 title "初始化": show several colored particles spread across the axis.
  Row 2 title "SVGD 迭代": show three small sub-panels left-to-right labeled "早期", "中期", "后期";
    particles move toward both modes; add solid arrows labeled "梯度力" and dashed double-headed arrows labeled "核排斥".
  Row 3 title "对比": left side shows the final particle set covering both peaks labeled "粒子后验";
    right side shows a single red X at one peak labeled "点估计" with note "可能丢失另一等价解".
  Keep layout clean, generous margins, consistent colors.
-->

### 3.4.8 变换估计方法综合对比

| 方法 | 参数化 | 可估计量 | 计算代价 | 不确定性 | 主要适用场景 |
|------|--------|---------|---------|---------|------------|
| SVD（Kabsch / [Arun et al.](cite:arunLeastSquaresFittingTwo1987)） | 旋转矩阵 | $SE(3)$ | $O(1)$（3×3 SVD） | 无 | 通用首选，数值最稳定 |
| 单位四元数（[Horn](cite:hornClosedformSolutionAbsolute1987)） | 四元数 | $SE(3)$ | $O(1)$（4×4 特征分解） | 无 | 需插值/滤波序列 |
| 李代数（$se(3)$） | 六维向量 | $SE(3)$ | $O(1)$ + 矩阵指数 | 无 | Anderson 加速兼容 |
| 对偶四元数（[Xia et al.](cite:xiaScalingIterativeClosest2017)） | 对偶四元数 | $\text{Sim}(3)$ | $O(1)$ | 无 | 含尺度估计 |
| GICP（[Segal et al.](cite:segalGeneralizedICP2009)） | 旋转矩阵 + 协方差 | $SE(3)$ | $O(nk)$（协方差估计） | 隐式（协方差） | 曲面噪声大的场景 |
| Stein ICP（[Maken et al.](cite:makenSteinICPUncertainty2022)） | 粒子集 | $SE(3)$ 后验 | $O(K^2 n)$（$K$ 粒子） | 显式（完整后验） | 安全关键，多模态 |
<!-- caption: 第 3.4 节 ICP 变换估计方法综合对比：参数化方案、可估计变换群、计算代价、不确定性表示能力与主要适用场景。 -->
<!-- label: tab:transform-comparison -->

| 文献 | 场景/数据集 | 指标口径 | 结果（数值） | 关键设定（便于复现） |
|------|-------------|----------|--------------|-----------------------|
| [Arun et al.](cite:arunLeastSquaresFittingTwo1987) | 合成点对（点数 $N$ 变化） | 端到端求解时间（ms） | VAX 11/780：$N=7/11/16/20/30$ 时，SVD 37.0/40.0/39.2/40.4/44.2 ms；四元数法 26.6/32.8/39.9/45.2/48.3 ms；迭代法 94.2/110.8/120.5/135.0/111.0 ms（迭代次数 5/7/10/6/6） | 对比三类求解器：SVD、四元数特征分解、迭代法；表格直接给出用时与迭代次数 |
| [Horn](cite:hornClosedformSolutionAbsolute1987) | 刚体配准闭式解 | 解的结构（矩阵规模/约束维数） | 构造 4×4 对称矩阵 $N$，取最大特征值对应特征向量作为最优四元数 | 旋转用 4 维单位四元数；分解是固定规模特征分解（但 $H$ 的构造仍需线性遍历点对） |
| [Zhang et al.](cite:zhangFastRobustIterative2022) | FRICP 实验设置 | 终止条件（公平对比口径） | ICP / ICP-l / AA-ICP：最多 1000 次迭代，或 $\|\Delta T\|_F<10^{-5}$ | 在 $se(3)$ 上做“加法更新”，便于 Anderson 加速；统一终止口径避免“停得早/晚”带来的假象 |
| [Xia et al.](cite:xiaScalingIterativeClosest2017) | 模拟 3D 曲线 + 真实点云 | 变换群维数与数据源 | $SE(3)$ 6 自由度扩展到 $\text{Sim}(3)$ 7 自由度；点名使用 PSB 与 Stanford Bunny | 用对偶数四元数把旋转/平移/尺度并入同一框架；每轮迭代在对应固定时可做一步求解 |
| [Segal et al.](cite:segalGeneralizedICP2009) | 模拟 + Velodyne 实测扫描对 | 邻域规模、迭代预算与场景尺度 | 协方差用 20 近邻估计；ICP 迭代上限 250，P2Pl/GICP 上限 50；实测示例两帧约 30 m 间隔，量测范围约 70–100 m | 以“点级协方差”把 P2P/P2Pl 统一到同一概率度量；内层求解用 GN/LM |
| [Censi](cite:censiAccurateClosedformEstimate2007) | 10 m 正方形环境（欠约束分析示例） | 位姿协方差（标准差）对照 | 真值：$(5.3\\text{ mm},5.3\\text{ mm},0.039^{\\circ})$；闭式估计：$(5.4\\text{ mm},5.4\\text{ mm},0.042^{\\circ})$；scan-matching 口径真值：$(7.6\\text{ mm},7.8\\text{ mm},0.058^{\\circ})$，闭式估计：$(7.7\\text{ mm},7.7\\text{ mm},0.060^{\\circ})$（真值位姿增量 $x=(0.1\\text{ m},0,2^{\\circ})$） | 收敛附近线性化 + 噪声模型推导闭式协方差；讨论欠约束时可观测子空间的处理 |
| [Maken et al.](cite:makenSteinICPUncertainty2022) | RGB-D（碗/杯等对称物体）+ challenging LiDAR 场景 | KL / OVL + 运行时 | 取 $K=100$ 粒子；Bayesian ICP 1000 样本。Stein ICP 的 KL（中位数）约 0.6–5.7，OVL 约 0.7–0.9；运行时约为 Bayesian ICP 的 1/8–1/5，整体加速 >5× | SVGD 按粒子并行更新（GPU 友好）；能表达对称/重复几何导致的多模态后验 |
<!-- caption: 第 3.4 节代表性“可复现设置 + 定量结果”汇总（覆盖本节正文出现的全部引用）。 -->
<!-- label: tab:transform-data -->

### 3.4.9 选择建议

对于大多数工程应用，SVD 闭式解（Kabsch/Arun）是默认选择——数值稳定、实现简单、$3\times3$ 矩阵分解几乎可以忽略的计算代价。当需要集成到 Kalman 滤波器或轨迹优化框架时，四元数或 $se(3)$ 表示更为自然。当处理多传感器标定或多分辨率场景时，$\text{Sim}(3)$ 的对偶四元数扩展是标准选择。当目标是提供位姿不确定性估计（如用于安全决策或融合）时，GICP 提供协方差近似，Stein ICP 提供完整后验——前者计算代价适中，后者精确但慢，适合离线后处理或高安全需求场景。

变换估计方法的选择与[第 3.1 节](ref:sec:correspondence)中的对应度量直接耦合：P2P + Kabsch 是最简单组合；P2Pl + 线性化 + Gauss-Newton 是工程中常用的高效组合；GICP 则自动在数据驱动下折中 P2P/P2Pl 的约束形态。[第 3.6 节](ref:sec:global-init) 将讨论在无可靠初始位姿时，如何通过全局方法为局部 ICP 提供可用的收敛起点。
