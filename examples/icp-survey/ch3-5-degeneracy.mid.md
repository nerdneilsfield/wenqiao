## 3.5 几何退化与可定位性 (Geometric Degeneracy and Localizability)
<!-- label: sec:degeneracy -->

[第 3.4 节](ref:sec:transform) 的 Kabsch/SVD 求解在 $H = J^\top J$ 满秩时给出唯一的最优变换。然而，当点云的几何结构无法约束所有 6 个自由度时，$H$ 在某些方向上奇异，ICP 的解沿这些方向变得任意，这便是**几何退化**（geometric degeneracy）。退化与外点（见[第 3.2 节](ref:sec:outlier)）的区别在于：外点问题源于“数据坏了”，可以通过鲁棒估计消掉；退化问题源于“点云本身在某些方向上没有足够几何约束”，再精细的对应也救不回来。自 [Zhang et al.](cite:zhangDegeneracyOptimizationBased2016) 在 ICRA 2016 将退化问题明确地拉到“可观测性/病态方向”这一层面后，围绕检测、量化与处理退化的研究形成了独立分支。Zhang 等在其自建的视觉+激光组合里程计实验里给了一个很直观的量化：在一段 538 m 的轨迹上，采用其 solution remapping 后，终点位置误差约为轨迹长度的 0.71%[Zhang et al.](cite:zhangDegeneracyOptimizationBased2016)。后续的 X-ICP 系列工作进一步把“哪几个自由度退化、退化到什么程度、如何把更新限制在可信子空间”做成了可复用模块：在 Seemühle 地下矿坑（VLP‑16）的对照里，X-ICP 报告的终点误差为 0.27 m；而同一设置下，二值阈值法（Zhang）与更悲观的条件数检测（Hinduja）分别达到 6.37 m 与 24.17 m，这组对比几乎把“能不能用”直接分开了 [Tuna et al.](cite:tunaXICPLocalizabilityAwareLiDAR2022)。

### 3.5.1 退化的数学本质

P2Pl ICP 的线性化目标函数在一次迭代内等价于求解正规方程：

$$
H \, \delta x = b, \quad H = \sum_i n_i n_i^\top \otimes J_i^\top J_i
$$
<!-- label: eq:ptp-normal -->

其中 $n_i$ 为目标点法向量，$J_i$ 为变换对应的点 Jacobian。$H$ 是一个 $6 \times 6$ 正半定矩阵，其特征值分解 $H = U \Sigma U^\top$ 揭示了优化的几何含义：特征值 $\sigma_k$ 越大，对应方向 $u_k$ 上的约束越强；$\sigma_k \to 0$ 则意味着无论 $\delta x$ 在 $u_k$ 方向上取何值，目标函数几乎不变——ICP 更新量在该方向上无意义。

这种“用 Hessian 谱刻画约束强弱/可观测性”的观点也常用于 ICP 的不确定性建模，例如闭式协方差估计中会显式讨论欠约束方向如何影响位姿不确定性 [Censi](cite:censiAccurateClosedformEstimate2007)。Censi 在一个 $10\\,\\text{m}\\times 10\\,\\text{m}$ 的方形环境里用 $x=(0.1\\,\\text{m},0,2^{\\circ})$ 的位姿扰动做示例，把闭式协方差的结论直接写成“毫米/角秒”级别的数字：在欠约束分析口径下，真值标准差约为 $(5.3\\text{ mm},5.3\\text{ mm},0.039^{\\circ})$，闭式估计为 $(5.4\\text{ mm},5.4\\text{ mm},0.042^{\\circ})$；而在 scan-matching 口径下，真值约为 $(7.6\\text{ mm},7.8\\text{ mm},0.058^{\\circ})$，闭式估计为 $(7.7\\text{ mm},7.7\\text{ mm},0.060^{\\circ})$（论文表格直接对照）[Censi](cite:censiAccurateClosedformEstimate2007)。这组数字的意思很朴素：一旦某个方向的几何约束变弱，协方差会立刻“鼓起来”，这不是求解器写错了，而是信息本身不够。

**退化几何的典型模式**。走廊（无限长直壁）：所有法向量集中于水平面内，法向量矩阵的零空间包含沿走廊轴的平移方向，$H$ 有 1 个近零特征值；圆形隧道：法向量分布于以轴为中心的圆柱面，$H$ 有 2 个近零特征值（轴向平移 + 绕轴旋转）；开阔平面（停机坪）：仅有竖直法向量，$H$ 有 5 个近零特征值，仅约束竖直方向平移。

**对应关系的物理意义**。[Zhang et al.](cite:zhangDegeneracyOptimizationBased2016) 将退化问题推广到一般基于优化的状态估计：若 $J$ 的 SVD 的最小奇异值 $\sigma_{\min} < \tau$，则相应状态分量的估计不可靠。这一判据直接适用于 P2Pl ICP，其中 $J$ 即为点到平面残差关于 $\delta x$ 的 Jacobian。

![几何退化场景与法向量分布分析](../images/ch3-degeneracy-geometry.png)
<!-- caption: 三类典型几何退化场景及其法向量分布与信息矩阵谱的定性关系。上行：走廊通常出现“单一方向约束不足”（轴向平移不易被平面法向约束）；圆形隧道可能同时缺失轴向平移与绕轴旋转的约束；开阔平面则只约束少数自由度，更多方向呈现近零曲率。下行：对应的 Gauss 映射（法向量在单位球面上的分布）直观解释了“约束来自哪些法向集合”，并与 Hessian 的近零特征方向一一对应。 -->
<!-- label: fig:degeneracy-geometry -->
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
  Three-column academic diagram (schematic): geometric degeneracy patterns in point cloud registration.
  Layout: three columns (走廊 / 圆形隧道 / 开阔平面), two rows.

  Row 1 "场景":
  - Column 1 "走廊": 3D sketch of a corridor; draw many wall normals as short blue arrows. Add one red arrow along the corridor axis labeled "退化方向".
  - Column 2 "圆形隧道": circular tunnel sketch; draw radial normals. Add two red arrows labeled "退化方向" (one axial translation, one axial rotation) but do not use any symbols or numbers.
  - Column 3 "开阔平面": large flat ground; draw vertical normals. Add multiple faint red arrows indicating "多方向约束不足" (no numbers).

  Row 2 "法向量分布（Gauss 映射）":
  - For each column, show a unit sphere outline with dots representing normals.
  - Corridor: dots concentrate on an equator-like arc.
  - Tunnel: dots form a latitude-like ring.
  - Plane: dots concentrate near one pole.

  Styling: white background, flat vector style, blue/red palette, all in-figure text Chinese only.
-->

### 3.5.2 退化检测方法

退化检测的目标是在 ICP 求解前（或求解中）识别哪些自由度约束不足，以便在这些方向上引入先验约束或触发传感器融合。

**特征值阈值法**（[Zhang et al.](cite:zhangDegeneracyOptimizationBased2016)）最直接：计算 $H$ 的最小特征值 $\sigma_{\min}$，若低于阈值 $\tau$，就判为退化，把更新量投影到非退化子空间。问题也出在这根阈值上：它既受场景尺度和点云密度影响，又很难给出“一劳永逸”的经验值。后续工作在复现实验时往往不得不把它当作显式超参去扫：LP-ICP 的消融里，同一条序列把阈值 Thr 从 50 增到 100，RMSE（ATE）会从 36.60 m 直接飙到 195.57 m，几乎等于把系统推向失效边缘[Yue et al.](cite:yueLPICPGeneralLocalizabilityAware2025)；X-ICP 的对照实验同样指出，如果不针对环境调阈值（文中给出的区间是把 Thr 从 120 调到 200），Zhang 的二值退化检测很容易在回程隧道段出现 LiDAR slip，导致终点误差到 6.37 m，而 X-ICP 同设置下仅 0.27 m [Tuna et al.](cite:tunaXICPLocalizabilityAwareLiDAR2022)。因此，阈值法更像一把“能用但难伺候”的扳手：一旦环境换了、点云密度换了，扳手的刻度就不再对。

它的局限不只是“参数敏感”这么简单，而是这种敏感往往没有明显先兆：同一根阈值在一段走廊里还有效，换到开阔区或稀疏矿道就可能突然开始误报或漏报；一旦检测结果错了，后面的约束策略也会跟着一起错。

**X-ICP 多类别可定位性分析**（[Tuna et al.](cite:tunaXICPLocalizabilityAwareLiDAR2022)）将退化细分为三类：完全可定位（6 DOF 均约束充分）、部分可定位（部分 DOF 退化）和不可定位（严重几何对称）。对每一个对应关系 $(p_i, q_i, n_i)$，X-ICP 计算其在各主方向 $u_k$ 上贡献的约束强度 $s_{ik} = |n_i^\top J_i u_k|^2$，聚合后得到每个方向的可定位性分数（localizability score）$L_k = \sum_i s_{ik}$。这种“方向分辨”的输出不是为了好看，而是直接能对接后端约束提交：在 Seemühle 地下矿坑（VLP‑16）的对照里，X-ICP 报告的终点误差仅 0.27 m，而二值阈值法（Zhang）和更悲观的条件数检测（Hinduja）分别到 6.37 m 和 24.17 m，差距几乎把“能不能用”分开了[Tuna et al.](cite:tunaXICPLocalizabilityAwareLiDAR2022)。

**概率退化检测**（[Hatleskog and Alexis](cite:hatleskogProbabilisticDegeneracyDetection2024)）对 P2Pl Hessian 的不确定性建模：$H$ 由含噪点坐标和法向量构成，其扰动 $\delta H$ 的分布可由传感器测量噪声推导。由此将"某方向是否退化"转化为带置信度的判别（例如：$P(\sigma_k < \tau)$ 超过触发阈值），从而把“特征值阈值法”的经验调参，替换为与噪声模型相一致的概率声明。作者在其四组真实场景实验中展示了更稳定的触发行为与更好的退化缓解效果；同时也给出了运行代价的量化：在 Intel i7-12800H 上，实验 2 的 LOAM 扫描匹配中位运行时间为 17 ms，其中退化检测开销占比为 5.4%；在 Khadas VIM4 上使用单个 A73 核心时，中位运行时间为 54 ms [Hatleskog and Alexis](cite:hatleskogProbabilisticDegeneracyDetection2024)。

这类方法的局限则在于噪声模型本身要足够靠谱。若点坐标噪声、法向误差或时间同步误差的统计假设和真实系统差得很远，那么“概率更合理”也可能只是建立在错模型上的精细判断。

**点分布退化检测**（[Ji et al.](cite:jiPointtodistributionDegeneracyDetection2024)）用点到分布（point-to-distribution）匹配替代点到平面，通过自适应体素分割捕获点云的局部几何模型。该方法对噪声更鲁棒（分布估计平滑了单点扰动），并在论文实验中以“误检测次数/Precision-Recall”等指标对比特征值类方法，强调其能降低“噪声诱发误报警”的问题：例如在 M2DGR 的 street 01 场景中给出误检测次数从 125 降至 10；在走廊类场景的 Precision-Recall 实验中，报告 Recall 从 0.7178 提升到 0.9568 [Ji et al.](cite:jiPointtodistributionDegeneracyDetection2024)。

代价是它把退化检测又往前推了一层建模：体素划分、分布拟合和邻域统计一旦设置不合适，检测结果同样会跟着漂。相比直接看谱，它更稳，但实现链条也更长。

![退化检测方法对比与可定位性分数可视化](../images/ch3-degeneracy-detection.png)
<!-- caption: 三种退化检测范式的对比示意。左：特征值阈值法通过“谱是否过小”给出整体退化判别，简单但易受尺度与密度影响；中：X-ICP 将约束强度分解到 6 个自由度方向，以雷达图形式输出可定位性分数，便于后续“只在可信方向提交约束”；右：概率退化检测输出各方向的退化置信度随迭代的变化，用于在系统中触发软约束/传感器融合。 -->
<!-- label: fig:degeneracy-detection -->
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
  Three-panel academic comparison (schematic) of degeneracy detection outputs.
  White background, clean vector style, all in-figure text Chinese only.

  Panel (a) "特征值阈值法":
  - A bar chart with 6 bars labeled "σ1"..."σ6" (no numeric values).
  - A dashed horizontal line labeled "阈值".
  - One or two bars clearly below the line and tinted red with a small warning mark.
  - Side note: "简单" / "易受尺度影响" (as short Chinese phrases).

  Panel (b) "X-ICP 可定位性":
  - A hexagon radar chart with axes labeled "t_x t_y t_z r_x r_y r_z" (Chinese-only context, no English).
  - The filled polygon shows one or two axes almost empty (degenerate), others larger (well-constrained).
  - Small legend: "可定位" (green) / "退化" (red), purely qualitative.

  Panel (c) "概率退化检测":
  - A line chart with x-axis "迭代步", y-axis "退化置信度".
  - One line rises above a dashed "触发阈值" line; other lines stay below.
  - No numeric ticks; keep it qualitative.
-->

### 3.5.3 退化方向的约束优化

检测到退化后，ICP 需要在退化方向上引入替代约束，而非直接求解病态线性系统。主要策略分为"主动约束"（修改优化更新方向）和"软约束"（引入先验惩罚项）两类。

**截断奇异值分解（Truncated SVD, TSVD）**是最早也是最简单的主动约束方案：对 $H = U \Sigma V^\top$ 截断奇异值，令小于阈值的奇异值置零，得到伪逆 $H^+ = V \Sigma^+ U^\top$，位姿更新变为 $\delta x = H^+ b$。效果等价于将更新量投影到良约束子空间，退化方向的更新量强制为零。缺陷是零更新量意味着在退化方向上完全不移动，等价于隐式施加"退化方向位移为零"的硬约束，与实际场景（走廊中仍需沿轴向移动，只是来自 ICP 的约束不可靠）不匹配。

也正因为这个原因，TSVD 更适合短时“保守止血”，不适合长时间连续运行在单向退化环境里。时间一长，真实运动和“被归零的更新”之间的偏差会持续累积。

**Tikhonov 正则化（软约束）**在目标函数中加入先验惩罚：

$$
\delta x^* = \arg\min_{\delta x} \|J \delta x - r\|^2 + \lambda_k \|\delta x - \delta x_\text{prior}\|^2_{W}
$$
<!-- label: eq:tikhonov-reg -->

其中 $\delta x_\text{prior}$ 来自 IMU 预积分或恒速运动外推，正则化权重 $\lambda_k$ 与退化程度（例如奇异值越小，越“拉向先验”）成正比。与 TSVD 的区别在于：退化方向不被归零，而是被“拉向先验”，既避免了硬投影带来的不连续，也给了系统在退化方向上继续前进的空间。[Tuna et al.](cite:tunaInformedConstrainedAligned2025) 在 2025 年的野外系统评测里把这件事说得很实在：在 Ulmberg 隧道这种“长时间单向退化”的工况下，基线 P2Plane 的 ATE 到 2.90 m，而非线性正则（NL‑Reg.）能压到 1.097 m；对应的局部误差（RTE）上，不等式约束与 NL‑Reg. 的最好结果分别是 0.033 m 与 0.035 m（Prior only 为 1.54 m）。在 ANYmal 森林实验里，如果只依赖腿部里程计先验，ATE 为 0.662 m；加入正则后，NL‑Reg. 与 NL‑Solver 分别到 0.364 m 与 0.342 m（Eq. Con. 为 0.490 m）[Tuna et al.](cite:tunaInformedConstrainedAligned2025)。这些数字背后的取舍也很明确：NL‑Reg. 的计算代价约是线性方法的 5 倍（作者报的量级是 80 ms vs 20 ms），要不要上它，取决于你能不能承受把 10 Hz 预算吃掉一半。

**X-ICP 紧耦合约束优化**（[Tuna et al.](cite:tunaXICPLocalizabilityAwareLiDAR2022)）将可定位性分析结果直接嵌入 ICP 优化步骤：构造方向选择矩阵 $S_\mathcal{L}$（保留良约束方向）和 $S_\mathcal{D}$（退化方向），将变换更新分解为：

$$
\delta x = S_\mathcal{L} \, H_\mathcal{L}^{-1} b_\mathcal{L} + S_\mathcal{D} \, \delta x_\text{ext}
$$
<!-- label: eq:xicp-update -->

其中 $\delta x_\text{ext}$ 来自外部传感器（IMU、轮速计）对退化方向的约束。良约束方向的更新无漂移（受 ICP 精确约束），退化方向的更新来自外部先验，实现两者的零漂移组合。

它的局限非常现实：一旦外部先验本身带偏，系统就会把这个偏差明确地灌进退化方向。X-ICP 的优势来自“知道该相信谁”，但这也意味着先验质量一差，收益会迅速缩水。

**不等式约束**（[Tuna et al.](cite:tunaInformedConstrainedAligned2025)）把退化方向的更新写成界约束 $|(\delta x)_k| \leq \epsilon$，再用 QP 去解。这里的 $\epsilon$ 就是工程上能直接把握的“我最多允许它在这条方向上抖多少”。在 Ulmberg 隧道上，作者给出的折中值是 $\epsilon=0.0014$，并配套报告了正则项的调参（例如线性正则 $\lambda=440$，非线性正则 $\lambda_D=675$）；他们还做了先验噪声敏感性测试：把平移先验噪声拉到 $\sigma_t=0.05\\,\\text{m}$ 后，除 Eq. Con. 外多数方法会发散[Tuna et al.](cite:tunaInformedConstrainedAligned2025)。这组实验让“不等式/正则化到底在吃什么信息”更清楚：不是它们本身多神奇，而是它们把系统对外部先验质量的依赖暴露成了可量化的边界条件。

它的局限同样很清楚：约束一旦收得太紧，就会把真实运动一起压死；放得太松，又起不到抑制漂移的作用。它比 TSVD 更柔和，但本质上仍然在“安全”和“机动性”之间做硬权衡。

![退化约束优化三种策略对比](../images/ch3-degeneracy-handling.png)
<!-- caption: 退化方向约束优化三策略的更新量几何直观（二维示意）。左：无约束 ICP 的等值线在退化方向形成“长槽”，更新量可在槽内滑动导致漂移；中：TSVD 将更新量投影到非退化子空间，能抑制漂移，但同时压制了退化方向的真实运动；右：软约束（如 Tikhonov）将外部先验作为“锚点”把长槽收紧，使更新在退化方向随先验变化而非任意漂移。下方以定性曲线示意三者的漂移累积趋势。 -->
<!-- label: fig:degeneracy-handling -->
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
  Three-panel geometric visualization (schematic): handling degenerate directions in ICP optimization.
  White background, clean vector style, all in-figure text Chinese only.

  Common coordinate system in all panels: x-axis "退化方向", y-axis "良约束方向" (no symbols, no numbers).

  Panel (a) "无约束":
  - Draw elongated contour lines forming a long valley along the x-axis.
  - A point and an update arrow sliding along the valley; annotate "易漂移".

  Panel (b) "TSVD 投影":
  - Same long valley.
  - Update arrow projected perpendicular to the valley (mostly along y-axis); annotate "抑制漂移" and "抑制真实运动" as short phrases.

  Panel (c) "软约束/外部先验":
  - Same valley plus a prior anchor point (green diamond) labeled "先验".
  - Show modified contours tightened around the anchor so the update arrow heads toward it; annotate "跟随先验".

  Bottom strip: a small qualitative line chart "漂移累积" with three curves labeled "无约束/TSVD/软约束" (no numeric axes).
-->

### 3.5.4 退化鲁棒的 ICP 变体

除在优化步骤引入外部约束外，另一类方法通过算法自身的自适应机制降低对外部传感器的依赖，在纯 LiDAR 场景下提升鲁棒性。

**GenZ-ICP**（[Lee et al.](cite:leeGenZICPGeneralizableDegeneracyRobust2025)，RA-L 2025）重新审视 P2P 与 P2Pl 两种误差度量的互补性：P2Pl 在平面丰富的环境（室内房间）精度高，但在走廊中法向量平行导致退化；P2P 在走廊场景中仍提供轴向约束（点到点距离不受法向量分布影响）。GenZ-ICP 根据当前帧的局部几何特征（平面点比例、法向量集中度）自适应计算融合权重 $w_\text{P2Pl}, w_\text{P2P}$（两者之和为 1）：

$$
\mathcal{L}_\text{GenZ} = w_\text{P2Pl} \sum_i (n_i^\top (Rp_i + t - q_i))^2 + w_\text{P2P} \sum_i \|Rp_i + t - q_i\|^2
$$
<!-- label: eq:genz-icp -->

走廊场景自动偏向 P2P（$w_\text{P2P} \to 1$），平面丰富场景自动偏向 P2Pl（$w_\text{P2Pl} \to 1$），无需外部传感器或手动切换。原文在 SubT-MRS 的 Long_Corridor 序列上也给了直观的量化对比：Point-to-plane ICP 的 APE 均值为 32.84 m、Point-to-point ICP 为 6.83 m，而 GenZ-ICP 将 APE 降至 1.69 m（同表 CT-ICP 为 44.18 m，Zhang et al. 为 19.43 m）[Lee et al.](cite:leeGenZICPGeneralizableDegeneracyRobust2025)。

它的局限是仍然把希望押在“两种经典度量的加权足够覆盖主要退化模式”上。若场景几何比“走廊 vs 平面”更复杂，或者法向统计本身不稳定，自适应权重就未必能准确反映真实可观性。

**LP-ICP**（[Yue et al.](cite:yueLPICPGeneralLocalizabilityAware2025)，2025）把 X-ICP 的可定位性分析从“只盯着点到平面”扩展到“线+面一起算”：边缘点（低平滑度）通过点到线约束补上走廊轴向信息，平面点（高平滑度）继续提供法向约束。它的优势主要体现在“平面约束不够、但线特征还在”的极端工况里：作者在 PLAM 的 `a2_traverse` 上报告 ATE 从 36.60 m 降到 12.31 m；在 SubT‑MRS 的长走廊序列上从 24.71 m 降到 11.92 m；在 PLAM `a3_odom` 上从 18.08 m 降到 7.44 m；在 CERBERUS 的 `ANYmal 2` 上从 0.32 m 降到 0.24 m。更关键的是它没有靠“加很多算力”换结果：在 Intel i7‑12700H 上，scan‑to‑map 配准平均耗时 35.87 ms，与 LVI‑SAM（38.04 ms）同量级[Yue et al.](cite:yueLPICPGeneralLocalizabilityAware2025)。

**DAMM-LOAM**（[Chandna and Kaushal](cite:chandnaDAMMLOAMDegeneracyAware2025)，2025）走的是“先把几何结构分清楚，再谈退化”的路线：用球面投影的法向量图把点云分成地面、墙面、屋顶、边缘与非平面点五类，再把不同类别的残差按退化程度做加权融合。它在走廊类数据上的量化很有代表性：在 SubT‑MRS 的 Long_Corridor 序列上，APE RMSE 报告为 1.72 m（KISS‑ICP 为 8.72 m，GenZ‑ICP 为 1.99 m），APE Max 为 4.08 m；在 Ground‑Challenge 的 Corridor1 上 APE RMSE 仅 0.06 m（GenZ‑ICP 0.24 m，KISS‑ICP 2.17 m），Corridor2 为 0.08 m（GenZ‑ICP 0.20 m）[Chandna and Kaushal](cite:chandnaDAMMLOAMDegeneracyAware2025)。这些数字背后其实是一个很“朴素”的结论：在走廊里，哪怕都是 LiDAR-only，能不能把墙、地、边缘这些约束拆清楚，直接决定了退化方向上漂移会不会被放大。

但这类方法也更依赖前面的结构划分是否稳定。一旦类别分错了，后面的加权就会建立在错误的几何理解上，系统复杂度也会明显高于“直接做一个统一 ICP”。

**退化感知位姿图因子**（[Hinduja et al.](cite:hindujaDegeneracyAwareFactorsApplications2019)，IROS 2019）把“只在可信方向提交约束”这件事落到了因子图里：退化感知 ICP 不再硬塞一个全 6‑DOF 的相对位姿，而是把信息矩阵在退化方向对应的分量置零，只保留良约束子空间的约束，让后端优化明确知道“哪些方向这条边说不准”。他们在水下声纳 SLAM（DIDSON 声纳，强退化几何）里给了一个很工程的指标：在某组数据上，动态阈值机制会直接拒绝 25 个错误闭环，从源头上避免把退化对齐的“假约束”灌进图优化里[Hinduja et al.](cite:hindujaDegeneracyAwareFactorsApplications2019)。

### 3.5.5 系统融合视角：退化检测与传感器切换

退化检测的最终目的不是“打标签”，而是触发合适的约束提交与传感器融合策略。[Wang et al.](cite:wangRecentAdvancesSLAM2025) 在 2025 年的退化环境 SLAM 综述里把这类系统抽象成“感知–决策”的闭环：一方面，GNSS 定位至少需要 4 颗卫星信号，一进隧道/矿井就天然缺观测；另一方面，多传感器融合在工程上几乎离不开高频 IMU（常见 >100 Hz）去填补 LiDAR/视觉较低频帧率的间隙。于是退化检测一旦触发，系统做的不是“继续硬解一个 6‑DOF”，而是把不可靠的方向交给更合适的先验或传感器来约束：

1. **检测阶段**：X-ICP 可定位性分析 / 概率检测给出每个方向的退化程度。
2. **决策阶段**：根据退化程度和可用传感器选择处理策略——轻微退化可用 Tikhonov 软约束稳定更新；严重退化且有 IMU/里程计时采用紧耦合约束优化（X-ICP 模式）提交“部分可信”的位姿增量；严重退化且缺乏外部先验时，可切换到算法自适应的度量（如 P2P+P2Pl 融合）或使用 TSVD 投影并降低因子权重。
3. **验证阶段**：系统级指标（配准残差、IMU 一致性检验）验证约束策略是否有效，动态调整退化检测阈值。

这一框架使 LiDAR SLAM 系统能够在退化环境中实现"优雅降级"（graceful degradation）而非硬性失败。

### 3.5.6 方法综合对比

| 方法 | 退化检测类型 | 处理策略 | 需外部传感器 | 代表场景 |
|------|------------|---------|------------|---------|
| Zhang et al. [Zhang et al.](cite:zhangDegeneracyOptimizationBased2016) | 特征值阈值 | TSVD 投影 | 否 | 走廊（理论分析） |
| X-ICP [Tuna et al.](cite:tunaXICPLocalizabilityAwareLiDAR2022) | 多类别可定位性 | 紧耦合约束优化 | 是（IMU/里程计） | 地下矿山、隧道 |
| Hatleskog & Alexis [Hatleskog and Alexis](cite:hatleskogProbabilisticDegeneracyDetection2024) | 概率 Hessian 噪声 | 平滑衰减更新 | 否 | 走廊、室外开阔区 |
| Ji et al. [Ji et al.](cite:jiPointtodistributionDegeneracyDetection2024) | 点到分布自适应体素 | 检测触发融合 | 可选 | 走廊、隧道 |
| GenZ-ICP [Lee et al.](cite:leeGenZICPGeneralizableDegeneracyRobust2025) | 隐式（自适应权重） | P2P+P2Pl 联合度量 | 否 | 走廊（纯 LiDAR） |
| LP-ICP [Yue et al.](cite:yueLPICPGeneralLocalizabilityAware2025) | 线+面多类别 | 扩展 X-ICP 约束 | 是（IMU/里程计） | 非结构化极端环境 |
| Hinduja et al. [Hinduja et al.](cite:hindujaDegeneracyAwareFactorsApplications2019) | 特征值（ICP内） | 部分约束位姿图因子 | 否（位姿图级） | 水下声纳 SLAM |
| Tuna et al. 2025 [Tuna et al.](cite:tunaInformedConstrainedAligned2025) | 多方法比较 | TSVD/Ineq/Tikhonov | 是（IMU） | 系统评测综合场景 |
<!-- caption: 第 3.5 节退化感知 ICP 方法综合对比：退化检测类型、优化处理策略、是否依赖外部传感器及代表性测试场景。 -->
<!-- label: tab:degeneracy-comparison -->

| 文献 | 场景/数据集 | 指标口径 | 结果（数值） | 关键设定/前提 |
|------|-------------|----------|--------------|---------------|
| [Zhang et al.](cite:zhangDegeneracyOptimizationBased2016) | 视觉+LiDAR 自建里程计测试（文中 Test 3） | 终点位置误差（相对轨迹长度） | 轨迹长度 538 m；终点位置误差约为 0.71% | 用特征分解识别退化方向，并用 solution remapping 在退化方向用 best guess 替代求解 |
| [Censi](cite:censiAccurateClosedformEstimate2007) | 10 m × 10 m 方形环境（论文数值示例） | 位姿协方差（平移/旋转标准差量级） | 扰动 $x=(0.1\\,\\text{m},0,2^{\\circ})$；示例中 $\\sigma_t$ 量级约 $10^{-3}$ m、$\\sigma_r$ 量级约 $10^{-2}$ 度 | 闭式协方差估计强调欠约束方向会导致不确定性快速膨胀 |
| [Tuna et al.](cite:tunaXICPLocalizabilityAwareLiDAR2022) | Seemühle 地下矿坑（VLP‑16） | End Position Error + APE/RPE | End Pos. Error 0.27 m；APE 平移均值/标准差 2.45(1.35) m；RPE(10 m) 平移 0.17(0.12) m | 多类别 localizability 检测 + 方向选择矩阵；对比 Zhang/Hinduja（同场景 End Pos. Error 6.37 m/24.17 m） |
| [Hatleskog and Alexis](cite:hatleskogProbabilisticDegeneracyDetection2024) | 4 组真实场景（论文实验 2 含 LOAM scan matching） | 运行时与检测开销占比 | i7‑12800H：中位 17 ms，检测开销占比 5.4%；VIM4 单 A73：中位 54 ms | 用噪声模型推导 Hessian 扰动分布，把触发写成概率事件 |
| [Ji et al.](cite:jiPointtodistributionDegeneracyDetection2024) | M2DGR street 01 + 走廊类场景 | 误检测次数 + Precision/Recall | street 01 误检测次数 125 → 10；Recall 0.7178 → 0.9568 | 点到分布模型 + 自适应体素，抑制噪声诱发的误报警 |
| [Lee et al.](cite:leeGenZICPGeneralizableDegeneracyRobust2025) | SubT‑MRS Long_Corridor | APE 均值（m） | P2Pl 32.84 m；P2P 6.83 m；GenZ‑ICP 1.69 m | 自适应融合 P2P/P2Pl，走廊自动偏向 P2P，平面丰富区域偏向 P2Pl |
| [Yue et al.](cite:yueLPICPGeneralLocalizabilityAware2025) | PLAM + SubT‑MRS + CERBERUS | ATE + 运行时间 | `a2_traverse` 36.60 → 12.31 m；长走廊 24.71 → 11.92 m；`a3_odom` 18.08 → 7.44 m；ANYmal 2 0.32 → 0.24 m；平均 35.87 ms（i7‑12700H） | 点到线+点到平面联合 localizability；并报告 Thr 从 50 到 100 会把 RMSE 从 36.60 m 拉到 195.57 m（阈值敏感性） |
| [Chandna and Kaushal](cite:chandnaDAMMLOAMDegeneracyAware2025) | SubT‑MRS Long_Corridor + Ground‑Challenge Corridor1/2 | APE RMSE（m）与 Max | Long_Corridor：APE RMSE 1.72 m（KISS‑ICP 8.72 m，GenZ‑ICP 1.99 m），APE Max 4.08 m；Corridor1 0.06 m（GenZ‑ICP 0.24 m），Corridor2 0.08 m（GenZ‑ICP 0.20 m） | 五类几何分类 + 退化加权 WLS + Scan Context 回环 |
| [Hinduja et al.](cite:hindujaDegeneracyAwareFactorsApplications2019) | 水下声纳 SLAM（DIDSON） | 错误闭环拒绝数量（示例） | 某组数据直接拒绝 25 个错误闭环 | 退化 ICP 输出以“部分约束因子”入图，退化方向信息矩阵置零 |
| [Tuna et al.](cite:tunaInformedConstrainedAligned2025) | ANYmal 森林 + Ulmberg 隧道 | ATE/RTE + 参数与时延 | Ulmberg：P2Plane ATE 2.90 m，NL‑Reg. 1.097 m；Ineq. Con. RTE 0.033 m；调参 $\epsilon=0.0014$、$\lambda=440$、$\lambda_D=675$；NL‑Reg. 约 80 ms vs 线性法约 20 ms；先验噪声 $\sigma_t=0.05\\,\\text{m}$ 时多法发散 | 系统性对比 TSVD/Ineq./Tikhonov，强调主动退化缓解与先验质量边界 |
| [Wang et al.](cite:wangRecentAdvancesSLAM2025) | 退化环境 SLAM 综述（GNSS 拒止/视觉退化/特征退化等） | 退化场景下的观测与融合节拍（综述中的工程事实） | GNSS 至少需要 4 颗卫星信号；多传感器融合常依赖 >100 Hz IMU 补低频 LiDAR/视觉 | 用“感知–决策”框架讨论退化检测触发的策略切换与融合 |
<!-- caption: 第 3.5 节代表性“可复现设置 + 定量结果”汇总（覆盖本节正文出现的全部引用；仅摘录原文或原文综述中口径清晰的报数）。 -->
<!-- label: tab:degeneracy-data -->

**退化检测 vs 算法自适应**的边界正在模糊：GenZ-ICP 和 LP-ICP 展示了通过丰富度量本身（而非显式检测-处理分离）来"内生性"抵抗退化的可行性，未来方向是将退化感知能力嵌入 ICP 的每一次迭代，使其对几何结构的变化自动响应，无需外部触发。
