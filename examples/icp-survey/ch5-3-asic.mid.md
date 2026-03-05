## 5.3 机器人专用处理器（ASIC）(Robot-Specific Processors and ASICs)

<!-- label: sec:asic -->

当搜索结构和数据路径已经相对稳定时，ASIC 才开始显示出比 FPGA 更强的优势。原因不难理解：ASIC 不再为可重配置互连和通用 LUT 付出额外面积，可以把更多晶体管预算直接投到片上存储、专用比较单元和规约数据通路上。因此，本节不再讨论“如何快速试错”，而是讨论当设计者愿意接受更高前期成本和更低后续灵活性时，ICP 相关硬件还能向前推进到什么程度。

本节选择三条有代表性的路线。Tigris 代表“围绕点云配准内核做深度协同设计”的专用处理器；Tartan 代表“面向机器人工作负载抽象出通用微架构支持”的处理器路线；PointISA 代表“保留处理器生态、用 ISA 扩展承载点云原语”的折中方案。三者的共同问题都是如何减少点云应用中的数据搬运和控制开销，但它们接受的算法改写程度和软件兼容目标并不相同。

### 5.3.1 Tigris：点云感知的协同设计处理器

Tigris [Xu et al.](cite:xuTigrisArchitectureAlgorithms2019) 是较早明确把“点云配准中的 KD-Tree 搜索”当作专用架构对象来处理的代表性工作，在 TSMC 16nm FinFET 工艺节点实现。

**算法-架构协同创新**：Tigris 的关键判断是，KD-Tree 搜索并非完全不可并行，而是需要先通过算法改写暴露出可被硬件利用的并行性。论文把这一思路拆成算法侧和架构侧两个部分：

1. **算法侧**：通过两阶段 KD-Tree 和近似搜索，把原本逐点精确查询的流程改写成“少量精确查询 + 邻域复用/插值”的形式。这样做的目的不是改变 ICP 的目标函数，而是减少真正需要进入树遍历的查询数量，并暴露查询级并行和节点级并行。

2. **架构侧**：围绕这种并行性组织向量化搜索引擎，把树节点放入 bank-interleaved SRAM，并让搜索单元和递归单元协同执行，以减轻访问冲突和控制停顿。换句话说，Tigris 不是简单把软件里的 KD-Tree 放进硬件，而是先重排数据结构，再让硬件沿着新的访问顺序运行。

**性能结果**：在 KITTI 相关点云配准任务上，Tigris 相对 RTX 2080 Ti 在 KD-Tree 搜索子过程上达到 77.2 倍加速和 7.4 倍功耗降低，并转化为端到端配准性能 41.7\% 提升和功耗 3.0 倍下降 [Xu et al.](cite:xuTigrisArchitectureAlgorithms2019)。这一结果的意义在于，它证明了“算法允许轻微近似 + 架构围绕搜索重写”的组合确实能把随机树遍历转化成可加速的内核。它的前提也同样清楚：如果算法后来不再以 KD-Tree 搜索为主，这套专用数据通路的复用价值会迅速下降。

![Tigris 向量化 KD-Tree 搜索引擎架构与 Bank-Interleaved SRAM 设计](figures/tigris-search-engine.png)
<!-- caption: Tigris 向量化 KD-Tree 搜索引擎示意图。该图用于说明两阶段搜索、bank 交织存储和多核查询调度的关系，不对应统一实验条件下的精确冲突率、插值误差或每帧延迟。 -->
<!-- label: fig:tigris-search-engine -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean academic microarchitecture schematic, not photorealistic.
  Use consistent color mapping:
    deep blue #2B4C7E for compute/search cores,
    teal blue #3C7A89 for SRAM and storage hierarchy,
    orange #D17A22 for query/data flow,
    dark green #5B8C5A for retained/reused query paths,
    dark red #A23B2A for conflicts or costly paths,
    gray outlines and labels.
  Chinese-first labels, strict panel alignment, rounded blocks, crisp buses and arrows.
  This figure is a conceptual architecture illustration, not a cycle-accurate or power-accurate diagram.
  Three-panel conceptual ASIC architecture diagram: Tigris-style KD-Tree search engine.
  Left panel "向量化搜索引擎 (Vectorized Search Engine)":
    Show multiple search cores, a request bus, an arbiter, and bank-interleaved SRAM.
    Emphasize vectorized search and coordinated memory access.
  Middle panel "稀疏搜索+插值 (Sparse Search + Interpolation)":
    Show a small set of exact queries and nearby points reusing their results by interpolation.
    Emphasize reduced expensive queries.
  Right panel "冲突仲裁时序 (Conflict Arbitration Timing)":
    Show several cores competing for banks and an arbiter resolving conflicts.
    Emphasize coordinated scheduling rather than exact rates.
  Clean ASIC microarchitecture style, white background, publication quality.
-->

### 5.3.2 Tartan：机器人应用的微架构设计

Tartan [Bakhshalipour and Gibbons](cite:bakhshalipourTartanMicroarchitectingRobotic2024) 走的是另一条路线。它并不为 ICP 单独做一颗芯片，而是试图抽象出机器人应用在感知、规划和控制中的共性瓶颈，再把这些瓶颈变成处理器级支持。

**机器人工作负载的共性**：Tartan 把问题表述为“现有 CPU 既不够像专用加速器，又不够懂机器人工作负载”。论文强调三类共性：

- 很多机器人内核的内存访问缺乏常规 CPU 假设下的规则局部性。
- 一部分计算虽然规整，但规模很小，难以充分利用通用向量单元。
- 控制与数据访问经常紧耦合，单纯增加算术吞吐并不能直接转化为系统收益。

**Tartan 的微架构支持**：

1. **面向机器人语义的预取与缓存支持**：论文提出机器人语义预取和应用内缓存分区，用来缓和非规则访问对缓存层级的冲击。

2. **面向小规模内核的定向计算支持**：通过定向向量化和面向近似计算的硬件路径，提高小规模机器人内核的执行效率。

3. **更强调端到端应用而非单一 ICP 内核**：因此，它关注的不是某一步搜索的绝对峰值加速，而是整套机器人软件在较小面积开销下能否持续受益。

在 RoWild Suite 的六个端到端机器人应用上，Tartan 对遗留软件平均提升 1.2 倍；对经过针对性优化但不可近似的工作负载平均提升 1.61 倍；对允许近似的工作负载平均提升 2.11 倍，峰值可达 3.87 倍 [Bakhshalipour and Gibbons](cite:bakhshalipourTartanMicroarchitectingRobotic2024)。这一结果没有 Tigris 那样激进，但它说明另一个事实：如果目标是支撑更广的机器人软件栈，那么“适度专用 + 保留处理器通用性”比只追求单一内核极限更现实。

![Tartan 微架构三大创新：RPP、MME 与空间 KV Cache](figures/tartan-microarch.png)
<!-- caption: Tartan 处理器微架构支持示意图。该图用于说明机器人语义预取、面向小规模内核的计算支持和缓存层级协同的关系，不对应单一实验中的精确预取准确率、命中率或周期数。 -->
<!-- label: fig:tartan-microarch -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean publication-quality processor schematic, not photorealistic.
  Use consistent color mapping:
    deep blue #2B4C7E for compute/microarchitecture units,
    teal blue #3C7A89 for memory/cache hierarchy,
    orange #D17A22 for data path emphasis,
    dark green #5B8C5A for beneficial reuse/retained state,
    dark red #A23B2A for bottlenecks or baseline limitations,
    gray outlines and neutral blocks.
  Chinese-first labels, even 3-panel spacing, minimal clutter, academic annotation style.
  This figure is a conceptual microarchitecture illustration, not an exact implementation floorplan or benchmark plot.
  Three-panel microarchitecture diagram: Tartan's three innovations for robotic workloads.
  Left panel "机器人感知预取器 RPP (Robotic Perception Prefetcher)":
    CPU pipeline diagram showing L1/L2/L3 cache hierarchy.
    RPP unit shown as dedicated hardware block alongside standard prefetchers.
    Internal structure of RPP:
      "路径前缀哈希表 (Path Prefix Hash Table)" - 128-entry table mapping tree path prefixes to
      predicted next node addresses.
      History register showing last 4 KD-Tree traversal steps (binary: 0110...).
      Output "预取地址 (Prefetch Address)" sent to L1 cache.
    Comparison bar showing RPP higher than a generic prefetcher.
    Annotation: "追踪相邻点路径相关性 (tracks correlation between adjacent point paths)".
  Middle panel "微型矩阵引擎 MME (Micro Matrix Engine)":
    4×4 grid of FMA units (16 total), each labeled "FMA" in blue.
    Connections showing: input matrices A and B (3×3 highlighted in orange) flowing into FMA units.
    One-cycle-style completion arrow for small matrices.
    Below: list of supported operations for small-matrix robotic kernels.
    Comparison: show higher throughput than generic SIMD for small matrices.
  Right panel "空间 KV Cache (Spatial KV Cache)":
    KD-Tree visualized as full binary tree. Top 14 levels highlighted in green (KV Cache region).
    Below level 14: tree continues in gray labeled "DDR DRAM".
    Cache-hit annotation showing frequent reuse of top tree levels.
    Memory note indicating the top tree region fits into dedicated SRAM.
    Latency comparison showing large reduction when cache hits.
    Visualization of spatial locality: multiple robot positions (arrows) accessing same root nodes.
  Bottom: qualitative speedup bar chart showing Tartan above a generic ARM baseline.
  Label "ISCA 2024 robot workloads".
  Clean microarchitecture diagram style, white background, publication quality.
-->

### 5.3.3 PointISA：ISA 扩展的协同设计

PointISA [Han et al.](cite:hanPointISAISAextensionsEfficient2025) 继续向“保留软件生态”的方向推进。它不直接做整颗点云专用处理器，而是在现有 ISA 上增加点云相关原语，并配套统一硬件执行结构。

**核心思路**：PointISA 不把每个点云算法都做成独立加速器，而是把欧氏距离、多维排序等高频操作抽成 ISA 扩展，再把 FPS、kNN 等算法重写成能利用这些扩展的并行模式。

- ISA 层增加点云加载、距离计算和排序相关指令。
- 硬件层使用统一执行结构，同时支持这些扩展指令和常规矩阵乘法。
- 算法层把 FPS、kNN 等流程改写成多点对多点（MP2MP）模式，以提高并行利用率。

在 gem5 和 AArch64 基线上的评测中，PointISA 在多种点云工作负载上实现平均 5.4 倍加速和 4.9 倍能效提升，面积开销约 0.9\% [Han et al.](cite:hanPointISAISAextensionsEfficient2025)。这条路线的价值不在于单点极限性能，而在于它把“点云原语”纳入了处理器指令语义，因而更容易进入既有编译器和软件栈。

### 5.3.4 ASIC 设计的关键权衡

![三代机器人专用处理器架构演进](figures/asic-evolution.png)
<!-- caption: 机器人专用处理器架构三代演进对比示意。第一代（Tigris, MICRO'19）：算法-架构协同优化 KD-Tree 搜索，向量化搜索引擎 + bank-interleaved SRAM，聚焦点云配准单任务。第二代（Tartan, ISCA'24）：系统分析机器人 workload 特征，设计专用预取器 + 微型矩阵引擎 + KV Cache，覆盖感知-规划-控制全栈。第三代（PointISA, MICRO'25）：ISA 扩展路线，在 RISC-V 基础上增加点云专用指令，兼顾软件生态与专用加速，pdist/pknn/pcov 三类核心指令。横轴：泛化性（专用→通用），纵轴：峰值能效（高→低）。 -->
<!-- label: fig:asic-evolution -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, publication-quality conceptual evolution diagram.
  Use consistent color mapping:
    deep blue #2B4C7E for ASIC-centric stages,
    teal blue #3C7A89 for memory/system support emphasis,
    orange #D17A22 for transitional or hybrid designs,
    dark green #5B8C5A for retained software ecosystem or broader generality,
    dark red #A23B2A only for tradeoff emphasis,
    gray axes and labels.
  Chinese-first labels, strong alignment, restrained arrow styling.
  This figure is a conceptual evolution map, not a quantitative timeline with exact coordinates.
  Timeline evolution diagram of three generations of robot-specific processors for ICP/point cloud.
  Horizontal axis "泛化性 (Generality)" from left (专用 Specialized) to right (通用 General).
  Vertical axis "峰值能效 (Peak Energy Efficiency)" from bottom (低 Low) to top (高 High).
  Three positioned boxes with arrows showing progression:
    Box 1 "Tigris (MICRO'19)" top-left: dark blue, focused dot labeled "KD-Tree Search Only",
      annotation: "algorithm-architecture co-design for KD-Tree-dominated registration".
    Box 2 "Tartan (ISCA'24)" middle: medium blue, wider box labeled "Perception+Planning+Control",
      annotation: "robotic prefetching and small-kernel support".
    Box 3 "PointISA (MICRO'25)" upper-right: light blue/teal, wide box labeled "RISC-V + ISA Ext.",
      annotation: "point-cloud ISA extensions with software ecosystem preserved".
  Curved arrow connecting the three boxes showing evolution direction.
  Small icons for each: Tigris=chip die, Tartan=robot arm, PointISA=CPU with extension plug.
  Clean academic style, white background, publication quality.
-->

ASIC 设计面临三个核心权衡：

**1. 通用性 vs 效率**：Tigris 更接近“围绕单一热点深挖”的专用内核，PointISA 更接近“把热点下沉到 ISA 语义”，Tartan 则处在两者之间，试图为更广的机器人软件栈提供有限但持续的收益。实际选择取决于产品究竟追求单任务极限，还是追求较长的软件生命周期。

**2. 算法固定化风险**：只要硬件收益依赖特定搜索结构、数值表示或近似策略，芯片流片后就很难像 FPGA 那样继续调整。如果未来系统转向 [第 3.6 节](ref:sec:global-init) 之后的全局初始化或 [第 3.7 节](ref:sec:dl-icp) 的深度学习配准，专用搜索数据通路的价值会迅速下降。

**3. 开发成本与验证成本**：ASIC 不只贵在流片，还贵在前期验证、软件适配和量产前风险控制。对研究原型而言，这意味着 ASIC 更适合用来验证“已经足够稳定”的热点，而不是承载仍在快速变化的算法探索。

| 方案 | 路线定位 | 主要对象 | 代表机制 | 已报告结果 |
|------|---------|---------|---------|----------|
| Tigris [Xu et al.](cite:xuTigrisArchitectureAlgorithms2019) | 点云配准专用 ASIC | KD-Tree 搜索主导的点云配准 | 两阶段 KD-Tree + 近似搜索 + 向量化搜索引擎 | KD-Tree 搜索 77.2× 于 RTX 2080 Ti；端到端性能提升 41.7\%；功耗降 3.0× |
| Tartan [Bakhshalipour and Gibbons](cite:bakhshalipourTartanMicroarchitectingRobotic2024) | 机器人处理器微架构 | 感知、规划、控制混合工作负载 | 定向向量化、近似执行、机器人语义预取、缓存分区 | 遗留软件 1.2×；不可近似工作负载 1.61×；可近似工作负载 2.11×，峰值 3.87× |
| PointISA [Han et al.](cite:hanPointISAISAextensionsEfficient2025) | ISA 扩展 + 统一执行结构 | 多类点云分析工作负载 | 点云原语 ISA 扩展 + MP2MP 算法改写 | 平均 5.4× 加速、4.9× 能效提升；面积开销约 0.9\% |
| Multi-mode SA-RPS-CS FPGA [Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025) | 可重配置对照路线 | 64 线 LiDAR 配准 | SA-RPS + 多模式搜索 | 21.5 FPS；搜索 2.3--32.4× 加速；能效 1.8--26.2× 提升 |
<!-- caption: 第 5.3 节专用处理器路线与可重配置对照路线汇总。表中只保留论文明确报告的定位、机制和结果，不对不同论文的延迟、工艺或功耗做未经统一条件校准的硬性排序。 -->
<!-- label: tab:asic-comparison -->

综合来看，ASIC 路线的真正价值不在于“任何指标都比 FPGA 高”，而在于它可以围绕已经稳定的热点建立更紧的存储和执行耦合。代价是算法一旦切换，硬件复用空间会迅速收缩。[第 5.4 节](ref:sec:pim)将继续讨论另一条不同的路线：不再优先重写执行核心，而是把距离计算和候选维护尽量推入存储阵列，以直接处理带宽墙问题。
