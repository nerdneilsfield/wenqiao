## 3.3 收敛加速与迭代优化 (Convergence Acceleration and Iterative Optimization)
<!-- label: sec:convergence -->

标准 ICP 属于交替优化的不动点迭代：每一步都以当前估计为线性化中心，重复“建立对应 → 更新位姿”。在噪声、弱约束或收敛方向不均衡的情况下，该迭代可能表现为收敛缓慢或轨迹振荡。[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001) 指出许多工程技巧（采样、层次化、终止准则）本质上都在改变“每步更新的有效信息量”。本节从五个维度系统梳理收敛加速方法：（1）Anderson 外推（历史信息复用）；（2）Majorization-Minimization（MM）与渐进非凸（GNC）下的鲁棒加速；（3）速度/运动先验提供更好的初值；（4）多分辨率策略重塑目标函数景观；（5）自适应终止准则。

如果只看“算一次对应再解一次刚体”的形式，ICP 的每步更新并不昂贵；真正拖慢收敛的常见原因有两类：一类是方向不对（在错误盆地边缘反复横跳），另一类是信息密度不够（每一步吃进去的几何约束太弱）。[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001) 的实验设置很直观：在约 $10^5$ 点规模的网格上，每轮只抽 $2000$ 个点（约 $1\\%$）做更新；在 550 MHz Pentium III Xeon 上，假设初值已在正确盆地内，两幅 range image 的对齐可以压到“几十毫秒”量级。把这些数字放进综述不是为了炫技，而是在提醒我们：迭代次数、每步代价、以及“每步到底有多少有效约束”，三者常常要一起看。

![ICP 收敛加速策略路径与迭代次数对比](../images/ch3-convergence-overview.png)
<!-- caption: ICP 收敛加速策略对比（示意）。左：目标函数等高线图上，标准 ICP（灰色虚线）的锯齿状路径 vs. Anderson 外推（蓝色）的平滑路径 vs. 多分辨率 ICP（橙色）的由粗到精路径。右：不同策略在“迭代步数/每步代价/稳定性”之间的定性权衡：历史外推减少步数、鲁棒 MM 降低外点主导风险、多分辨率扩大可收敛区域但引入多层开销。 -->
<!-- label: fig:convergence-overview -->
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
  Two-panel academic comparison figure for ICP convergence acceleration methods.
  Left panel: 2D contour plot of a bowl-shaped loss landscape. Show three optimization paths:
  - Grey dashed zigzag path labeled "标准 ICP"，many small steps
  - Blue smooth curved path labeled "Anderson 外推"，fewer larger steps
  - Orange coarse-to-fine path labeled "多分辨率"，first reach basin then refine
  Axes labeled "平移 tx" and "旋转 θ", contour lines in light grey, minimum marked with star.
  Right panel: compact qualitative comparison chart (not numeric) showing trade-offs:
  rows are methods in Chinese, columns are "迭代步数", "每步代价", "外点稳定性", "对初值敏感性".
  Use small filled circles (●/○) or 3-level bars to indicate low/medium/high qualitatively.
  All chart text must be Chinese only.
  White background, clean publication style, consistent color scheme.
-->

### 3.3.1 ICP 作为不动点迭代：加速的统一视角

ICP 的每次迭代本质上是一个不动点更新。设位姿参数向量 $\boldsymbol{\xi}^{(k)} \in se(3)$（李代数六维向量），"对应建立 + 变换估计"的复合映射记为 $G$，则

$$
\boldsymbol{\xi}^{(k+1)} = G\!\left(\boldsymbol{\xi}^{(k)}\right)
$$
<!-- label: eq:fixed-point -->

标准 ICP 相当于 Picard 迭代——每步只利用 $G(\boldsymbol{\xi}^{(k)})$。其收敛速率（线性收敛）由 $G$ 的 Lipschitz 常数 $\kappa = \|G'\| < 1$ 决定：每次迭代误差以 $\kappa$ 倍递减。当 $\kappa$ 接近 1 时（如旋转分量收敛慢，平移分量收敛快的不平衡场景），需要大量迭代。Picard 迭代的低效正是因为它在每次更新时"忘记"了历史方向信息。Anderson 加速和 Majorization-Minimization（MM）框架分别从"外推利用历史"和"最优化更紧代理函数"两条路径解决这一问题。

这里最好再分清两种“慢”。一种是已经在正确盆地里，但每步都只走很短的局部修正，轨迹像锯齿一样来回磨；另一种是每一步虽然也在下降，却总被外点、差初值或尺度层次稀释掉有效信息，导致下降幅度始终不大。AA 主要对付前一种，MM/鲁棒核和多分辨率更多是在缓解后一种。把这两类慢混在一起讨论，很容易把“省了几步”和“更不容易失败”写成同一回事。

### 3.3.2 Anderson 加速：AA-ICP

Anderson 加速（Anderson Acceleration，AA）最早由 [Anderson](cite:andersonIterativeProceduresNonlinear1965) 在不动点迭代的语境里提出。它的门槛很低：不需要梯度，只要能算 $G(u)$，就能记住最近 $m$ 步残差，解一个带 $\\mathbf{1}^\\top\\alpha=1$ 约束的小规模最小二乘，把多个历史方向揉成一次外推步。放在 ICP 里，这个思路几乎是“无侵入式”的：对应搜索、位姿估计都不用动，外层把 Picard 的 $\\boldsymbol{\\xi}^{(k+1)}\\leftarrow G(\\boldsymbol{\\xi}^{(k)})$ 换成“带历史的更新”就行 [Pavlov et al.](cite:pavlovAAICPIterativeClosest2017)。

[Pavlov et al.](cite:pavlovAAICPIterativeClosest2017) 的实验把关键细节交代得比较清楚：在 TUM RGB-D Benchmark 的 Freiburg1 子集里，他们只用深度点云做 scan matching，把“帧间匹配”改成“隔 5 帧匹配”来模拟关键帧，总共处理了 2738 对扫描；在 Stanford Bunny（bun000 与 bun045）上，每帧约 4 万点，随机施加旋转/平移扰动做了 1000 次测试。参数上，收敛阈值取 $\\varepsilon=0.001$，最大迭代数 100，并限制外推系数（$|\\alpha_j|\\le 10$ 且 $\\alpha_0>0$）来降低“外推把自己拽出盆地”的概率。对应到结果，论文报告中位数加速约 $35\\%$（平均约 $30\\%$），并且在约 $97\\%$ 的 case 里最终误差更小（中位数改善约 $0.3\\%$）[Pavlov et al.](cite:pavlovAAICPIterativeClosest2017)。

顺带说一句，这个 benchmark 本身的“量级”也值得记住：原始序列一共有 39 段，Kinect 的 RGB-D 数据是 640×480、30 Hz，动捕系统用 8 台高速相机给 100 Hz 的真值轨迹；除了手持序列，也有 Pioneer 3 机器人挂载 Kinect 的轨迹 [Sturm et al.](cite:sturmBenchmarkEvaluationRGBD2012)。因此 AA-ICP 在这个数据上加速的，主要是“室内、连续帧、初值不算太离谱”的那一类匹配。

设历史残差矩阵 $F_k = [f_{k-m+1},\\ldots,f_k]$，$f_j = G(\\boldsymbol{\\xi}^{(j)}) - \\boldsymbol{\\xi}^{(j)}$，AA 求解

$$
\min_{\boldsymbol{\alpha}} \|F_k \boldsymbol{\alpha}\|_2^2 \quad \text{s.t.} \quad \mathbf{1}^\top\boldsymbol{\alpha} = 1
$$
<!-- label: eq:anderson-ls -->

然后以加权组合外推新位姿：

$$
\boldsymbol{\xi}^{(k+1)} = \sum_{j=0}^{m} \alpha_j^{(k)}\, G\!\left(\boldsymbol{\xi}^{(k-j)}\right)
$$
<!-- label: eq:anderson -->

[Pavlov et al.](cite:pavlovAAICPIterativeClosest2017) 的实现方式很“外层封装”：内部仍是你熟悉的 ICP（找对应、解位姿、算残差），外层只在更新环节插入一次外推。AA 额外付出的主要是维护长度为 $m$ 的历史，以及每轮解一次规模随 $m$ 线性增长的小最小二乘；真正需要下功夫的是稳住外推：他们在误差恶化时回退到标准 Picard 步，并在出现“盆地切换”迹象时重置历史窗口，以避免一次外推把轨迹拉跑。

AA 的几何直觉可以说得再实一点：如果最近几步更新方向高度相关，说明 Picard 迭代正在重复做“方向差不多、幅度偏小”的修补。AA 不是再走一步同类小步，而是直接解一个系数组合，让这些历史残差在当前点附近尽量相互抵消，从而估计出一条更像 secant 步的外推方向。于是它最擅长的是“已经进了盆地，但走得太磨”的情况；若历史方向本身就被假极小值污染，外推反而会把错误放大，这也是论文里必须设置回退与重置机制的原因。

![Anderson 加速机制详解](../images/ch3-anderson-mechanism.png)
<!-- caption: Anderson 加速在 ICP 迭代中的机制示意。面板（a）给出位姿空间中的迭代轨迹：标准 ICP 往往呈锯齿状，而 AA 通过线性组合最近若干步的更新方向生成外推步，使轨迹更平滑、步数更少。面板（b）示意历史窗口中各步权重系数 $\alpha_j$ 的相对贡献。 -->
<!-- label: fig:anderson-mechanism -->
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
  Two-panel academic vector figure explaining Anderson Acceleration (AA) in ICP.
  Panel (a) title "迭代轨迹":
    2D contour plot of a generic loss landscape (light gray contours).
    Draw a gray zigzag path labeled "标准 ICP" from an initial point to a minimum.
    Highlight the last 4 update directions as small gray arrows labeled "f_{k-3}", "f_{k-2}", "f_{k-1}", "f_k".
    Draw one bold blue extrapolation arrow from the current point toward the minimum, labeled "AA 外推" and annotate "Σ α_j f_{k-j}".
    No numeric axis ticks; axes labeled in Chinese only: x-axis "旋转分量", y-axis "平移分量".
  Panel (b) title "权重系数":
    Bar chart showing relative coefficients "α_k, α_{k-1}, α_{k-2}, α_{k-3}" (no specific values),
    with the most recent bars visually larger (qualitative).
  White background, flat vector style, consistent gray-blue palette, all in-figure text Chinese only.
-->

**稳定性增强**：AA 在外点占优或错误盆地附近进行外推时，更新方向可能被“假极小值”牵引而变差。[Pavlov et al.](cite:pavlovAAICPIterativeClosest2017) 讨论了若干稳定化技巧，例如在外推导致目标值恶化时回退到标准 Picard 步、在收敛盆地发生切换时重置历史窗口等。这类“外推失败时退回”的策略在工程上很常见，能够在保留加速收益的同时降低外推带来的风险。

它的局限也很明确：AA 几乎不改变 ICP 的收敛盆地，更多是在既有盆地里“走得更像样”。如果初值本来就在错盆地，或者对应关系在几轮之间频繁跳变，历史残差就不再代表同一个局部几何结构，外推反而容易失真。换句话说，AA 的前提不是“任何 ICP 都能套”，而是局部迭代已经有相当强的一致性。

### 3.3.3 Majorization-Minimization 框架与 FRICP

[Zhang et al.](cite:zhangFastRobustIterative2022) 将 ICP 从 AA 视角进一步推进：证明经典 P2P ICP 等价于一个 Majorization-Minimization（MM）算法，并基于这一视角同时实现加速与鲁棒化。

**MM 视角**：MM 算法通过最小化目标函数的代理（surrogate）上界来迭代逼近最优解。P2P ICP 最小化

$$
\mathcal{E}(R,t) = \sum_i \|Rp_i + t - \hat{q}_i\|^2
$$
<!-- label: eq:p2p-obj -->

在固定对应 $\hat{q}_i$ 时，这是一个关于 $(R,t)$ 的严格凸二次型（$\Sigma$ 的代理），通过 SVD 一步求解。[Zhang et al.](cite:zhangFastRobustIterative2022) 证明从一步到下一步这个更新就是 MM 步，从而可以直接应用 Anderson 加速于位姿的李代数参数化 $\boldsymbol{\xi} \in se(3)$，避免了欧拉角表示的奇异性问题。

把 ICP 放进 MM 框架后，有个以前容易说虚的点就落地了：固定对应并不是“工程上先凑合一下”，而是等价于在当前点构造了一个更容易优化的代理上界，然后把这个上界精确最小化。这样一来，MM 保证的是“每轮走的都是一条可解释的下降步”，AA 则是在这些合法步之间再去榨历史信息。两者不是重复加速，而是分别在“步是否可靠”和“步是否够大”这两个层面起作用。

**Welsch 函数鲁棒化**：为处理外点，[Zhang et al.](cite:zhangFastRobustIterative2022) 将 $L_2$ 损失替换为 Welsch 函数

$$
\psi_\nu(x) = 1 - \exp\!\left(-\frac{x^2}{2\nu^2}\right)
$$
<!-- label: eq:welsch -->

其中 $\nu$ 为尺度参数。Welsch 函数的性质：当 $x \ll \nu$ 时近似 $L_2$（内点区域）；当 $x \gg \nu$ 时趋于 1（外点区域的饱和损失），效果等同于给予外点接近零的权重。在 MM 框架下，Welsch 函数对应的迭代加权方案为

$$
\omega_i^{(k)} = \exp\!\left(-\frac{\|d_i^{(k)}\|^2}{2\nu^2}\right), \quad d_i^{(k)} = Rp_i + t - \hat{q}_i
$$
<!-- label: eq:welsch-weight -->

权重自适应地降低外点的贡献，同时对内点保留全权重，无需手动设置截断阈值。整个框架（MM + Anderson 加速 + Welsch 权重）即 FRICP（Fast Robust ICP），其设计目标是在保持鲁棒性的同时尽量把每步更新维持为“加权最小二乘 + 高效位姿更新”的形式，从而在工程实现上更易获得较高效率 [Zhang et al.](cite:zhangFastRobustIterative2022)。

这也是 FRICP 和 Sparse ICP 的关键分野。Sparse ICP 把“外点应当稀疏出现”更强地写进目标函数，因此鲁棒性很硬，但求解器也随之变重；FRICP 则有意选了 Welsch 这类还能落回 MM/加权最小二乘结构的鲁棒核，不追求最激进的稀疏建模，而是尽量保住每轮更新的轻量结构。换句话说，FRICP 加速的不是某个单独模块，而是尽量不让“鲁棒化”把整个迭代链条拖重。

FRICP 的“快”并不是靠把停止条件放松出来的。[Zhang et al.](cite:zhangFastRobustIterative2022) 明确写了对比设置：ICP、ICP-l 与 AA-ICP 统一使用同一套终止准则（最大迭代数 1000，或相邻两次变换差满足 $\\|\\Delta T\\|_F<10^{-5}$，$\\Delta T$ 为两次迭代变换之差）；Sparse ICP 在 RGB-D SLAM 数据上取 $p=0.8$、其余实验取 $p=0.4$（Sparse ICP-l 全部取 $p=0.4$）。在这套规则下，他们给出的时间单位是秒，误差用平均/中位 RMSE（表头注明 $\\times 10^{-3}$）。

更关键的是数字本身。以 RGB-D SLAM 那组表为例（8 个序列），标准 ICP 的单对点云耗时大致在 0.23–0.93 s；AA-ICP 往往能压到 0.16–0.59 s；Fast ICP（非鲁棒版本）进一步到 0.14–0.43 s，并且这三者的 RMSE 基本维持在同一量级（例如 `fr1/xyz` 的 RMSE 都是 2.1/0.89 左右）[Zhang et al.](cite:zhangFastRobustIterative2022)。鲁棒这边差别就更明显：同一张表里，Ours (Robust ICP) 在 `fr1/xyz` 上用 0.60 s 把 RMSE 做到 0.5/0.43，而 Sparse ICP 则是 11.2 s（RMSE 1.6/0.86）。在“部分重叠”的合成测试里，Bimba 一组更夸张：Sparse ICP 约 37.90 s，而 Ours (Robust ICP) 约 0.96 s、RMSE 0.87/0.67；标准 ICP 虽然更快（0.33 s），RMSE 却停在 68/60 这个量级 [Zhang et al.](cite:zhangFastRobustIterative2022)。这几组数字基本把 FRICP 的位置讲透了：它愿意多花一点计算，把优化轨迹从“被外点拽着走”拉回到“内点在主导”。

**Sparse ICP 对比**：[Bouaziz et al.](cite:bouazizSparseIterativeClosest2013) 把外点“稀疏化”进目标函数：用 $\\ell_p$（$p<1$）去惩罚残差，并用 ADMM 做变量分裂求解。它确实能把大残差压下去，而且论文里给的数字非常有说服力：在 Owl 的虚拟扫描实验中，初始误差 $e=4.0\\times 10^{-1}$，把 $p$ 往小推到 0.4 后能把误差压到 $4.8\\times 10^{-4}$；即便用 $p=1$，也能到 $1.6\\times 10^{-2}$ 的量级（另外，剪枝阈值 $d_{th}$ 用 bbox 对角线的百分比来设，$d_{th}=10\\%$ 时 $p=2$ 的误差约 $2.9\\times 10^{-2}$）[Bouaziz et al.](cite:bouazizSparseIterativeClosest2013)。代价同样是“写在算法结构里”的：每轮不再是一个小的刚体闭式解，而要维护一套近端/乘子更新；因此在大规模点云上，时间往往被求解器吃掉，运行效率更依赖实现细节与超参。[Zhang et al.](cite:zhangFastRobustIterative2022) 的 FRICP 用 Welsch 核得到类似的“抑制大残差”效果，但在 MM 框架下每步仍保持为加权最小二乘，更容易做出一个速度-鲁棒性都不难看的折中。

FRICP 自己也不是没有代价。它依赖鲁棒核尺度和退火/更新策略把“哪些点该被快速降权”处理得足够稳；若场景里内点本身就很少，或者对应几乎全被错误初值带偏，Welsch 权重也只能在局部框架内做修补，不能替代真正的全局初始化。

![MM 代理函数与 Welsch 鲁棒核详解](../images/ch3-mm-welsch.png)
<!-- caption: MM 代理函数与鲁棒核的机制示意。（a）MM 以“易优化的代理函数”上界原目标，在当前点处相切并逐步更新，使目标值单调下降；（b）多步迭代中代理函数逐渐逼近原目标的局部极小；（c）不同鲁棒核对应的权重函数 $w(r)=\\rho'(r)/(2r)$：残差越大，权重越小，对应对优化的有效贡献被抑制；（d）以残差分布为背景可视化权重对“内点区/外点区”的区分作用（示意）。 -->
<!-- label: fig:mm-welsch -->
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
  Four-panel academic vector figure, white background, flat style, all in-figure text Chinese only.
  Panel (a) title "MM 代理函数":
    Plot a non-convex black curve "目标函数 E(ξ)" and a blue dashed parabola "代理函数 Q(ξ|ξ^(k))" touching at "ξ^(k)".
    Mark the surrogate minimizer "ξ^(k+1)" with a green dot and a downward arrow "单调下降".
  Panel (b) title "迭代更新":
    Show 3 successive surrogate parabolas (different colors) and their minimizers moving toward a local minimum on the black curve.
  Panel (c) title "权重函数 w(r)":
    Plot weight curves for "L2", "Huber", "Geman-McClure", "Welsch" (qualitative shapes, no numeric ticks).
    Axis labels: x-axis "残差幅值 r", y-axis "权重 w(r)".
    Shade two regions labeled "内点区" and "外点区".
  Panel (d) title "权重作用示意":
    Draw a 1D residual histogram (gray bars) and overlay one chosen weight curve (e.g., Welsch, red),
    visually showing that large residuals are down-weighted.
  Consistent color palette, thin gridlines, publication-quality typography.
-->

### 3.3.4 速度预测初始化：VICP

在连续扫描序列中（如 LiDAR 里程计），相邻帧之间的位姿变化可以用前帧的运动速度外推预测。VICP（Velocity ICP）沿这一思路显式估计传感器速度，并用速度更新来补偿扫描畸变与累积误差 [Hong et al.](cite:hongVICPVelocityUpdating2010)。若上一帧估计到的角速度和线速度为 $(\boldsymbol{\omega}_k, \boldsymbol{v}_k)$，则下一帧 $k+1$ 的初始位姿估计可写为

$$
T_0^{(k+1)} = \exp\!\left(\hat{\boldsymbol{\omega}}_k \Delta t\right) \cdot T^{(k)} \cdot \exp\!\left(\hat{\boldsymbol{v}}_k \Delta t\right)
$$
<!-- label: eq:vicp -->

其中 $\Delta t$ 为帧间时间间隔，$\hat{(\cdot)}$ 为从 $\mathbb{R}^3$ 到 $so(3)$ 或 $se(3)$ 的 hat 映射。速度预测的意义在于：把“完全未知的初值”替换为“由短时运动连续性外推得到的初值”，从而更频繁地把 ICP 送入正确的收敛盆地，减少无效迭代与发散风险。

所以 VICP 解决的其实不是“盆地里怎么走得更快”，而是“能不能先掉进对的盆地”。这一点和 AA、FRICP 是互补关系而不是替代关系：后两者默认你已经离可收敛区域不太远，重点是别在局部阶段浪费步数；VICP 则先用运动连续性把初值拉近，否则后面的局部加速根本没有用武之地。

**适用场景**：VICP 更适合帧率较高、运动相对连续的序列配准（如里程计/建图前端）。当出现急转弯、加减速或点云畸变明显时，纯速度外推可能产生较大初值偏差，通常需要与 IMU 预积分或其他先验联合使用。典型 SLAM 系统如 FAST-LIO2 [Xu et al.](cite:xuFASTLIO2FastDirect2022) 便以 IMU 约束提供更可靠的初值，本质上属于“用运动先验缩小 ICP 搜索范围”的思路。

因此它的局限几乎都来自运动模型本身：一旦平台发生急剧机动、打滑、碰撞、或者时间同步与畸变补偿做得不好，速度先验就可能系统性地把初值推错。对于低帧率、弱连续性的配准任务，这类方法的收益也会明显下降。

VICP 的论文里给了一个很硬的对照：他们用 Hokuyo URG-04LX（扫描周期 100 ms/scan）在 $7.2\\,\\text{m}\\times 7.8\\,\\text{m}$ 的室内环境跑了 4 组轨迹，其中两组是更快的运动（平均速度约 $2.7\\,\\text{m/s}$，另外两组约 $1.2\\,\\text{m/s}$）。用累计漂移误差对比，标准 ICP 在 Experiment 1/2 的旋转漂移分别达到 $58.14^{\\circ}$ 和 $79.98^{\\circ}$、平移漂移分别是 2191 mm 和 2014 mm；VICP 则降到 $7.28^{\\circ}$/$17.06^{\\circ}$ 与 177 mm/65 mm。即便在相对温和的 Experiment 3/4，VICP 也把旋转漂移从 $16.80^{\\circ}$/$54.59^{\\circ}$ 降到 $6.88^{\\circ}$/$3.28^{\\circ}$（平移漂移 1490/2942 mm 降到 408/210 mm）[Hong et al.](cite:hongVICPVelocityUpdating2010)。这组数字基本说明：当扫描本身被运动拉“歪”了，单纯靠更快的局部求解器去加速 ICP 意义不大，先把畸变补回去，才谈得上收敛速度。

FAST-LIO2 属于“IMU 把初值兜住”的路线：它在 19 个公开序列的基准对比里报告自己在 17 个序列上精度最好，并把里程计与建图频率做到最高可达 100 Hz；论文还专门点名了两类极端设置：杂乱室内、旋转速度可到 1000 deg/s，以及最高 7 m/s 的高速运动 [Xu et al.](cite:xuFASTLIO2FastDirect2022)。放在这里的意义很简单：速度/运动先验首先是为了把起点拉进“能收敛的区域”，其次才是为了少迭代几步。

**连续时间 ICP**：更进一步，连续时间运动模型（Continuous-Time ICP，CT-ICP）以时间连续轨迹来建模扫描内运动，并在配准过程中对扫描畸变进行补偿，是速度预测思想的时间连续延伸。[Dellenbach et al.](cite:dellenbachCTICPRealtimeElastic2022) 将其用于实时 LiDAR 里程计，并在 KITTI odometry leaderboard 上报告平均相对平移误差（RTE）为 $0.59\\%$；同时给出单线程 CPU 上平均 $60\\,\\text{ms}$/scan 的运行时间。

另外两条“实现层面的数字”也很有参考价值：为了保证前端节奏，CT-ICP 在实时模式下通常把单帧优化迭代上限压到 5 次；闭环部分则单独计时（高度图匹配平均约 1.1 s、位姿图优化约 1.2 s），这样就不会把后端的不确定性拖到前端里程计的时间预算里 [Dellenbach et al.](cite:dellenbachCTICPRealtimeElastic2022)。

### 3.3.5 多分辨率策略：扩大收敛盆地

**核心思想**："先粗后精"。在分辨率较低（点云大幅降采样）的层级上 ICP 的目标函数更平滑——局部极小值被模糊掉，收敛盆地更宽；一旦在粗层找到近似正确的位姿，在精层恢复细节精度。标准三层金字塔设计为

$$
T^* = \text{ICP}_{r_0}\!\left(\text{ICP}_{r_1}\!\left(\text{ICP}_{r_2}\!\left(T_0,\,\mathcal{P}_{r_2},\mathcal{Q}_{r_2}\right),\,\mathcal{P}_{r_1},\mathcal{Q}_{r_1}\right),\,\mathcal{P}_{r_0},\mathcal{Q}_{r_0}\right)
$$
<!-- label: eq:multires -->

其中 $r_0 < r_1 < r_2$ 为点云分辨率（$r_2$ 最粗，$r_0$ 最细）。每层传入下层的是上层收敛的位姿估计，不是随机初始化。[Magnusson](cite:magnussonThreeDimensionalNormalDistributions2009) 在三维 NDT 框架中展示，多分辨率策略能够显著提高对较大初始误差的容忍，从而更稳健地把优化推进到可精修的盆地内。

如果要把“容忍更大的初值”说得更具体一点，[Magnusson](cite:magnussonThreeDimensionalNormalDistributions2009) 在其 3D-NDT 的评估里给了一个相对明确的量级：引入多分辨率离散化与三线性插值后，算法在初始平移误差到 0.5 m、初始旋转误差到 0.2 rad 的设置下仍能更稳定地收敛；而与 ICP 的对比实验也显示，3D-NDT 在差初值场景下往往更不容易被“卡死”。这里并不是说多分辨率能替代全局初始化，而是它确实能把局部优化的可收敛区域往外推一圈。

**层数与降采样比的设计**：工程上常用少量层级（例如三层）即可取得明显收益：粗层负责抹平局部极小并快速进入正确盆地，细层负责恢复细节精度。体素质心降采样（第 4.2 节）常用作粗层的默认选择，以在显著降低点数的同时保留整体几何；法向空间降采样（NSS）可在精层优先保留几何变化丰富区域，从而提升精修阶段的有效约束。

多分辨率真正省下来的，也不只是“粗层点少，所以每轮更便宜”。更重要的是粗层先把高频几何细节压掉，使目标函数的局部起伏少很多，很多原本会把局部优化绊住的假极小先消失了；等位姿已经被送到一个靠谱区域，再把细节逐层放回来做精修。也正因为如此，多分辨率常常同时提升成功率和总收敛效率，而不只是减少单轮算量。

**与 AA 的正交叠加**：多分辨率策略与 Anderson 加速在作用机理上基本正交——粗层主要负责把初始误差压入可收敛盆地，AA 则在盆地内减少迭代步数。工程上常见的做法是在粗层/中层完成“入盆地”，再在精层启用 AA 或鲁棒核来加快收敛；其代价主要来自多层表示与一次小规模最小二乘外推的维护开销 [Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001)，[Pavlov et al.](cite:pavlovAAICPIterativeClosest2017)。

多分辨率的局限则在于，粗层一旦把关键几何也一并抹掉，优化虽然“更平滑”，却可能失去区分真解与假解所需的约束。层级设计过粗时尤其如此：你以为自己扩大了盆地，实际可能只是把不同候选解都压成了差不多的样子。它更适合作为“局部优化的前置缓冲层”，而不是独立承担全局搜索职责。

![多分辨率 ICP 三层金字塔结构详解](../images/ch3-multires-pyramid.png)
<!-- caption: 多分辨率 ICP 的三层金字塔与“先粗后精”的作用机理示意。左列：点云从粗到细的三层表示；中列：对应层级下的代价景观，粗层更平滑、局部极小被弱化，细层细节丰富但局部极小更多；右列：级联流程，粗层负责进入正确盆地，细层负责精修到高精度。 -->
<!-- label: fig:multires-pyramid -->
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
  Three-column academic vector diagram explaining multi-resolution ICP (coarse-to-fine).
  White background, flat style, all in-figure text Chinese only.
  Left column (3 stacked rows) titled "点云金字塔":
    show the same scene with three densities: coarse (blue, sparse), mid (green), fine (orange, dense).
    Label rows "粗层", "中层", "精层" with arrows between rows labeled "传递位姿".
  Middle column (3 stacked rows) titled "代价景观":
    for each level, show a contour plot: coarse = smooth with one wide basin; fine = more local minima.
    Mark an initial point and a convergence path; mark false minima with red X in the fine level.
  Right column titled "级联流程":
    flowchart "粗层对齐 → 中层细化 → 精层精修", with a side note "无金字塔：更易陷入局部极小" (schematic, no numbers).
  Consistent blue/green/orange palette, thin lines, clear spacing and margins.
-->

### 3.3.6 自适应终止准则

ICP 的终止准则直接影响精度与计算时间的平衡。标准 ICP 实现通常同时采用以下三类准则，任意一个触发即停止：

**变换增量准则**：

$$
\|\Delta R\|_F < \epsilon_R \quad \text{且} \quad \|\Delta t\|_2 < \epsilon_t
$$
<!-- label: eq:stop-transform -->

当相邻两次迭代的位姿变化量同时低于阈值时停止。阈值应结合点云尺度与噪声水平设置，以避免过早停止或无谓迭代。

**残差相对改善准则**：

$$
\frac{\left|\mathcal{E}^{(k)} - \mathcal{E}^{(k-1)}\right|}{\mathcal{E}^{(k)}} < \delta
$$
<!-- label: eq:stop-residual -->

残差相对下降量低于阈值时停止。这一准则能检测"平台期"：残差已不再改善但仍未触发变换增量准则的情况。

**最大迭代次数**：$k > k_{\max}$。硬截断保证最坏情形下运行时间有界，是实时系统的必要安全阀。

**自适应 $k_{\max}$**：进一步地，可根据残差改善趋势动态调整 $k_{\max}$：当连续多步改善极小或呈震荡时更早终止；当改善趋势稳定且仍显著时允许额外迭代以换取更低残差。阈值应结合点云尺度、噪声水平与实时性预算设置，避免把“参数默认值”误当作跨场景通用规律。

终止准则之所以应该放在“收敛加速”里，而不是当成实现细节带过去，就是因为很多所谓加速其实都可能被停止条件污染。一个方法如果只是更早停，并不能说明它真的更会收敛；反过来，如果在统一的停止口径下仍然更快，那这个加速才有比较意义。AA-ICP 和 FRICP 的实验都专门把这件事交代清楚，因此它们的加速比才值得拿来写进综述。

当然，终止准则本身也有局限。变换增量阈值在退化场景里可能过于乐观，因为“几乎不动了”未必代表“已经对齐了”；残差改善阈值又可能在重尾噪声下过早进入平台期。真正稳妥的做法通常不是依赖某一条单一准则，而是把变换、残差和最大迭代数一起看，并让阈值跟点云尺度和实时预算绑定。

写综述时，终止准则这类“看起来很细碎”的数字反而最能防止误读。AA-ICP 的实验直接给了收敛阈值 $\\varepsilon=0.001$、最大迭代数 100，以及外推系数限制 $\\alpha_l=10$ [Pavlov et al.](cite:pavlovAAICPIterativeClosest2017)。FRICP 的对比更“较真”：为了不让“谁先停谁更快”搅乱结论，作者把 ICP / ICP-l / AA-ICP 的停止条件统一成 max iters=1000 或 $\\|\\Delta T\\|_F<10^{-5}$ [Zhang et al.](cite:zhangFastRobustIterative2022)。这些数字放在这里，是为了让读者知道：你看到的加速比不是靠松动终止条件堆出来的。

### 3.3.7 收敛加速方法综合对比

| 方法 | 加速来源 | 初值容忍 | 外点稳定性 | 额外开销 | 更适合的使用方式 |
|------|----------|----------|------------|----------|------------------|
| 标准 ICP | — | 低 | 低 | 低 | 有可靠初值、低噪声场景的局部精修 |
| AA-ICP | 历史外推 | 低 | 中 | 低（历史缓存 + 小规模最小二乘） | 在同一盆地内的快速收敛 [Pavlov et al.](cite:pavlovAAICPIterativeClosest2017) |
| FRICP | 鲁棒 MM/GNC + 外推 | 中 | 高 | 中（权重更新 + 外推） | 含外点/噪声的稳定精修 [Zhang et al.](cite:zhangFastRobustIterative2022) |
| Sparse ICP | 稀疏惩罚 | 低 | 高 | 高（ADMM/近端迭代） | 离线或小规模的强鲁棒配准 [Bouaziz et al.](cite:bouazizSparseIterativeClosest2013) |
| VICP [Hong et al.](cite:hongVICPVelocityUpdating2010) | 运动先验提供初值 | 中 | 中 | 低 | 连续帧里程计/建图前端（与 IMU/里程计结合） |
| 多分辨率 | 粗层入盆地 + 细层精修 | 高 | 中 | 中（多层表示与多次求解） | 大初始误差或局部极小丰富的场景 [Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001) |
| 组合策略 | 先入盆地再加速 | 高 | 高 | 中—高 | 全局初始化/多分辨率/鲁棒核/AA 的按需组合 |
<!-- caption: 第 3.3 节收敛加速方法对比（定性）：加速来源、初值容忍、外点稳定性、额外开销与典型使用方式。 -->
<!-- label: tab:convergence-comparison -->

| 引用 | 任务/数据 | 指标 | 关键数字（设置/结果） |
|------|----------|------|------------------------|
| [Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001) | 合成网格（约 $10^5$ 点） | 采样与时间 | 每轮采样 $2000$ 点（约 $1\\%$）；550 MHz PIII Xeon；对齐耗时“几十毫秒”（初值良好时） |
| [Anderson](cite:andersonIterativeProceduresNonlinear1965) | 不动点迭代（方法本身） | 计算规模 | 历史长度为 $m$；每轮解一个 $m{+}1$ 维系数的约束最小二乘（额外开销主要在小规模线性代数） |
| [Pavlov et al.](cite:pavlovAAICPIterativeClosest2017) | TUM RGB-D（Freiburg1）+ Bunny | 加速比/设置 | 2738 对扫描；隔 5 帧匹配；Bunny 每帧约 4 万点、1000 次扰动；$\\varepsilon=0.001$、$\\alpha_l=10$、max iters=100；中位数加速约 $35\\%$、误差中位数改善约 $0.3\\%$ |
| [Sturm et al.](cite:sturmBenchmarkEvaluationRGBD2012) | TUM RGB-D Benchmark | 数据规模/频率 | 39 个序列；Kinect 640×480@30 Hz；动捕 8 相机给 100 Hz 真值轨迹；含手持与 Pioneer 3 载体 |
| [Zhang et al.](cite:zhangFastRobustIterative2022) | RGB-D SLAM + 部分重叠模型 | 时间/RMSE/停止条件 | 停止条件统一：max iters=1000 或 $\\|\\Delta T\\|_F<10^{-5}$；例如 `fr1/xyz`：ICP 0.23 s、AA-ICP 0.16 s、Robust ICP 0.60 s，RMSE 分别约 2.1/0.89 与 0.5/0.43（表头注明 $\\times 10^{-3}$） |
| [Bouaziz et al.](cite:bouazizSparseIterativeClosest2013) | Sparse ICP（Owl 虚拟扫描） | 误差 | 初始 $e=4.0\\times 10^{-1}$；$p=0.4$ 后 $e=4.8\\times 10^{-4}$；$p=1$ 时 $e=1.6\\times 10^{-2}$；$d_{th}$ 以 bbox 对角线百分比计（如 10%） |
| [Hong et al.](cite:hongVICPVelocityUpdating2010) | 2D 激光里程计 | 漂移误差 | URG-04LX：100 ms/scan；Exp1：ICP 58.14°/2191 mm vs VICP 7.28°/177 mm；Exp2：79.98°/2014 mm vs 17.06°/65 mm；快运动均速约 2.7 m/s |
| [Xu et al.](cite:xuFASTLIO2FastDirect2022) | LiDAR-IMU 里程计 | 频率/极端动态 | 19 个序列基准；17 个序列精度最好；最高 100 Hz；旋转可到 1000 deg/s；最高 7 m/s 运动 |
| [Dellenbach et al.](cite:dellenbachCTICPRealtimeElastic2022) | LiDAR-only SLAM | RTE/时间预算 | KITTI leaderboard：RTE 0.59%；60 ms/scan（单线程）；实时模式迭代上限常设 5；闭环匹配约 1.1 s、图优化约 1.2 s |
| [Magnusson](cite:magnussonThreeDimensionalNormalDistributions2009) | 3D-NDT 多分辨率注册 | 初值容忍 | 报告多分辨率+三线性插值后，对初始平移 0.5 m、初始旋转 0.2 rad 的鲁棒性显著提升 |
<!-- caption: 第 3.3 节引用数据汇总（覆盖本节全部引用）。表中数字用于把“加速/更鲁棒”落到可复现实验设置上。 -->
<!-- label: tab:convergence-data -->

### 3.3.8 收敛速度的根本限制

值得指出，上述方法主要加速的是“已在盆地内”的局部收敛速率，而**不直接扩大收敛盆地本身**。Anderson 加速和 MM 框架仍属于局部策略：若初始位姿处于错误盆地，外推反而可能放大偏离。多分辨率策略通过粗层平滑目标函数景观，能在一定程度上提升对初始误差的容忍，但仍不构成全局最优保证。真正意义上的全局初始化与可认证求解见[第 3.6 节](ref:sec:global-init)（如 Go-ICP、TEASER++ 等），其作用是先将误差压入可收敛区域，再由多分辨率加局部加速在精层快速收敛。第 4 章将进一步讨论软件层面的优化（如批处理近邻查询、并行化线性代数）如何降低每次迭代的绝对时间开销。
