## 3.2 外点处理与鲁棒性 (Outlier Handling & Robustness)
<!-- label: sec:outlier -->

外点（outlier）是点云配准中最常见的干扰来源：它们可能来自传感器噪声与遮挡、两帧之间的非重叠区域、动态目标（行人/车辆），或由几何重复导致的错误对应。在标准 ICP 的最小二乘目标中，少量大残差就可能主导梯度方向，使优化偏离正确解并落入错误的局部极小值。本节按“外点如何被识别与抑制”的机制梳理六类代表性鲁棒化方案，从截断估计与连续降权，到引入物理先验与图论一致性剪枝。

![外点处理方案概览](../images/ch3-outlier-overview.png)
<!-- caption: 六类外点处理策略概览示意。（a）TrICP：截断距离最大的对应；（b）M-估计量：对大残差连续降权；（c）互熵：以核函数隐式抑制离群残差；（d）DICP：引入多普勒先验剔除动态点；（e）RANSAC+ICP：先粗假设筛内点再局部精修；（f）SUCOFT：在兼容性图上保留一致性强的对应子集。 -->
<!-- label: fig:outlier-overview -->
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
  Academic six-panel horizontal diagram showing six outlier handling strategies for ICP registration.
  Panel (a) "TrICP": scatter plot of paired correspondences, show kept pairs in green and trimmed pairs
  in faded red, label "按距离排序后截断 (Trimming)".
  Panel (b) "M-Estimator": weight function curves comparing Huber (blue), Tukey (red), L2 (grey dashed)
  vs residual magnitude on x-axis; label "M-估计量".
  Panel (c) "Correntropy": Gaussian kernel shape overlaid on residual distribution, showing implicit
  downweighting of large errors; label "互熵 (Correntropy)".
  Panel (d) "DICP": 3D LiDAR scan with moving car highlighted and pruned out via Doppler velocity check;
  label "多普勒筛滤".
  Panel (e) "RANSAC+ICP": flowchart showing RANSAC hypothesis generation → inlier consensus →
  ICP refinement; label "RANSAC+ICP".
  Panel (f) "SUCOFT": compatibility graph with nodes and green supercore subgraph highlighted, pruning
  outlier nodes; label "超核心剪枝".
  Clean white background, consistent blue-green-orange color scheme, Chinese labels in quotes,
  academic publication style, 600 dpi.
-->

### 3.2.1 截断 ICP：TrICP

截断迭代最近点算法（Trimmed ICP，TrICP）由 [Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002) 于 2002 年提出，核心思想是将最小截断二乘（Least Trimmed Squares，LTS）估计器系统地应用于 ICP 的各个步骤。给定目标重叠率参数 $\rho \in (0,1]$，算法在每次迭代中仅保留距离最小的 $\lfloor\rho n\rfloor$ 个点对，其目标函数为

$$
\mathcal{E}_\text{TrICP} = \sum_{i=1}^{\lfloor\rho n\rfloor} d_{(i)}^2
$$
<!-- label: eq:tricp -->

其中 $d_{(1)}\leq d_{(2)}\leq\cdots$ 是排序后的点对距离。与标准 ICP 相比，TrICP 在 $\rho=1$ 时退化为原始算法；当 $\rho<1$ 时，被截除的点对不贡献梯度，优化仅利用保留下来的内点对。[Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002) 证明了该算法单调收敛于局部极小值，并在部分重叠、含外点的设置下验证了截断估计对配准稳定性的提升。

从求解过程看，TrICP 改动的其实不是位姿更新器，而是“哪些对应有资格进入更新”。标准 ICP 的一次迭代是“找最近邻 -> 全部送进最小二乘 -> 更新位姿”；TrICP 则在中间多插了一步排序，把残差最大的那一段直接切掉，再用剩下的内点做一次普通刚体配准。也就是说，它把“外点抑制”写成了一个离散选择问题。这样做的好处是物理意义非常直接：如果两帧只有约 70% 真正重叠，那就只让这 70% 左右的点对参与优化；坏处也同样直接：排序边界是硬的，排在边界两侧的两个点对，权重可能从 1 突然跳到 0，这会让目标函数在边界附近不够平滑。

这篇论文给了两组“难度梯度”非常清晰的报数。一组是 3D Frog 数据：两个点集各约 3000 点；作者把标准 ICP 视作 $\rho=1$ 的特例，对比了 ICP（45 次迭代，MSE=5.83，耗时 7 s）与 TrICP（设定重叠率 70%，88 次迭代，MSE=0.10，耗时 2 s）（原文表 1，1.6 GHz PC）[Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002)。另一组是 SQUID 鱼轮廓库的 1100 个 2D 形状：通过控制旋转角（1°/5°/10°/15°/20°）与重叠率（100%→60%）构造部分重叠场景，并用“估计旋转与真值旋转的平均绝对误差（deg）”衡量稳健性。以最难的 20° 旋转、60% 重叠为例，TrICP 的误差为 1.7949°，而 ICRP 为 3.0254°（原文表 2、表 3）[Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002)。这组数据对应的是一个明确边界：当外点主要来自非重叠区域时，TrICP 能把更新重新限制在重叠区域内；但一旦错误对应混入被保留的那一段，硬截断本身并不会再区分“保留下来的内点”和“恰好没被截掉的伪内点”。

TrICP 的参数 $\rho$ 直接对应先验重叠率估计，物理含义清晰；但 $\rho$ 固定意味着截断边界不随迭代动态调整，若重叠区域几何多变，可能在某些帧出现截断过多或截断不足。

### 3.2.2 M-估计量与稀疏 ICP

M-估计量将标准最小二乘目标替换为对大残差施加次二次惩罚的鲁棒核函数，从而隐式地压低外点权重：

$$
\mathcal{E}_\text{robust} = \sum_{i=1}^{n} \rho_M\!\left(\|Rp_i + t - q_{j(i)}\|\right)
$$
<!-- label: eq:mestimator -->

常用核函数包括 Huber 核 $\rho_H(r)=r^2/2$ ($|r|\leq\delta$) 和 Tukey 双权核 $\rho_T(r)=c^2[1-(1-r^2/c^2)^3]/6$ ($|r|\leq c$，否则为常数 $c^2/6$)。Tukey 核对超过截断半径 $c$ 的残差贡献零梯度，等效于完全忽略极端外点；与 TrICP 的硬截断不同，这种忽略是通过梯度逐渐衰减到零实现的。

这一类方法和 TrICP 的根本差别，在于它不再先做“留/不留”的离散决策，而是把每个对应的影响连续地压小。写成迭代形式更直观：若当前残差为 $r_i$，则鲁棒核可以等价改写成加权最小二乘
$$
\mathcal{E}_\text{robust} \approx \sum_i w_i(r_i)\, r_i^2,
$$
其中 $w_i(r_i)=\rho_M'(r_i)/(2r_i)$。残差小的点保留接近 1 的权重，残差大的点逐渐被降权。这样一来，优化器看到的不再是“忽然少了一批点”，而是“每个点都还在，只是有些点的发言权越来越小”。从数值上看，这一过程比 TrICP 更平滑，也更适合和 GN/LM 之类的连续优化器对接；但代价是核函数尺度参数要调，带宽过大就会接近普通最小二乘，过小又会把本来有用的对应一起压掉。

[Zhang et al.](cite:zhangFastRobustIterative2022) 提出的 FRICP（Fast and Robust ICP）系统地将渐进非凸（Graduated Non-Convexity，GNC）框架引入 ICP：从接近凸的目标函数出发，逐步收紧鲁棒核，使优化轨迹更不易被早期外点“带偏”，从而改善部分重叠与外点条件下的配准稳定性。[Zhang et al.](cite:zhangFastRobustIterative2022) 在五组部分重叠模型对（含 Bunny、Dragon 等）上以 Super4PCS 先做粗对齐，并在点集上叠加不同比例的随机外点；以 Bunny 为例，其鲁棒点到点方案的平均/中位 RMSE（×$10^{-3}$）为 0.85/0.69、耗时 0.34 s，而 Sparse ICP 为 0.94/0.71、耗时 24.06 s，误差同量级但运行时间相差约两个数量级[Zhang et al.](cite:zhangFastRobustIterative2022)。

[Bouaziz et al.](cite:bouazizSparseIterativeClosest2013) 从另一角度出发，将配准目标显式改写为 $\ell_p$ 范数（$p\in[0,1]$）最小化问题：

$$
\mathcal{E}_\text{Sparse} = \sum_{i=1}^{n} \|Rp_i + t - q_{j(i)}\|_2^p, \quad p\in[0,1]
$$
<!-- label: eq:sparseicp -->

当 $p\to0$ 时目标趋近于计数内点数，自然获得稀疏性；$p=1$ 退化为 $\ell_1$。求解采用 ADMM（交替方向乘子法），保留了 ICP 交替估计的基本框架 [Bouaziz et al.](cite:bouazizSparseIterativeClosest2013)。

把它和前面的 M-估计量放在一起看，差别就清楚了。M-估计量仍然是在“最小二乘”框架内改权重，目标函数本质上还是光滑优化；Sparse ICP 则更进一步，直接把“希望只有少数对应承担大残差”写进 $\ell_p$ 稀疏惩罚里。尤其当 $p<1$ 时，这个目标已经明显非凸，不再适合简单地靠一次加权更新解决，所以论文转而用 ADMM 把“刚体变换更新”和“稀疏残差更新”拆开求。换句话说，M-估计量是在 LS 框架里做软鲁棒化，Sparse ICP 则是在目标层面把“外点应当稀疏出现”明确编码进去。

[Bouaziz et al.](cite:bouazizSparseIterativeClosest2013) 在“owl”虚拟扫描的对齐实验里把这个思想量化得很直接：他们用相对于真值的 RMSE（记为 $e$）评估配准质量，并对比了“阈值剔除到底该取多大”这一最常见的工程困境。原文图 4 的报数里，粗初值为 $e=4.0\\times 10^{-1}$；传统 $\\ell_2$ ICP（$p=2$）配合距离阈值剔除时，$d_{th}=5\\%$ 仍为 $4.1\\times 10^{-1}$，$d_{th}=10\\%$ 可到 $2.9\\times 10^{-2}$，但 $d_{th}=20\\%$ 又回升到 $7.5\\times 10^{-2}$（$d_{th}$ 以包围盒对角线的百分比定义）；$\\ell_1$（$p=1$）做到 $1.6\\times 10^{-2}$；而 $\\ell_p$（$p=0.4$）进一步降到 $4.8\\times 10^{-4}$[Bouaziz et al.](cite:bouazizSparseIterativeClosest2013)。这一组数字的含义很“工程”：阈值剔除不是不能用，而是太依赖场景尺度与初值质量；稀疏范数把“剔除”变成了连续的自适应降权，省掉了最难调的那根硬阈值。作者还在附录中指出其 shrink 更新通常 2–3 次迭代即可收敛，这也是它能保持可用速度的重要原因之一[Bouaziz et al.](cite:bouazizSparseIterativeClosest2013)。

### 3.2.3 互熵 ICP (Correntropy-based ICP)

互熵（Correntropy）来源于信息论，其定义为

$$
C_\sigma(X,Y) = \mathbb{E}\left[k_\sigma(X-Y)\right] = \frac{1}{n}\sum_{i=1}^n \exp\!\left(-\frac{\|Rp_i+t-q_{j(i)}\|^2}{2\sigma^2}\right)
$$
<!-- label: eq:correntropy -->

其中 $\sigma$ 为高斯核带宽。最大化互熵等价于最小化一个以高斯衰减为权重的加权 $\ell_2$ 损失：残差越大，高斯权重越小，外点贡献随之被自然压低，无需手动设置硬截断阈值[Wu et al.](cite:zhengCorrentropyScaleICP2019)。与 Tukey 核相比，互熵核的权重随残差增大单调下降但不硬截为零，更偏向在统计鲁棒性与数值稳定性之间取折中。

从形状上看，互熵和前面的鲁棒核也不完全一样。Huber 更像“小残差二次、大残差一次”，Tukey 则是在阈值外彻底失声；互熵对应的是高斯型权重，残差一大，影响会指数衰减，但理论上不会在某一点突然变成 0。这种设计特别适合“我怀疑有长尾噪声，但又不想把边缘上的困难内点一刀切掉”的场景。代价是带宽 $\sigma$ 的解释更统计化：它不再只是几何距离阈值，而是在问“多大的偏差还算是同一分布里的正常波动”。

[Wu et al.](cite:zhengCorrentropyScaleICP2019) 在此基础上进一步提出带尺度参数的 SCICP（Scale Correntropy ICP），在相似变换框架下将各向同性缩放因子一并纳入优化，使方法可覆盖“存在尺度偏差”的配准情形（例如跨传感器标定误差或重建尺度漂移）[Wu et al.](cite:zhengCorrentropyScaleICP2019)。

SCICP 的优势主要体现在“外点很脏、又有尺度差”的组合场景里。[Wu et al.](cite:zhengCorrentropyScaleICP2019) 在 2D CE-Shape-1 数据库的 Apple/Pocket/Ray 三组点集上对比了 Scale ICP、CPD 与 SCICP，并分别报告尺度误差 $\\varepsilon_s$、旋转误差 $\\varepsilon_R$ 与平移误差 $\\varepsilon_{\\vec{t}}$：例如 Apple 上，SCICP 的 $\\varepsilon_s=0.0020$、$\\varepsilon_R=9.0351\\times 10^{-4}$、$\\varepsilon_{\\vec{t}}=0.0817$，而 Scale ICP 为 0.0687/0.3031/80.0321，CPD 为 0.1061/0.0889/32.0936（原文表 1）；耗时方面，Apple 上 Scale ICP 为 0.0022 s，SCICP 为 0.0083 s，CPD 为 0.0462 s（原文表 2）[Wu et al.](cite:zhengCorrentropyScaleICP2019)。在 3D 仿真（Happy/Bunny/Dragon）里，SCICP 同样在 $\\varepsilon_s,\\varepsilon_R,\\varepsilon_{\\vec{t}}$ 上整体小于 Scale ICP，例如 Dragon 的 $\\varepsilon_{\\vec{t}}$ 从 0.0196 降到 $6.8352\\times 10^{-5}$（原文表 3）[Wu et al.](cite:zhengCorrentropyScaleICP2019)。这里的关键不是“核函数更复杂”，而是尺度项一旦先被坏对应拉偏，后面的旋转和平移就会跟着偏；互熵核先压低大残差的权重，等于先稳住尺度，再让三者的耦合更新继续进行。

### 3.2.4 Doppler ICP (DICP)

DICP 是针对 FMCW LiDAR 等能够逐点测量瞬时径向速度的传感器设计的 ICP 变体。传统 ICP 在走廊、隧道等几何结构重复的环境中极易产生退化（沿对称轴的平移不可观），因为纯几何目标函数缺乏沿此方向的约束。DICP 引入了多普勒残差项：

$$
\mathcal{E}_\text{DICP} = \underbrace{\sum_i \|Rp_i+t-q_{j(i)}\|^2}_{\text{几何残差}} + \lambda \underbrace{\sum_i \left(v_i - \hat{v}_i(\boldsymbol{\omega},\mathbf{v})\right)^2}_{\text{Doppler残差}}
$$
<!-- label: eq:dicp -->

其中 $v_i$ 为点 $p_i$ 的实测径向速度，$\hat{v}_i$ 为由当前估计的角速度 $\boldsymbol{\omega}$ 和线速度 $\mathbf{v}$ 预测的径向速度，$\lambda$ 为两项的相对权重。多普勒速度从独立的物理量出发约束运动估计，有效打破了退化对称性 [Hexsel et al.](cite:hexselDICPDopplerIterative2022)。

这一节和前面几种方法的思路不一样。TrICP、M-估计量、互熵、本质上都还是“先承认几何残差会被外点污染，再想办法减小污染”；DICP 则直接多引入了一类观测，把“哪些点不该参与几何配准”提前暴露出来。尤其在走廊、隧道这类几何上近似一维可观的场景里，纯几何 ICP 很难分清“我是沿轴向真的动了”还是“只是找到了一组看起来也说得过去的对应”；而多普勒速度给了一个独立于几何形状的运动证据，使这两个解不再同样合理。

DICP 的另一贡献是利用多普勒测量识别动态目标：若某点的测量径向速度与当前运动估计的预测值差异显著，该点很可能来自行驶车辆或行人，算法将其从对应集中剔除。[Hexsel et al.](cite:hexselDICPDopplerIterative2022) 在 Aeva Aeries I FMCW LiDAR 的 5 段真实序列与 CARLA 的 2 段仿真序列上，与 Open3D 的经典 P2Pl ICP 做对比：在 Baker-Barry Tunnel 等“特征贫乏 + 重复结构”场景中，基线 ICP 的平移 RPE 处于米级（>1 m），而 DICP 可降至厘米级（<0.1 m），同时路径误差从 525.35 m 降至 1.23 m；在含大量动态车辆的 Brisbane Lagoon Freeway，基线路径误差高达 4337.18 m，而 DICP 为 4.16 m。作者还报告 Doppler 约束可显著减少迭代次数，例如 Baker-Barry Tunnel 的平均迭代次数由 30.8 次降至 7.6 次（Robin Williams Tunnel：44.3 次降至 13.1 次），体现了“物理量约束 + 动态点剔除”对退化与动态外点的双重抑制[Hexsel et al.](cite:hexselDICPDopplerIterative2022)。

![DICP 的多普勒筛滤机制](../images/ch3-dicp-doppler.png)
<!-- caption: DICP 动态目标筛滤示意。左：原始点云，行驶车辆（红色）的多普勒测速与静态背景（蓝色）明显不同。右：基于多普勒阈值剔除动态点后，仅静态背景参与 ICP 优化，消除了动态污染对配准结果的影响。 -->
<!-- label: fig:dicp-doppler -->
<!-- width: 0.85\textwidth -->
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
  Two-panel academic diagram illustrating DICP (Doppler ICP) dynamic object rejection.
  Left panel "原始点云 (Raw Point Cloud)": 3D LiDAR scan of urban street scene viewed from ego-vehicle.
  Moving cars shown in warm red/orange, labeled "动态点 (Dynamic Points)". Static buildings, road
  surface, and parked vehicles shown in cool blue, labeled "静态背景 (Static Background)".
  Speed arrows on moving cars indicating radial velocity measurements.
  Right panel "筛滤后 (After Filtering)": same scene but moving cars removed; remaining static
  points only (blue). Green check marks indicating "用于配准 (Used for Registration)".
  Clean technical illustration style, white background, professional publication quality,
  consistent blue-red color scheme, axis labels and scale bar included.
-->

### 3.2.5 RANSAC-ICP 混合策略

RANSAC（Random Sample Consensus）与 ICP 的结合属于“先把内点挑出来，再让局部优化做精”的两阶段思路：先用 RANSAC 从重外点对应集中采样生成位姿假设，以共识集大小或鲁棒代价评估假设质量；再用 ICP 在该假设附近做局部精修。这个套路的价值在于，它把 ICP 最怕的两件事拆开处理：初值差的问题让前端负责把解推到可收敛区域；局部精度则交给 ICP 的几何最小二乘去榨干。与 RANSAC 同属“外点极高时仍能先给出可用解”的代表还有 TEASER/TEASER++：论文不仅在摘要中强调已知尺度时可容忍超过 99% 外点，还在 3DMatch 上给出逐场景成功率与时间对比（原文表 II）：TEASER++ 在 Kitchen/Home/Hotel 等 8 个场景的正确配准率为 83.1%–98.6%，平均单次运行时间 0.059 s；RANSAC-1K 仅 74.5%–94.2%（0.008 s），RANSAC-10K 为 79.3%–97.2%（0.074 s）[Yang et al.](cite:yangTEASERFastCertifiable2021)。工程上常见的组合是“TEASER++ 给全局初值 + ICP 做最后一公里”，用 TEASER++ 的鲁棒性换一个更稳的起点，再把最后的精度交给局部优化。

RANSAC 的主要代价是当外点比例升高时，为获得足够高置信度所需的假设数量会迅速增大，这一点在系统评测里非常直观。[Yang et al.](cite:yangRANSACs3DRigid2022) 在 U3M/BMR/U3OR/BoD5 四个数据集上评测了 14 种 RANSAC 风格估计器，并专门在 U3M 上注入可控干扰：高斯噪声标准差从 0.5 pr 到 3.0 pr（步长 0.5 pr）；均匀/随机降采样保留比例从 80% 一直降到 10%；孔洞数量从 6 增到 26（每个孔洞通过 KNN 删除邻域点合成，邻域规模取 $2\\%\\times|\\mathbf{P}^t|$）（论文 Fig. 7）。他们还展示了对应集本身的难度差异可以很大：示例对应集的内点率从 56.41%（117 对）到 13.17%（129 对）不等（Fig. 6）[Yang et al.](cite:yangRANSACs3DRigid2022)。这些“外部条件”的数字能解释很多现象：当内点率和空间分布一旦走坏，采样策略、局部参考系重复性、以及假设评估指标的计算代价，就会一起决定 RANSAC 是否还能在可用时间内筛出足够好的初值。

所以 RANSAC+ICP 和前面几类方法的分工其实很鲜明：前面的方法大都假设“虽然有外点，但当前解已经离真值不算太远”，重点是别让坏对应把局部优化带跑；RANSAC 则是在更早一步解决“我手里这批对应到底有没有希望给出一个靠谱初值”。一旦这个问题都答不出来，再鲁棒的局部 ICP 也只是围着错误初值打转。代价就是它必须反复采样、验证、重算共识集，在高外点率下时间开销会急剧上升。

### 3.2.6 SUCOFT：超核心最大化

SUCOFT（Supercore Maximization with Flexible Thresholding）从图论视角处理外点：给定一组候选对应，在兼容性图（compatibility graph）上以“局部刚体一致性”定义边关系，满足一致性的对应对之间连边；算法核心是在该图上求解“最大超核心”（maximum $K$-supercore）：

$$
\text{$K$-supercore} = \{v\in\mathcal{V} : |\mathcal{N}(v)\cap S|\geq K\}
$$
<!-- label: eq:supercore -->

其中 $K$-超核心是最大子图 $S$，满足其中每个节点至少与 $K$ 个其他节点相连。[Sun](cite:sunSUCOFTRobustPoint2024) 证明最大超核心必然包含最大团（maximum clique），因此在存在噪声与“缺边”的情况下，超核心剪枝往往比最大团更不容易把真实内点过早剔除。在此基础上，SUCOFT 以灵活阈值（flexible thresholding）做后处理进一步精炼对应集，作者报告该精炼在多数设置下仅需 2–3 次迭代即可收敛[Sun](cite:sunSUCOFTRobustPoint2024)。

它和 RANSAC 的对比也很有代表性。RANSAC 是“随机挑几个点，猜一个解，再看有多少人支持”；SUCOFT 则是“先不急着猜解，而是先问哪些对应彼此之间相容”。前者是从参数空间做搜索，后者是从对应图的结构里找稳定子集。于是当外点比例高到采样很难抽中纯内点子集时，图论剪枝常常更有优势；但它也更依赖一开始就有一批质量尚可的候选对应，否则图本身就可能是乱的。

在多个基准测试中，[Sun](cite:sunSUCOFTRobustPoint2024) 在 ETH LiDAR、WHU、Stanford Bunny/Armadillo、3DMatch 与 3DLoMatch 上系统评测了已知尺度与未知尺度两类问题，并报告 SUCOFT 在两类设定下都可容忍超过 99% 的外点。其消融结果显示，SUCOM 在初始外点率为 20%–98% 时可将剩余外点率压到 0%，即便在 99% 的极端外点下，剩余外点率也不超过 10%；在此基础上再由 ROFT 快速收敛，从而把图论一致性剪枝转化为“可落地”的外点抑制链路[Sun](cite:sunSUCOFTRobustPoint2024)。在 3DLoMatch 的已知尺度设置下，SUCOFT 的 registration recall 报告为 43.14%，也反映了其在低重叠室内场景中的实用性[Sun](cite:sunSUCOFTRobustPoint2024)。

### 3.2.7 各方法综合对比

| 方法 | 代表论文 | 核心机制 | 更适合的外点形态 | 主要局限 |
|------|----------|----------|------------------|---------|
| TrICP | [Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002) | 距离排序后截断（LTS） | 部分重叠导致的非重叠外点 | 需先验/估计重叠率；截断边界不自适应 |
| M-估计量 / GNC（FRICP） | [Zhang et al.](cite:zhangFastRobustIterative2022) | 连续降权 + 渐进非凸 | 噪声外点与轻度误配 | 核带宽与退火策略影响收敛；仍是局部法 |
| Sparse ICP | [Bouaziz et al.](cite:bouazizSparseIterativeClosest2013) | $\ell_p$ 稀疏惩罚 + 变量分裂 | 对应集中含显著离群残差 | 非凸；ADMM/近端迭代的收敛与速度依赖超参 |
| 互熵（SCICP） | [Wu et al.](cite:zhengCorrentropyScaleICP2019) | 核函数隐式降权 | 重尾噪声与长尾离群 | 带宽选择敏感；不当设置会过度抑制有效约束 |
| DICP | [Hexsel et al.](cite:hexselDICPDopplerIterative2022) | 多普勒先验筛滤 + 额外残差 | 动态目标引入的系统性外点 | 依赖具备多普勒测量的传感器；权重融合需标定 |
| RANSAC+ICP | [Yang et al.](cite:yangRANSACs3DRigid2022) | 采样假设 + 共识集筛选 + 局部精修 | 特征匹配阶段产生的大量误配 | 高外点时假设数爆炸；非确定性且依赖随机种子 |
| SUCOFT | [Sun](cite:sunSUCOFTRobustPoint2024) | 兼容性图一致性剪枝（超核心） | 对应集外点占优、但内点满足几何一致性 | 图构建开销大；需可靠的初始候选对应集 |
<!-- caption: 第 3.2 节外点鲁棒化方法对比：代表论文、核心机制、典型外点形态与局限。 -->
<!-- label: tab:outlier-comparison -->

| 文献 | 场景/数据集 | 指标口径 | 结果（数值） | 关键设定/前提 |
|------|-------------|----------|--------------|---------------|
| [Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002) | Frog（3D，约 3000 点/点集）+ SQUID（2D，1100 形状） | Frog：MSE/时间/迭代；SQUID：旋转误差（deg） | Frog：ICP（45 次，MSE=5.83，7 s）vs TrICP（重叠率 70%，88 次，MSE=0.10，2 s，1.6 GHz PC）；SQUID 最难设置（20°，60% 重叠）：TrICP 1.7949°，ICRP 3.0254° | LTS 截断只保留最小 $\\lfloor\\rho n\\rfloor$ 对应；SQUID 旋转角 1–20°、重叠率 60–100% 的系统性扫描 |
| [Zhang et al.](cite:zhangFastRobustIterative2022) | 5 组部分重叠模型对（示例：Bunny） | RMSE 与耗时（原文表 1，RMSE 单位为 ×$10^{-3}$） | Bunny：鲁棒点到点 0.85/0.69，0.34 s；Sparse ICP 0.94/0.71，24.06 s | Super4PCS 先粗对齐；在点集上叠加随机外点（论文中给出多档外点比例实验设置） |
| [Bouaziz et al.](cite:bouazizSparseIterativeClosest2013) | “owl” 虚拟扫描对齐（原文图 4） | RMSE（相对真值） | 粗初值：$4.0\\times 10^{-1}$；$p=2$ + 剔除：$d_{th}=5\\%$ 为 $4.1\\times 10^{-1}$、$10\\%$ 为 $2.9\\times 10^{-2}$、$20\\%$ 为 $7.5\\times 10^{-2}$；$p=1$ 为 $1.6\\times 10^{-2}$；$p=0.4$ 为 $4.8\\times 10^{-4}$ | $d_{th}$ 以包围盒对角线百分比定义；$p\\in[0,1]$ 的 $\\ell_p$ 残差 + ADMM；附录注明 shrink 更新常 2–3 次迭代收敛 |
| [Wu et al.](cite:zhengCorrentropyScaleICP2019) | CE-Shape-1（Apple/Pocket/Ray）+ Stanford 3D（Happy/Bunny/Dragon，仿真） | $\\varepsilon_s,\\varepsilon_R,\\varepsilon_{\\vec{t}}$ + 耗时 | 例：Apple：SCICP $\\varepsilon_s=0.0020$、$\\varepsilon_R=9.0351\\times 10^{-4}$、$\\varepsilon_{\\vec{t}}=0.0817$；Scale ICP 0.0687/0.3031/80.0321；CPD 0.1061/0.0889/32.0936（原文表 1）。耗时：Apple SCICP 0.0083 s，CPD 0.0462 s（原文表 2）。3D：Dragon $\\varepsilon_{\\vec{t}}$ 0.0196→$6.8352\\times 10^{-5}$（原文表 3） | 相似变换（含各向同性尺度）；MCC 作为相似度，交替更新对应与变换，并证明单调收敛到局部最优 |
| [Hexsel et al.](cite:hexselDICPDopplerIterative2022) | Aeva Aeries I FMCW LiDAR（5 序列）+ CARLA（2 序列） | Path Error / 平移 RPE / 平均迭代次数（原文表 II） | Baker‑Barry Tunnel：Path Error 525.35 m→1.23 m；迭代 30.8→7.6。Brisbane Lagoon Freeway：Path Error 4337.18 m→4.16 m | 与 Open3D P2Pl ICP 对比；加入 Doppler 残差与动态点剔除（DOR） |
| [Yang et al.](cite:yangRANSACs3DRigid2022) | U3M 注入噪声/降采样/孔洞 + 四数据集评测 | 干扰强度设置 + 对应集统计（实验设置层面） | 高斯噪声 0.5–3.0 pr（步长 0.5）；均匀/随机降采样保留 80%→10%；孔洞 6→26（单孔洞删除邻域点数 $2\\%\\times|\\mathbf{P}^t|$）；示例对应集内点率 56.41%（117 对）到 13.17%（129 对） | 14 种 RANSAC 风格估计器分解到“采样/生成/评估/停止准则”；用于解释高外点下假设数爆炸与评估代价的来源 |
| [Yang et al.](cite:yangTEASERFastCertifiable2021) | 3D 基准 + 3DMatch（论文实验概述） | 外点耐受与量级（论文摘要与实验小结） | 已知尺度时可容忍 >99% 外点；TEASER++ 运行在毫秒级 | TLS 代价 + 图论剪枝 + 可认证松弛；工程上常用作“全局初值”再接 ICP 精修 |
| [Sun](cite:sunSUCOFTRobustPoint2024) | ETH/WHU、Stanford Bunny/Armadillo、3DMatch/3DLoMatch | 外点耐受与 RR（消融 + 基准表） | >99% 外点（已知/未知尺度）仍可工作；SUCOM 处理后：20%–98% 外点剩余 0%，99% 外点剩余 ≤10%；3DLoMatch（已知尺度）RR=43.14%；ROFT 多数仅需 2–3 次迭代 | 先在兼容图上做 SUCOM 大规模剪枝，再用 ROFT 灵活阈值精炼 |
<!-- caption: 第 3.2 节代表性“可复现设置 + 定量结果”汇总（仅摘录文中明确报数且口径清晰的结果）。 -->
<!-- label: tab:outlier-data -->

![鲁棒核函数与外点耐受性对比](../images/ch3-robust-weight-functions.png)
<!-- caption: 四类鲁棒核/权重函数对大残差的抑制方式对比（示意）。$w(r)=\\rho'(r)/(2r)$ 将残差大小 $r$ 映射为“该对应对优化的有效贡献”。相较于 $\\ell_2$（恒定权重），Huber 在大残差处线性降权，Tukey 在阈值外近似归零，而互熵（Gaussian）平滑衰减。 -->
<!-- label: fig:robust-weights -->
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
  Single-panel academic plot comparing robust weight functions for ICP.
  White background, vector style, IEEE-like typography, thin axes, light gridlines.
  Plot w(r) versus residual magnitude r.
  Curves:
  - "L2" (gray dashed): constant horizontal line
  - "Huber" (blue): stays high for small residuals then decays
  - "Tukey" (red): decays to near-zero after cutoff
  - "Gaussian (Correntropy)" (green): smooth exponential-like decay
  Add two shaded vertical regions: left light-gray region labeled "内点区" and right light-red region labeled "外点区".
  Axis labels must be Chinese only: x-axis "残差幅值 r", y-axis "权重 w(r)".
  Legend at top-right, no English axis text.
-->

与对应策略（见[第 3.1 节](ref:sec:correspondence)）的关系在于：外点处理与对应建立相互耦合。TrICP、M-估计量和互熵 ICP 在标准最近邻对应基础上叠加鲁棒化；DICP 则在对应搜索阶段引入多普勒先验主动过滤；而 SUCOFT 工作在特征对应集合上，属于前置外点剔除，独立于 ICP 的几何对应搜索。在实际系统中，常把前置对应过滤（距离/法向量角度阈值，见[第 3.1 节](ref:sec:correspondence)）与迭代中的连续权重衰减联合使用，以覆盖不同来源的外点。[第 3.6 节](ref:sec:global-init) 将进一步讨论全局初始化如何将初始误差压入可收敛区域，从而减少外点主导的失败模式。
