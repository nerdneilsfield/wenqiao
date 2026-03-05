## 8. 结论 (Conclusion)
<!-- label: sec:conclusion -->

ICP 在刚体点云配准中长期扮演“局部精修基线”的角色：它的优势在于问题分解清晰、实现成本低、便于与系统其它模块组合；它的局限也同样明确，主要来自局部收敛、外点与动态干扰，以及计算资源约束[Besl and McKay](cite:beslMethodRegistration3D1992)[Chen and Medioni](cite:chenObjectModellingRegistration1992)[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001)[Pomerleau et al.](cite:pomerleauReviewPointCloud2015)[Tam et al.](cite:tamRegistration3DPoint2013)。本文沿着 [第 3 章](ref:sec:variants)、[第 4 章](ref:sec:software)、[第 5 章](ref:sec:hardware-accel) 和 [第 6 章](ref:sec:evaluation) 组织材料，目标不是给出单一“最优方法”，而是建立一套面向工程选型的判断框架。

### 8.1 关键结论与实践要点

**对应搜索与数据访问模式决定了工程瓶颈**：经典对比研究反复表明，运行时的主导开销往往集中在对应建立与其数据结构实现上，而不是小规模的闭式求解本身[Rusinkiewicz and Levoy](cite:rusinkiewiczEfficientVariantsICP2001)[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。

**鲁棒性改造常比更换局部目标函数更“划算”**：在外点与部分重叠普遍存在的任务中，截断、核函数、GNC 等机制能明显改善偏置与失败率（[第 3.2 节](ref:sec:outlier)），但其收益取决于外点结构与评测协议[Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002)[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。

**两阶段范式是通用工程模板**：全局初始化把问题拉回 ICP 的收敛盆，局部 ICP 提供可控的精修与误差收敛（[第 3.6 节](ref:sec:global-init)）。这一范式既适用于手工特征（如 FPFH）也兼容学习型特征（如 FCGF、GeoTransformer）[Rusu et al.](cite:rusuFPFHFastPoint2009)[Zhou et al.](cite:zhouFastGlobalRegistration2016)[Choy et al.](cite:choyFullyConvolutionalGeometric2019)[Qin et al.](cite:qinGeometricTransformerFast2022a)。

**软件优化可叠加，硬件加速需面向端到端约束**：降采样、并行化与近似最近邻等策略往往可以按“先降规模、再降常数”的顺序组合（[第 4 章](ref:sec:software)），而在严格能耗与延迟预算下，专用处理器、FPGA 流式化与 PIM 路线更可能带来确定性的端到端收益[Xu et al.](cite:xuTigrisArchitectureAlgorithms2019)[Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025)[Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025)。

**评测必须同时报告协议与阈值**：3DMatch 等基准的经验表明，同一指标在不同阈值下结论可能截然不同；缺少阈值与实现细节时，跨论文比较很难稳定复现[Zeng et al.](cite:zeng3DMatchLearningLocal2017)。

### 8.2 面向不同读者的建议

**对算法研究者**：
1. 先把失败模式说清楚：是收敛盆外、结构化外点，还是退化不可观（[第 7 章](ref:sec:future)）。对每个失败模式给出可复现的评测协议（[第 6 章](ref:sec:evaluation)）并报告阈值[Zeng et al.](cite:zeng3DMatchLearningLocal2017)[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。
2. 先做“鲁棒化”和“初始化”，再做局部目标函数微调：在外点/低重叠任务中，这是更稳定的改进路径[Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002)[Yang et al.](cite:yangTEASERFastCertifiable2021)。

**对硬件研究者**：
1. 把优化目标写成系统约束：延迟、吞吐、功耗、内存峰值与失败率需要共同报告（[第 6.2 节](ref:sec:benchmarks) 与 [第 7 章](ref:sec:future)），否则难以与软件方案公平比较[Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。
2. 优先围绕“数据访问 + 对应建立”做共设计：这部分最容易被带宽与随机访存支配，也是专用硬件最能发挥优势的环节[Xu et al.](cite:xuTigrisArchitectureAlgorithms2019)[Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025)。

**对系统工程师**：
1. 先写约束，再选算法：延迟预算、功耗预算、失败后果（能否安全拒绝）决定了“鲁棒估计、不确定性、硬件投入”是否必要（[第 6.1 节](ref:sec:applications) 与 [第 7 章](ref:sec:future)）[Maken et al.](cite:makenSteinICPUncertainty2022)。
2. 先用软件堆栈挖尽常规收益：降采样、数据结构与并行化通常能先带来稳定收益（[第 4 章](ref:sec:software)），再考虑专用硬件（[第 5 章](ref:sec:hardware-accel)）[Muja and Lowe](cite:mujaScalableNearestNeighbor2014)。

![综述结构概览图](../images/ch8-survey-overview.png)
<!-- caption: 本综述的结构概览图：从算法变体到软件优化、硬件路线与评测语境，强调这些层次如何共同影响 ICP 的工程选型。 -->
<!-- label: fig:survey-overview -->
<!-- width: 0.95\textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style for all panels: white background, flat vector illustration, no realistic rendering, no 3D shading, no poster or marketing aesthetics. Treat this as a conceptual mechanism diagram rather than a measured chart unless verified data are explicitly provided. Do not fabricate exact statistics, timings, ratios, or axis values. Use consistent color mapping across all figures: compute/process modules = #2B4C7E, storage/cache/memory = #3C7A89, data flow/candidate flow = #D17A22, retained/active/valid regions = #5B8C5A, bottleneck/pruned/conflict/failure = #A23B2A, text = #333333, borders = #888888, light gray blocks = #EDEDED. Chinese-first labels with concise academic wording, rounded rectangles for modules, aligned multi-panel layout, clear arrows, minimal line crossings, crisp lines, balanced whitespace, suitable for thesis or survey paper.
  Create a publication-quality overview diagram (flat 2D vector style) for an ICP survey paper.
  White background, generous margins, clean sans-serif font with CJK support.
  Title: "ICP 综述结构概览"
  Layout: a left-to-right flow with four blocks: algorithm variants, software optimization, hardware acceleration, and evaluation context.
  Keep the content conceptual rather than decorative. Emphasize the relationship between method design, implementation cost, and evaluation protocol.
  Use subtle blue accent headers and light gray borders. No icons, no 3D, no gradients.
-->
