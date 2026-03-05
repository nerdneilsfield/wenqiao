## 1. 引言
<!-- label: sec:intro -->

　　三维点云配准研究的是这样一个问题：给定两组无序三维点集 $P = \{p_i\} \subset \mathbb{R}^3$ 与 $Q = \{q_j\} \subset \mathbb{R}^3$，在对应关系未知的条件下，估计刚体变换 $T = (R, t) \in SE(3)$，使 $T(P)$ 与 $Q$ 在某种几何误差度量下尽可能一致。若从优化角度看，这一任务等价于在旋转和平移构成的六维空间中同时处理“位姿”与“对应”两个耦合未知量；其中，对应关系的不确定性决定了问题既难以直接写成闭式解，也容易受到噪声、外点和初始化误差的影响。

　　1992 年，[Besl 与 McKay](cite:beslMethodRegistration3D1992) 提出的点对点 ICP 与 [Chen 与 Medioni](cite:chenObjectModellingRegistration1992) 提出的点对面 ICP 几乎同时给出了局部配准的经典框架：固定当前位姿估计对应，再在固定对应下更新位姿。这个交替结构把原本带有组合搜索性质的问题拆成了两个可重复求解的子步骤，因此很快成为三维配准系统的标准后端。此后三十余年，相关工作一方面沿着算法变体扩展鲁棒性、收敛域和适用场景，另一方面沿着软件实现与硬件架构压缩延迟和功耗。[Pomerleau 等](cite:pomerleauReviewPointCloud2015)与 [Tam 等](cite:tamRegistration3DPoint2013)已经梳理了早期方法谱系；本文进一步把“算法设计”“软件加速”“硬件约束”放在同一框架下讨论。

### 1.1 点云配准的重要性与应用场景
<!-- label: sec:applications -->

　　点云配准之所以长期保持研究热度，原因不在于它只服务某一类任务，而在于多类系统都把它当作几何对齐的基础算子。下面按五类代表性场景说明其需求差异，并给出文献中可直接复核的设置或数量级。

　　**移动机器人同步定位与地图构建（SLAM）**。激光雷达里程计依赖逐帧扫描配准估计增量位姿，回环检测则需要把当前观测与历史局部地图重新对齐，以抑制长期漂移。[Pomerleau 等](cite:pomerleauReviewPointCloud2015)将这一流水线拆成数据滤波、关联求解、外点剔除和误差最小化四个模块，并用搜索救援、电厂检测、海岸监测和自动驾驶等案例说明：不同场景变化的不是“是否需要配准”，而是允许的重叠率、噪声水平和计算预算。以 KITTI 为例，整套数据共 6 小时，传感器频率覆盖 10--100 Hz[Geiger 等](cite:geigerVisionMeetsRobotics2013)；这意味着局部配准若放在在线里程计回路中，留给单帧更新的时间多半只有几十到一百毫秒。

　　**自动驾驶高精度定位**。此类任务要求把车载 LiDAR 点云与预建地图实时对齐，因此延迟和功耗常与精度同样重要。[Xu 等](cite:xuTigrisArchitectureAlgorithms2019a)在面向点云配准的体系结构研究中指出，KD 树搜索是普遍存在的主导瓶颈；他们给出的专用处理器 Tigris 在 KD 树搜索子任务上相对 RTX 2080 Ti 获得 77.2 倍加速、7.4 倍功耗降低，折算到端到端配准性能约为 41.7\% 提升、功耗约降为原来的三分之一。这一结果直接说明：当系统工作在持续在线模式时，瓶颈不只来自算法误差模型，还来自数据结构与访存方式。

　　**工业检测与机器人拣选**。Besl 与 McKay 当年提出 ICP 的直接动机，就是把传感器扫描的刚性零件与 CAD 模型对齐，从而判断加工误差[Besl and McKay](cite:beslMethodRegistration3D1992)。这一场景到今天仍然成立，只是约束从“能否对齐”进一步变成“能否在节拍内对齐”。[Kosuge 等](cite:kosugeSoCFPGAbasedIterativeclosestpointAccelerator2020)面向拣选机器人设计的 SoC-FPGA ICP 加速器，在 Amazon Picking Challenge 数据上把位姿估计时间压到 0.72 s、功耗为 4.2 W，相比基于 KD 树的四核 CPU 实现快 11.7 倍；[Liu 等](cite:liuHABFNNICPStreamingFPGA2025a)进一步给出 3.4 W 功耗下最高 17.36 倍的 CPU 加速。这里首先失效的环节多半不是位姿求解，而是最近邻搜索无法跟上抓取周期；一旦搜索延迟失控，后续最小二乘更新再稳定也无法进入控制回路。

　　**医学图像配准与术中导航**。计算机辅助手术需要把术前体数据与术中传感器点云对齐，以定位器械或病灶位置。这类场景的特点不是点数一定很大，而是误差容忍极小，且系统不能依赖复杂纹理或大规模离线训练。[Pomerleau 等](cite:pomerleauReviewPointCloud2015)将医疗应用列为典型方向之一，原因就在于 ICP 的几何误差模型和局部收敛行为更容易被解释与审查；但这一前提只在初始位姿已较接近、可观测结构充分时才成立。

　　**三维重建与多视角拼接**。多视角扫描先做粗配准，再用 ICP 局部精修，原因是只靠局部最近邻难以跨越大位姿偏差。[Rusu 等](cite:rusuFPFHFastPoint2009)提出的 FPFH 仍是常用初始化特征之一；而 [Xu 等](cite:xuPointCloudRegistrationISPRS2023)在多类数据上比较经典方法与学习方法后指出，面对部分重叠和复杂几何，不少方法的成功率仍低于 40\%。由此可见，两阶段框架并未过时，它仍是把“大范围捕获”和“局部高精度对齐”拼接起来的常见工程方案。

| 场景 | 代表文献/数据 | 约束或指标 | 正文摘录的代表性数值 | 直接含义 |
|---|---|---|---|---|
| 移动机器人 SLAM | [Geiger 等](cite:geigerVisionMeetsRobotics2013) | 传感器频率、数据规模 | KITTI 总时长 6 h；频率 10--100 Hz | 在线配准多半只有毫秒到百毫秒级预算 |
| 自动驾驶定位 | [Xu 等](cite:xuTigrisArchitectureAlgorithms2019a) | KD 树搜索与端到端配准性能 | KD 树搜索子任务相对 RTX 2080 Ti 为 77.2 倍加速、7.4 倍功耗降低；端到端约 41.7\% 提升 | 系统瓶颈首先落在对应搜索和访存 |
| 工业拣选 | [Kosuge 等](cite:kosugeSoCFPGAbasedIterativeclosestpointAccelerator2020) | 位姿估计延迟、功耗 | 0.72 s，4.2 W，较四核 CPU 快 11.7 倍 | 节拍受限时，最近邻搜索先成为短板 |
| 嵌入式映射 | [Liu 等](cite:liuHABFNNICPStreamingFPGA2025a) | 执行时间与能耗 | 3.4 W 下最高 17.36 倍 CPU 加速 | 低功耗部署会反过来约束算法实现方式 |
| 多视角重建 | [Xu 等](cite:xuPointCloudRegistrationISPRS2023) | 跨场景成功率 | 部分重叠与复杂几何下，多数方法成功率低于 40\% | 仅靠局部精修不足以覆盖大位姿偏差 |
<!-- caption: 第 1.1 节应用场景中的代表性定量约束与数据摘录。仅保留原文或摘要中口径清晰的数字。 -->
<!-- label: tab:intro-applications-data -->

![点云配准的五类主要应用场景](../images/ch1-applications.png)
<!-- caption: 点云配准的五类主要工程应用场景概览。（a）移动机器人 SLAM：LiDAR 帧间配准建立局部地图；（b）自动驾驶：实时点云与高精地图匹配（10-100 Hz）；（c）工业检测与拣选：扫描零件与 CAD 模型配准；（d）医学图像：术前体数据与术中传感器点云对齐；（e）三维重建：多视角扫描拼接为完整模型。 -->
<!-- label: fig:applications -->
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
  Chapter 1 figure mode: survey-intro overview.
  Focus on application taxonomy, scope comparison, timeline, and chapter motivation.
  All panels should explain where ICP is used, why it matters, or what this survey covers.
  Use conceptual layouts, not benchmark plots, unless the text explicitly cites verified original numbers.
  Five-panel overview diagram of point cloud registration applications, white background,
  clean flat illustration style, blue-gray palette with orange accent.
  Panel (a) "移动机器人 SLAM": top-down floor plan with robot trajectory (blue line),
  LiDAR scan fan, two overlapping scan frames colored red and blue labeled "帧 k" and "帧 k+1".
  Panel (b) "自动驾驶": side-view car with LiDAR cone, overlay of sparse live scan (red dots)
  on dense pre-built map (gray dots), frequency label ">10 Hz".
  Panel (c) "工业检测": robot arm holding a mechanical part, split view showing CAD model
  wireframe (blue) aligned with scan (orange), label "CAD 模型" and "扫描点云".
  Panel (d) "医学图像": simplified bone or organ point cloud in blue, intraoperative probe
  scan in orange, dashed alignment arrow between them, label "术前" and "术中".
  Panel (e) "三维重建": three colored point cloud fragments from different viewpoints (red,
  green, blue) converging to a single merged gray model with label "多视角拼接".
  Each panel has its Chinese label as a small caption below.
-->

### 1.2 ICP 的地位：三十年的主流局部配准基线
<!-- label: sec:icp-status -->

　　ICP 长期作为局部配准基线，主要因为它在“可解释性”“求解成本”和“可替换性”之间保持了较好的平衡。第一，它只要求一个几何最近邻算子，不依赖纹理或人工特征，因此在点云、曲线和网格等不同表示上都能工作[Besl and McKay](cite:beslMethodRegistration3D1992)。第二，当对应暂时固定时，旋转和平移可以退化为闭式最小二乘问题，[Arun 等](cite:arunLeastSquaresFittingTwo1987)与 [Horn](cite:hornClosedformSolutionAbsolute1987)分别给出了 SVD 与四元数解法。第三，它的主循环天然可拆成“建立对应”“抑制坏对应”“更新位姿”三部分，这使工程实现可以在不推翻整套系统的前提下逐项替换模块[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001)。

　　[Pomerleau 等](cite:pomerleauReviewPointCloud2015)将 ICP 的完整配准流水线形式化为**数据滤波 → 关联求解 → 离群值剔除 → 误差最小化**四个可独立替换的功能模块，该框架将百余页的变体研究系统化整合，成为此后算法比较与工程实现的通用参考架构。

　　然而，广泛应用也带来了严重的碎片化问题。针对 ICP 的各类失败模式，研究者在不同学术社区中提出了数百种修改方案，彼此间缺乏统一视角与系统对比。针对**部分重叠**场景，[Chetverikov 等](cite:chetverikovTrimmedIterativeClosest2002)提出了 TrICP 算法；针对**离群值**干扰，[Bouaziz 等](cite:bouazizSparseIterativeClosest2013)提出了含 $\ell_1$ 稀疏惩罚的 Sparse ICP；针对**全局最优**性保证，[Yang 等](cite:yangGoICPGloballyOptimal2016)通过完整 $SE(3)$ 分支定界提供了理论保证；针对**收敛速度**优化，[Pavlov 等](cite:pavlovAAICPIterativeClosest2017)引入 Anderson 加速将迭代次数削减约 30–35%；深度学习方向，[Wang 与 Solomon](cite:wangDeepClosestPoint2019)用注意力机制替代硬最近邻对应，[Yew 与 Lee](cite:yewRPMNetRobustPoint2020)以可学习 Sinkhorn 最优传输求解软对应概率矩阵。

　　另一方面，性能压力也推动了与算法并行演化的实现路线。[Xu 等](cite:xuTigrisArchitectureAlgorithms2019a)把 KD 树搜索作为体系结构优化核心；[Liu 等](cite:liuHABFNNICPStreamingFPGA2025a)直接以暴力近邻搜索的规则访存换取流式 FPGA 效率；PICK [Nie 等](cite:niePICKSRAMbasedProcessinginmemory2025)则把 kNN 查询进一步下推到 SRAM 存内计算阵列，报告相对现有设计 4.17 倍加速和 4.42 倍能效提升。也就是说，部署平台并不只是“运行算法”的容器，它会反过来影响对应搜索、数据布局和近似策略的选择。

### 1.3 综述范围与文章结构
<!-- label: sec:scope -->

　　本综述沿**算法分类、软件加速、硬件加速**三条主线组织 ICP 文献，并以统一的计算瓶颈分解框架将算法选择与实现约束有机连接。

　　[第 2 节](ref:sec:background)形式化定义配准问题，给出刚体变换的数学表示与基本目标函数，梳理标准 ICP 算法的步骤流程与收敛性质，并归纳典型失败模式与应对策略。

　　[第 3 节](ref:sec:variants)按对应建立、鲁棒性增强、收敛加速、变换估计、全局初始化与学习化六个维度系统归纳 ICP 变体，强调每类改动对应的误差来源与计算代价。

　　[第 4 节](ref:sec:software)讨论软件层加速策略：数据结构优化、降采样/多分辨率处理、并行化与近似最近邻等方法在精度-速度权衡上的可量化影响。

　　[第 5 节](ref:sec:hardware)讨论 GPU、FPGA、ASIC 与 PIM 四条硬件加速路径，并将其与最近邻搜索、矩阵构建等计算热点对应起来。

　　[第 6 节](ref:sec:applications)整理主要应用场景、常用数据集与评测协议，并给出跨方法的对比维度与复现要点。

　　[第 7 节](ref:sec:future)总结仍未解决的核心挑战与潜在研究方向；[第 8 节](ref:sec:conclusion)给出全文结论。

### 1.4 与已有综述的对比
<!-- label: sec:prior-surveys -->

　　三篇代表性系统综述均未覆盖本文范围，各有侧重与局限。

　　**[Pomerleau 等 2015](cite:pomerleauReviewPointCloud2015)**（*Foundations and Trends in Robotics*，104 页）从移动机器人视角梳理了 2014 年前的配准算法，涵盖搜索救援、工业检测、海岸监测、自动驾驶四类应用场景，分类框架详尽完善。然而，该综述发表于深度学习配准方法成熟之前，未包含 DCP、RPM-Net 等学习型方法，亦无任何硬件加速内容，且聚焦于移动平台软件实现，未涉及 FPGA/ASIC/PIM 等专用硬件路径。

　　**[Tam 等 2013](cite:tamRegistration3DPoint2013)**（*IEEE TVCG*，vol. 19，pp. 1199—1217）覆盖刚性与非刚性三维配准，是该领域较为全面的算法分类综述。其主要局限在于聚焦算法描述层面，不讨论计算复杂度量化、软件优化实现或任何形式的硬件加速，亦不区分不同部署约束下的算法选择策略。

　　**[Xu 等 2023](cite:xuPointCloudRegistrationISPRS2023)**（*ISPRS Open Journal*）同时覆盖经典与深度学习配准方法，在室内到卫星的多源数据集上进行了定量评估，是近年较为全面的方法比较工作。该综述偏重摄影测量与遥感场景，不含硬件加速设计，对嵌入式与边缘部署约束的讨论也相对有限。

　　除上述三篇系统综述外，[Brightman 与 Fan 2022](cite:brightmanBriefOverviewCurrent2022)从"无靶标（cloud-to-cloud）"配准流程出发，对挑战与潜在研究方向做了凝练讨论，并专门点评了深度学习方法在点云配准中的兴起及其尚未解决的问题；但该工作篇幅较短，缺少跨部署约束（软件与硬件）的定量对比框架。[Yang 等 2024](cite:yang20243dregistration30years)以更宽口径回顾了三十年 3D 配准方法谱系，但未对 ICP 的加速实现与硬件路径给出面向工程部署的系统总结。

　　本文的工作重点在于把**算法变体 × 软件加速 × 硬件加速**放进同一条分析链路中：前两类问题决定“误差如何形成、如何被抑制”，后一类问题决定“这些设计是否能在既定时延与功耗下落地”。例如，PICK [Nie 等](cite:niePICKSRAMbasedProcessinginmemory2025)强调的是把最近邻查询的数据搬运压到存储层，HA-BFNN [Liu 等](cite:liuHABFNNICPStreamingFPGA2025a)强调的则是以规则数据流替代树结构访问；两者处理的是同一瓶颈，但对应的算法友好性并不相同。

![本综述与已有综述的覆盖维度对比](../images/ch1-survey-comparison.png)
<!-- caption: 本综述与三篇代表性系统综述在覆盖维度上的对比。横轴为四个维度（经典 ICP 变体、深度学习方法、软件加速、硬件加速），纵轴为各综述；实心圆表示完整覆盖，空心圆表示部分覆盖，叉号表示不覆盖。本综述为唯一同时覆盖四个维度的工作。 -->
<!-- label: fig:survey-comparison -->
<!-- width: 0.75\textwidth -->
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
  Chapter 1 figure mode: survey-intro overview.
  Focus on application taxonomy, scope comparison, timeline, and chapter motivation.
  All panels should explain where ICP is used, why it matters, or what this survey covers.
  Use conceptual layouts, not benchmark plots, unless the text explicitly cites verified original numbers.
  Academic coverage comparison table/heatmap, white background, clean minimalist style.
  Four rows (surveys): "Pomerleau et al. 2015", "Tam et al. 2013 (TVCG)",
  "Xu et al. 2023 (ISPRS)", "本综述 (Ours)".
  Four columns (dimensions): "经典 ICP 变体", "深度学习方法", "软件加速", "硬件加速".
  Cell content:
  - Pomerleau 2015: filled circle, cross, partial circle, cross
  - Tam 2013: filled circle, cross, cross, cross
  - Xu 2023: partial circle, filled circle, cross, cross
  - Ours: filled circle, filled circle, filled circle, filled circle
  Filled circle = "完整覆盖" (dark blue), partial circle = "部分覆盖" (light blue),
  cross = "不覆盖" (gray). Add a legend at bottom.
  Highlight the "Ours" row with a light blue background to emphasize full coverage.
-->

![ICP 发展时间轴 1992—2025](../images/icp-timeline.png)
<!-- caption: ICP 算法、加速技术与专用硬件的发展时间轴（1992—2025）。四条泳道分别为基础算法、算法变体、深度学习方法与专用硬件加速器，展示三十余年间的关键里程碑。 -->
<!-- label: fig:timeline -->
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
  Chapter 1 figure mode: survey-intro overview.
  Focus on application taxonomy, scope comparison, timeline, and chapter motivation.
  All panels should explain where ICP is used, why it matters, or what this survey covers.
  Use conceptual layouts, not benchmark plots, unless the text explicitly cites verified original numbers.
  Horizontal academic timeline figure, x-axis spans 1992 to 2025, title "ICP 算法发展时间轴
  (ICP Algorithm Timeline 1992-2025)". White background, blue and orange accent colors,
  clean vector style, bilingual labels (Chinese primary, year in numbers).
  Four parallel swim-lanes with labels on the left:
  Lane 1 "基础算法 (Foundations)": 1992 "Besl-McKay ICP (点对点)", 1992 "Chen-Medioni
  (点对面)", 2003 "NDT", 2009 "GICP".
  Lane 2 "算法变体 (Variants)": 2002 "TrICP", 2013 "Sparse ICP", 2016 "Go-ICP",
  2017 "AA-ICP", 2019 "Symmetric ICP", 2022 "DICP", 2023 "GFOICP", 2025 "BSC-ICP".
  Lane 3 "深度学习 (Deep Learning)": 2019 "DCP", 2019 "DeepVCP", 2020 "RPM-Net",
  2022 "GeoTransformer", 2024 "PointDifformer", 2025 "NAR-*ICP".
  Lane 4 "专用硬件 (Hardware)": 2019 "Tigris (MICRO)", 2020 "SoC-FPGA", 2020 "QuickNN
  (HPCA)", 2021 "NDT-FPGA", 2024 "Tartan (ISCA)", 2025 "PICK / HA-BFNN / PointISA".
  Each event shown as a labeled dot on a horizontal line. Lane 1 blue, Lane 2 orange,
  Lane 3 green, Lane 4 purple. Year gridlines at 1992, 2000, 2010, 2020, 2025.
-->
