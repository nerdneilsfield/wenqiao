## 5.1 硬件加速的动机与设计空间 (Motivation and Design Space for Hardware Acceleration)
<!-- label: sec:hardware -->

[第 4 章](ref:sec:software)已经表明，软件优化能够降低 ICP 的平均延迟，但瓶颈仍集中在最近邻搜索的数据访问阶段。对自动驾驶和机器人点云任务而言，这一瓶颈并不是抽象判断，而是多篇硬件论文反复验证的共识：[Xu 等](cite:xuTigrisArchitectureAlgorithms2019)在点云配准设计空间探索中指出，KD-Tree 搜索在不同实现之间都占据主导时间；[Chen 等](cite:chenParallelNNParallelOctreebased2023a)进一步指出，已有加速器即使引入并行计算单元，仍会被外部 DDR 带宽限制；[Nie 等](cite:niePICKSRAMbasedProcessinginmemory2025)则把点云 kNN 的主要困难概括为“计算强度高且内存访问开销重”。因此，第五章讨论硬件加速的出发点不是单纯追求更高算力，而是分析不同硬件路线如何处理随机访存、片外带宽和数据搬运。

本节按这一逻辑展开。首先说明通用处理器为什么难以持续压缩最近邻搜索延迟；随后总结 ICP 各子步骤中哪些部分值得硬件投入；再将设计空间拆成数值精度、器件形态和算法共设计三个维度；最后讨论单模块加速为何不必然转化为系统级收益，为后续 [第 5.2 节](ref:sec:fpga)、[第 5.3 节](ref:sec:asic)、[第 5.4 节](ref:sec:pim) 和 [第 5.5 节](ref:sec:codesign) 奠定比较框架。

### 5.1.1 通用处理器的性能瓶颈

ICP 算法的计算结构与通用 CPU 的设计假设之间存在根本性不匹配：

**内存访问不规则**：KD-Tree、Octree 和球形桶的查询都包含条件分支与层次遍历。CPU 和 GPU 可以并行执行距离计算，但难以规整树遍历的访问序列，因此缓存复用和预取收益有限。[Xu 等](cite:xuTigrisArchitectureAlgorithms2019)之所以把 KD-Tree 搜索作为 Tigris 的首要加速对象，正是因为不同精度和性能折中下，这一步始终压过配准流水线的其他阶段。[Chen 等](cite:chenParallelNNParallelOctreebased2023a)对八叉树 kNN 的分析也得到相同结论：若搜索仍依赖片外 DDR，内部并行度提升会很快受外部带宽约束。

**带宽墙先于算力墙暴露**：点云对应搜索涉及大量“取节点、比较、更新候选集”的短计算链路。对于这类负载，外部存储的访问时延往往比单次距离计算更难压缩，因此硬件论文普遍把高带宽缓存、片上 SRAM 或 PIM 作为核心设计点，而不是继续增加浮点单元数量。[Chen 等](cite:chenParallelNNParallelOctreebased2023a)使用 HBM 和片上多通道缓存提升可用带宽；[Nie 等](cite:niePICKSRAMbasedProcessinginmemory2025)则进一步把距离计算和 Top-$k$ 维护下推到存储阵列内部，以消除运行时片外访问。

**功耗差距来自控制与搬运开销**：通用处理器必须同时服务多类程序，因此控制逻辑、缓存层级和一致性开销无法为 ICP 单独裁剪。专用加速器只保留最近邻搜索和小矩阵运算需要的数据通路，因而更容易把功耗集中到“确实在做几何计算”的部分。[Liu 等](cite:liuEnergyEfficientRuntime2023)在 Zynq-7000 上实现的可重配置定位加速器，相对 Intel 和 Arm CPU 分别达到 59.1 倍和 9.2 倍加速，并通过运行时配置把平均能耗再降约 18\%；[Xu 等](cite:xuTigrisArchitectureAlgorithms2019)的 Tigris 在 KD-Tree 搜索上相对 RTX 2080 Ti 达到 77.2 倍加速，同时把功耗降至后者的约 $1/7.4$。这些结果说明，硬件收益并不只来自“算得更快”，还来自“少搬数据、少走控制流”。

![Roofline 模型下 ICP 算子的内存受限分析](figures/roofline-icp.png)
<!-- caption: ICP 各算子在 Roofline 模型下的受限关系机制示意。该图用于说明最近邻搜索更容易受带宽限制、而固定规模 SVD 更接近计算受限，不对应单一论文中的精确测试数值。 -->
<!-- label: fig:roofline-icp -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean publication-quality layout, not photorealistic, not 3D rendered, not poster-like.
  Use consistent color mapping:
    deep blue #2B4C7E for compute/processing units,
    teal blue #3C7A89 for memory/cache/storage,
    orange #D17A22 for data flow and intermediate states,
    dark green #5B8C5A for valid/retained regions,
    dark red #A23B2A for bottlenecks/conflicts/pruned regions,
    dark gray #333333 text, medium gray #888888 borders, light gray #EDEDED background blocks.
  Chinese labels with optional English parentheses.
  Strict multi-panel alignment, rounded rectangles, crisp arrows, restrained annotation density.
  This figure is a conceptual mechanism illustration, not a quantitative experimental plot.
  Academic Roofline-style mechanism diagram for ICP operators, two-panel layout.
  Left panel "通用 CPU Roofline":
    Log-scale x-axis for arithmetic intensity and log-scale y-axis for performance.
    Show a horizontal compute ceiling and a diagonal memory-bandwidth ceiling.
    Place KD-Tree query deep in the memory-bound region, covariance construction near the ridge,
    and fixed-size SVD in the compute-bound region.
    Annotate that random access dominates cache behavior.
  Right panel "专用硬件带宽迁移":
    Overlay the original CPU roofline in light gray.
    Show FPGA/ASIC and PIM rooflines shifting right to indicate higher effective bandwidth.
    Add arrows indicating that the search bottleneck moves when bandwidth and data locality improve.
  Clean academic style, white background, publication quality.
-->

### 5.1.2 ICP 的计算热点分析

理解硬件设计空间的前提，是先确定哪一类算子值得专门映射到硬件。现有论文虽然采用的数据结构和平台不同，但结论相对一致：最近邻搜索是第一瓶颈，协方差累积和小矩阵求解属于第二层瓶颈。[Xu 等](cite:xuTigrisArchitectureAlgorithms2019)围绕 KD-Tree 搜索展开专用处理器设计；[Sun 等](cite:sunRealtimeFPGABasedPoint)、[Kosuge 等](cite:kosugeSoCFPGAbasedIterativeclosestpointAccelerator2020)、[Chen 等](cite:chenParallelNNParallelOctreebased2023a)和 [Nie 等](cite:niePICKSRAMbasedProcessinginmemory2025)也都把对应搜索或 kNN 查询置于加速核心。相比之下，$3 \times 3$ SVD 与位姿更新虽然不可缺少，但计算规模固定、数据重用高，在大多数实现里都不是决定端到端时延的首要因素。

图 [图 5-2](ref:fig:icp-hotspot)给出这种“主瓶颈与次瓶颈”关系的机制示意：

![ICP 计算热点分解与硬件加速机会分析](figures/icp-hotspot.png)
<!-- caption: ICP 计算热点与硬件加速机会示意图。该图用于说明“对应搜索优先、规约次之、固定小矩阵再次之”的相对关系，不对应单一实验中的精确占比。 -->
<!-- label: fig:icp-hotspot -->
<!-- width: 0.7\textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean publication-quality layout, not photorealistic, not 3D rendered.
  Use the same chapter-wide color mapping:
    deep blue #2B4C7E for compute-heavy dominant modules,
    teal blue #3C7A89 for storage-related blocks,
    orange #D17A22 for data flow and secondary modules,
    dark green #5B8C5A for retained/beneficial stages,
    dark red #A23B2A for bottlenecks or pruned/inefficient stages,
    grays for neutral background and outlines.
  Chinese-first labeling, compact legend, strict panel alignment.
  This figure is a conceptual hotspot illustration, not a measured runtime chart.
  Academic pie chart and bar chart combination showing ICP hotspot relationship.
  Left pie chart:
    Nearest-neighbor search is the largest segment,
    covariance construction is the second-largest segment,
    fixed-size SVD is a small segment,
    and other control/update steps are the smallest segment.
  Right horizontal bar chart:
    Show relative hardware acceleration opportunity with nearest-neighbor search highest,
    covariance construction second, SVD lower, and control-dominated steps lowest.
  White background, publication quality, labels in Chinese and English.
-->

**最近邻搜索**：每个源点的查询彼此独立，理论上有很高并行度，但树遍历、候选更新和片外取数交织在一起，使这一步最容易暴露存储系统瓶颈。因此，FPGA、ASIC 和 PIM 三条路线都把对应搜索作为第一优先级。

**协方差矩阵构建与规约**：这一步的数据访问更规则，适合映射到 SIMD、流水线或树形规约网络。若系统目标是完整 ICP 流水线，而不是只做 kNN 内核，加速器通常还需要覆盖这一部分，否则对应搜索被压缩后，规约会变成新的前端瓶颈。

**SVD 与位姿更新**：其矩阵维度固定，便于做定长数据通路或微码优化，但收益更多体现在稳定延迟和流水线闭环，而不是绝对吞吐量。

这一分解意味着，硬件方案若不先解释如何处理对应搜索，就难以在系统层面给出可信的收益。

### 5.1.3 硬件设计空间的三个维度

面向 ICP 的硬件加速器设计涉及三个正交维度：

**1. 精度-性能权衡（Precision-Performance Tradeoff）**：
- 全精度浮点实现保留了较宽的动态范围，适合直接复用现有软件算子，但面积和功耗开销最高。
- 半精度或定点实现能够显著降低乘加阵列成本，因此在 FPGA 和 PIM 设计中更常见；代价是必须重新验证量化误差对配准精度和收敛稳定性的影响。[Liu 等](cite:liuEnergyEfficientRuntime2023)明确把定点运算作为节省资源的核心手段之一，[Nie 等](cite:niePICKSRAMbasedProcessinginmemory2025)则进一步把位宽裁剪作为性能与精度之间的运行时折中。

**2. 灵活性-效率权衡（Flexibility-Efficiency Tradeoff）**：
- FPGA 允许研究者快速验证新的搜索结构和流水线组织，因此 RPS、HA-BFNN、多模式对应搜索等方案都首先落在可重配置平台上 [Sun 等](cite:sunRealtimeFPGABasedPoint)[Liu 等](cite:liuHABFNNICPStreamingFPGA2025a)[Deng 等](cite:dengEnergyefficientRealtimeFPGA2025)。
- ASIC 将配置自由度换成更稳定的时延和更高的单位能效，适合算法路径已经相对固定的场景，例如 Tigris 面向点云感知的专用数据通路 [Xu 等](cite:xuTigrisArchitectureAlgorithms2019)。
- PIM 不再把“更强计算核心”当成唯一解法，而是把距离计算与候选维护尽量推近存储阵列，以减轻总线传输压力 [Nie 等](cite:niePICKSRAMbasedProcessinginmemory2025)[Shin 等](cite:shin2IMNN2025)。

**3. 算法-硬件协同设计（Algorithm-Hardware Co-design）**：
纯软件优化主要在既有算法框架内压低常数项；协同设计则允许研究者改写数据结构、搜索策略和数值表示，以换取硬件友好的访问模式。例如，Tigris 通过两阶段 KD-Tree 与近似搜索挖掘查询级和节点级并行 [Xu 等](cite:xuTigrisArchitectureAlgorithms2019)；ParallelNN 通过并行八叉树构建和关键帧调度提升数据复用 [Chen 等](cite:chenParallelNNParallelOctreebased2023a)；PICK 通过位宽裁剪和两级流水线把 kNN 的距离计算与 Top-$k$ 选择耦合起来 [Nie 等](cite:niePICKSRAMbasedProcessinginmemory2025)。协同设计的收益更高，但每一次算法改写都需要重新检查误差传播、鲁棒性边界和系统接口。

### 5.1.4 软硬件之间的系统鸿沟

只看单个内核的峰值吞吐量，容易高估系统级收益。点云 SLAM 或机器人定位流水线至少还包含预处理、特征提取、位姿图优化和地图更新；如果加速器只压缩对应搜索，而 DMA、主控调度或后端求解没有同步调整，端到端时延仍会停在其他模块上。因此，硬件设计除了追求局部加速，还需要回答三个系统问题：

- **系统级热点**：与 ICP 共同占据主要时间的模块（如体素哈希更新、法向量计算）是否也需要加速？
- **数据带宽**：加速器与处理器之间的接口带宽是否成为瓶颈（如 PCIe 传输延迟）？
- **控制流整合**：加速器如何与 SLAM 框架的主控制流集成（中断、DMA、协处理器接口）？

[Liu 等](cite:liuEnergyEfficientRuntime2023)的可重配置定位加速器正是沿着这一思路设计的：它不是把并行度固定死，而是根据场景中的特征点数量动态调整硬件配置，在维持精度和性能约束的同时把平均能耗再降约 18\%。这类结果提示我们，真正可部署的加速器必须同时处理“高峰负载够快”和“轻载场景不过度耗电”两类需求。

| 代表工作 | 平台/工艺 | 任务与场景 | 指标 | 已报告结果 |
|---------|---------|----------|------|----------|
| Runtime Reconfigurable Localization [Liu et al.](cite:liuEnergyEfficientRuntime2023) | Xilinx Zynq-7000 FPGA | KITTI、EuRoC 机器人定位 | 相对 CPU 加速比、运行时节能 | 59.1× vs Intel CPU，9.2× vs Arm CPU；动态配置再降约 18\% 平均能耗 |
| RPS-ICP [Sun et al.](cite:sunRealtimeFPGABasedPoint) | FPGA | 有组织 LiDAR 点云配准 | 帧率、对应搜索速度、能效 | 18.6 FPS；对应搜索 13.7× 于既有 FPGA；能效 50.7× 于 GPU |
| ParallelNN [Chen et al.](cite:chenParallelNNParallelOctreebased2023a) | Virtex HBM FPGA | KITTI 点云 kNN | 加速比、能效 | 107.7× vs CPU，12.1× vs GPU；能效 73.6×/31.1× |
| Tigris [Xu et al.](cite:xuTigrisArchitectureAlgorithms2019) | 16 nm ASIC | 点云配准 KD-Tree 搜索 | 子过程加速、端到端收益、功耗 | KD-Tree 搜索 77.2× vs RTX 2080 Ti；端到端性能提升 41.7\%；功耗降 3.0× |
| PICK [Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025) | SRAM-PIM | KITTI、SONN、S3DIS、DALES 点云 kNN | 加速比、节能 | 4.17× 加速，4.42× 节能 |
| C²IM-NN [Shin et al.](cite:shin2IMNN2025) | 28 nm CAM-PIM | 3D 点云匹配 | 能效、存储占用 | 23.08× 能效提升，48.4\% 存储占用下降 |
<!-- caption: 第 5.1 节代表性硬件工作与已公开结果汇总。表中仅保留论文明确报告的场景、指标和数值，不对不同论文的延迟与功耗做未经统一实验条件校准的横向换算。 -->
<!-- label: tab:hw-platform-comparison -->

![ICP 硬件加速设计空间三维分析](figures/hw-design-space.png)
<!-- caption: 面向 ICP 的硬件加速设计空间机制示意图。该图用于展示灵活性、数值表示和协同设计程度三类权衡关系，点位为概念定位，不对应统一基准下的精确坐标。 -->
<!-- label: fig:hw-design-space -->
<!-- width: 0.85\textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, publication-quality academic schematic, not a realistic 3D render.
  Use the same chapter-wide color mapping:
    deep blue #2B4C7E for compute/processing families,
    teal blue #3C7A89 for memory/storage-oriented families,
    orange #D17A22 for data-flow and mid-spectrum designs,
    dark green #5B8C5A for retained/efficient regions,
    dark red #A23B2A for bottleneck-limited or low-flexibility regions,
    dark gray #333333 text and gray outlines.
  Chinese labels with optional English parentheses. Clean axes, balanced whitespace, minimal decorative effects.
  This figure is a conceptual design-space illustration, not a quantitative scatter plot.
  Conceptual 3D design-space diagram for ICP hardware acceleration.
  Three axes:
    flexibility vs efficiency,
    numeric precision from floating point to low precision,
    co-design depth from hardware-only to algorithm-hardware co-design.
  Place representative families qualitatively:
    CPU/GPU in higher-flexibility region,
    FPGA structured-search methods in the middle,
    ASIC hotspot-specific designs in high-efficiency region,
    PIM methods in high co-design and low/medium flexibility region.
  Use sphere sizes qualitatively to suggest relative performance-per-watt.
  White background, publication quality, clear academic labeling.
-->

[第 5.2 节](ref:sec:fpga)到 [第 5.4 节](ref:sec:pim) 将分别展开 FPGA、ASIC 与 PIM 的具体实现；[第 5.5 节](ref:sec:codesign)再回到跨平台的共设计方法，讨论哪些算法改写值得为硬件付出复杂度代价。
