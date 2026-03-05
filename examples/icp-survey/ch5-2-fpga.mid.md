## 5.2 FPGA 可重配置加速 (FPGA Reconfigurable Acceleration)

<!-- label: sec:fpga -->

FPGA（Field-Programmable Gate Array）是 ICP 硬件加速的重要中间路线：相比 CPU/GPU，它允许研究者把对应搜索、规约和小矩阵求解组织成固定时序的数据通路；相比 ASIC，它又保留了重新布置搜索结构、缓存层级和并行度的能力，适合算法仍在快速迭代的阶段。

从公开工作看，FPGA 路线的演进大致经历了三个阶段。早期工作多把目标放在单个计算内核，例如小矩阵运算或特定 kNN 电路；随后，研究重点转向对应搜索本身的数据结构改写，例如 RPS、分层图和球形桶，以减少随机访存 [Sun et al.](cite:sunRealtimeFPGABasedPoint)[Kosuge et al.](cite:kosugeSoCFPGAbasedIterativeclosestpointAccelerator2020)[Liu et al.](cite:liuHABFNNICPStreamingFPGA2025a)。最近的工作则开始把搜索模块与参数配置、滑动窗口缓存和整条配准流水线一并设计，使同一加速器能够覆盖多种 ICP 变体和场景约束 [Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025)。

### 5.2.1 对应搜索的 FPGA 流水线设计

ICP 的 FPGA 加速首先要处理一个结构性矛盾：最近邻搜索希望保留几何邻近关系，但树形索引的访问顺序对流水线并不友好。只要查询仍依赖频繁的片外访问，FPGA 的并行比较单元就难以持续保持满载。因此，许多设计并不直接照搬软件里的 KD-Tree，而是先改写数据组织，再设计查询流水线。

**RPS（Range-Projection-Structure）**：[Sun et al.](cite:sunRealtimeFPGABasedPoint) 提出针对有组织 LiDAR 点云（按激光线束排列）的新型搜索结构 RPS，将激光线束的相似投影位置和距离编码为连续内存索引，使对应搜索变为规则的矩形窗口查询（而非 KD-Tree 的随机跳转）：

$$
\text{RPS}[r][c] = \text{points with projection}(r, c) \text{ and distance} \approx d_{rc}
$$
<!-- label: eq:rps-index -->

RPS 的关键不在于引入新的距离度量，而在于把“先找树节点、再比距离”的访问顺序改成“先按扫描线定位候选区域、再在局部窗口中筛选对应点”。这样做的前提是输入点云必须保持有组织的 LiDAR 扫描结构；一旦点云已经被重采样成无组织集合，这一优势就会减弱。Sun 等在车载 LiDAR 配准场景中报告，其 FPGA 框架达到 18.6 FPS，对应搜索加速器比既有 FPGA 实现快 13.7 倍，能效比分别优于 GPU 和既有 FPGA 方案 50.7 倍和 27.4 倍 [Sun et al.](cite:sunRealtimeFPGABasedPoint)。

![RPS 与 KD-Tree 内存访问模式对比及 FPGA 流水线预取设计](figures/rps-vs-kdtree.png)
<!-- caption: RPS 与 KD-Tree 访问模式的机制对比示意。该图用于说明树遍历的随机访存与扫描线窗口搜索的顺序访存差异，不对应单一实验中的精确缓存统计或时延数值。 -->
<!-- label: fig:rps-vs-kdtree -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean publication-quality schematic, not photorealistic, not 3D rendered.
  Use consistent color mapping:
    deep blue #2B4C7E for compute/search engines,
    teal blue #3C7A89 for BRAM/cache/storage structures,
    orange #D17A22 for data flow and candidate movement,
    dark green #5B8C5A for valid/local sequential access regions,
    dark red #A23B2A for bottlenecks, random jumps, or failed prefetch,
    grays for neutral structure and outlines.
  Chinese-first labels, strict 2x2 panel grid, rounded rectangles, crisp arrows, no decorative gradients.
  This figure is a conceptual mechanism illustration, not a measured cache/latency chart.
  Four-panel conceptual comparison diagram: KD-Tree vs RPS memory access patterns for FPGA ICP.
  Top-left "KD-Tree 随机跳转 (Random Access)":
    Show scattered nodes and long jumps between addresses.
    Emphasize failed prefetch and poor locality.
  Bottom-left "KD-Tree 内存分布 (Memory Layout)":
    Show parent and child nodes physically separated in memory.
    Highlight that compiler and hardware prefetching are ineffective.
  Top-right "RPS 连续窗口 (Sequential Window Access)":
    Show a 2D scanline grid and a small local window moving sequentially.
    Emphasize contiguous addresses and regular access.
  Bottom-right "FPGA 预取流水线 (Prefetch Pipeline)":
    Show input stream, prefetch buffer, BRAM-backed search engine, and staged processing.
    Add a small qualitative comparison strip showing KD-Tree low locality vs RPS high locality.
  Clean FPGA architecture style, white background, publication quality.
-->

**HA-BFNN-ICP**：[Liu et al.](cite:liuHABFNNICPStreamingFPGA2025a) 没有继续沿用树索引，而是把点云匹配改写成硬件加速的暴力近邻搜索（HA-BFNN），再配合流式预处理和阈值筛选控制候选集规模。这样做的理由很直接：在 FPGA 上，规则扫描和片上缓存往往比复杂树遍历更容易维持稳定吞吐。该方法依赖定点预处理和流式数据调度，在基于 AMD Kintex-7 的自定义板卡上，对单帧 14400 点数据实现 5.76 ms 匹配时间，整套系统在 3.4 W 功耗下相对 CPU 达到 17.36 倍加速，同时保持与软件实现相当的精度 [Liu et al.](cite:liuHABFNNICPStreamingFPGA2025a)。它的局限也很明确：一旦候选集无法通过阈值和数据分布压到可控范围，暴力搜索的比较开销会先升高。

**SoC-FPGA ICP for Picking Robots**：[Kosuge et al.](cite:kosugeSoCFPGAbasedIterativeclosestpointAccelerator2020) 提供了另一条桥接路径。该工作面向 Amazon Picking Challenge 数据集中的机器人抓取位姿估计，把传统 K-D 树搜索替换为分层图结构，并用排序网络实现并行 k-NN 选择；同时利用部分动态重配置在“图构建”和“最近邻搜索”之间复用硬件资源。实验结果表明，该系统在 4.2 W 功耗下将单次物体位姿估计压到 0.72 s，相对基于四核 CPU 和 K-D 树的实现达到 11.7 倍加速 [Kosuge et al.](cite:kosugeSoCFPGAbasedIterativeclosestpointAccelerator2020)。这类结果说明，FPGA 的价值不只在于把一段搜索代码搬进硬件，还在于允许设计者围绕资源复用重写整条搜索路径。

### 5.2.2 多模式对应搜索的可重配置设计

不同场景对对应搜索的需求不同：室内 SLAM 需要高精度 $k$-NN（$k=1$）；多帧融合需要距离约束 NN；点到平面 ICP 需要法向量约束 NN。[Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025) 提出多模式可重配置对应搜索框架：

- **KNN 模式**（$k$ 最近邻）：适合标准 P2P ICP，对应质量最好。
- **RNN 模式**（距离约束最近邻）：仅返回距离 $\leq r$ 的点，自动过滤远离点，适合含外点场景中的距离门控，对应 [第 3.2 节](ref:sec:outlier) 中常见的阈值思想。
- **AKNN 模式**（近似 $k$ 最近邻）：以近似搜索换取更高速度，其设计目标与 [第 4.4 节](ref:sec:approx-nn) 的软件近似搜索思路一致，但这里把折中关系落在硬件可配置寄存器上。

三种模式通过寄存器在运行时切换，不必重新生成比特流。Deng 等将这种多模式搜索建立在扫描线辅助的 SA-RPS 结构上，并在 64 线 LiDAR 的 KITTI 场景中报告 21.5 FPS 的实时配准；其 SA-RPS-CS 搜索加速器相对既有 FPGA 设计达到 2.3--32.4 倍加速、1.8--26.2 倍能效提升，在保持 95\% 以上召回率的同时精度损失很小 [Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025)。这种设计成立的前提，是输入仍保留扫描线拓扑；若点云来源不满足这一条件，SA-RPS 的构建收益会先下降。

![HABFNN 层次化球形桶分区几何与 BRAM 布局设计](figures/habfnn-ball-partition.png)
<!-- caption: HA-BFNN/球形分区类 FPGA 搜索结构示意图。该图用于说明分层候选筛选、片上缓存和并行扫描之间的关系，不对应单一论文中的精确球半径、bank 数或查询时延。 -->
<!-- label: fig:habfnn-ball-partition -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean publication-quality layout, not photorealistic.
  Use chapter-wide consistent colors:
    deep blue #2B4C7E for compute/search engines,
    teal blue #3C7A89 for BRAM and storage banks,
    orange #D17A22 for candidate flow,
    dark green #5B8C5A for retained/visited regions,
    dark red #A23B2A for pruned regions,
    gray outlines and light gray supporting blocks.
  Chinese-first labels, equal panel spacing, strict alignment.
  This figure is a conceptual search-structure illustration, not a quantitative complexity or latency plot.
  Three-panel technical concept diagram: hierarchy-based or bucket-based FPGA search.
  Left panel "层次化球形分区 (Hierarchical Ball Partition)":
    Show a point cloud divided into coarse, medium, and fine candidate regions.
    Highlight that only a subset of nearby regions is visited for one query.
  Middle panel "查询搜索过程 (Query Search Process)":
    Show pruning at each hierarchy level and final local scanning at leaf level.
    Emphasize reduced candidate set rather than exact counts.
  Right panel "BRAM 存储布局 (BRAM Storage Layout)":
    Show several BRAM banks feeding a parallel local-scan engine.
    Emphasize banked on-chip storage and parallel reads.
  Clean FPGA architecture style, white background, publication quality.
-->

### 5.2.3 全流程 FPGA 流水线与数据局部性优化

完整的 FPGA ICP 实现不能只盯住搜索模块，还要处理搜索结果怎样进入后续规约、求解和控制环。否则，即便对应搜索本身已经很快，数据搬运和模块衔接仍会吞掉端到端收益。

**流水线架构**：从公开设计看，较完整的 FPGA 流水线至少包含四类模块：

1. **预处理模块**（降采样 + 法向量估计）：从 LiDAR 接口接收原始点云，输出精简点云及每点法向量。
2. **对应搜索模块**（KD-Tree / RPS / HABFNN）：并行处理所有点的最近邻查询。
3. **协方差累积模块**：以流水线方式并行累积 $H$ 矩阵的 9 个元素（树形加法器，深度 $\log_2 n$）。
4. **SVD 求解模块**：固定 $3 \times 3$ SVD，展开为硬件友好的 Jacobi 迭代或直接 LUT 查表（4–6 Jacobi 扫描即可收敛到 FP32 精度）。

关键性能决策不在于“所有数据都上片”，而在于哪些数据必须保持片上驻留、哪些数据可以流式经过。目标点云或索引结构如果能够稳定留在 BRAM 或片上缓存，对应搜索就能减少反复回访外部存储；源点云则更适合按帧流入，并在完成当前轮对应搜索后立即进入规约模块。RPS、HA-BFNN 和 SA-RPS 三类方案的共同点，都在于想办法提高这种片上驻留比例。

**定点数优化**：定点化的作用不只是“省资源”，还会决定一条流水线能否塞进目标芯片。[Liu et al.](cite:liuEnergyEfficientRuntime2023)把定点运算列为可重配置定位加速器的核心技术之一，并据此在性能、精度和资源之间做设计空间搜索；[Liu et al.](cite:liuHABFNNICPStreamingFPGA2025a)同样将固定点预处理作为流式 HA-BFNN-ICP 的基础。它的前提是场景尺度和数值范围足够稳定；若量化范围设置过紧，误差会先在法向量估计、协方差累积或阈值筛选处放大。

![FPGA ICP 全流程流水线架构](figures/fpga-pipeline.png)
<!-- caption: FPGA ICP 全流程流水线机制示意图。该图用于说明预处理、对应搜索、协方差规约和小矩阵求解的连接关系，以及 BRAM、DSP 和控制逻辑的资源分工，不对应统一实验条件下的精确资源占比或延迟比例。 -->
<!-- label: fig:fpga-pipeline -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, publication-quality academic pipeline schematic.
  Use consistent color mapping:
    deep blue #2B4C7E for compute modules,
    teal blue #3C7A89 for on-chip memory/BRAM,
    orange #D17A22 for data streams,
    dark green #5B8C5A for retained output/valid flow,
    dark red #A23B2A only for bottleneck emphasis if needed,
    gray outlines and light gray background blocks.
  Chinese-first labels, rounded rectangular modules, left-to-right pipeline, balanced whitespace.
  This figure is a conceptual full-pipeline architecture illustration, not a measured resource or latency chart.
  Academic architecture diagram of a full-pipeline FPGA ICP accelerator.
  Main horizontal pipeline flow (left to right), connected by thick blue arrows:
    Box 1 "LiDAR 输入 (LiDAR Input)": sensor icon, raw point cloud stream.
    Box 2 "预处理 (Preprocessing)": two sub-boxes "降采样 Downsample" and "法向量 Normals",
      BRAM icon labeled "片上存储 (On-chip BRAM)".
    Box 3 "对应搜索 (Correspondence Search)": KD-tree/RPS/HABFNN icon with 8 parallel
      search lanes shown, BRAM block labeled "目标点云 Q (Target Cloud Q, BRAM)".
    Box 4 "协方差累积 (Covariance Build)": tree reduction diagram showing 8→4→2→1 adder
      stages, output labeled "H matrix (3×3)".
    Box 5 "SVD/Jacobi": 3×3 matrix with Jacobi sweep arrows, output "R, t".
    Box 6 "变换输出 (Transform Output)": rotation matrix R and translation t displayed.
  Bottom row: qualitative resource usage sketch for BRAM, DSP, and control logic.
  Right side: qualitative latency-breakdown inset showing correspondence search as the dominant stage.
  Clean publication quality, white background, consistent blue/orange/green color scheme.
-->

### 5.2.4 FPGA ICP 实现对比

| 实现 | 平台 | 场景 | 主要设计点 | 已报告结果 |
|------|------|------|-----------|-----------|
| SoC-FPGA ICP [Kosuge et al.](cite:kosugeSoCFPGAbasedIterativeclosestpointAccelerator2020) | SoC-FPGA | Amazon Picking Challenge 抓取位姿估计 | 分层图 k-NN + 排序网络 + 部分动态重配置 | 0.72 s/次位姿估计，4.2 W，11.7× 于四核 CPU + K-D 树 |
| RPS-ICP [Sun et al.](cite:sunRealtimeFPGABasedPoint) | FPGA | 车载有组织 LiDAR 配准 | RPS 结构 + RPS 构建器/搜索器协同 | 18.6 FPS；对应搜索 13.7× 于既有 FPGA；能效 50.7× 于 GPU |
| Runtime Reconfigurable Localization [Liu et al.](cite:liuEnergyEfficientRuntime2023) | Xilinx Zynq-7000 | KITTI、EuRoC 定位 | 定点计算 + 设计空间搜索 + 运行时重配置 | 59.1× 于 Intel CPU，9.2× 于 Arm CPU；平均能耗再降约 18\% |
| HA-BFNN-ICP [Liu et al.](cite:liuHABFNNICPStreamingFPGA2025a) | AMD Kintex-7 自定义板 | 3D LiDAR 建图 | 固定点预处理 + 流式 HA-BFNN + NNT 筛选 | 单帧匹配 5.76 ms；3.4 W；17.36× 于 CPU |
| Multi-mode SA-RPS-CS [Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025) | FPGA | KITTI 64 线 LiDAR 配准 | SA-RPS + 滑动窗口缓存 + 多模式搜索 | 21.5 FPS；搜索 2.3--32.4× 于既有 FPGA；能效 1.8--26.2× 提升 |
<!-- caption: 第 5.2 节 FPGA 代表实现汇总。表中仅保留论文明确报告的场景、设计点和结果，不把不同实验条件下的延迟、功耗和误差直接做横向换算。 -->
<!-- label: tab:fpga-comparison -->

综合来看，FPGA 路线的优势在于可以围绕具体场景快速重写搜索结构，并把这些改写直接映射到流水线和缓存层级上；其弱点则是片上资源有限，很多收益依赖点云组织形式、量化范围和候选集规模。一旦这些前提不成立，吞吐量会先在片外带宽或资源复用处下降。[第 5.3 节](ref:sec:asic)将继续讨论把这些路径进一步固化到 ASIC 后，会带来什么收益，以及又会失去哪些灵活性。
