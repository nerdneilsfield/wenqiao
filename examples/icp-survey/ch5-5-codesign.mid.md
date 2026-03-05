## 5.5 算法-硬件协同设计方法论 (Algorithm-Hardware Co-design Methodology)

<!-- label: sec:codesign -->

[第 5.2 节](ref:sec:fpga) 到 [第 5.4 节](ref:sec:pim) 展示的几条路线虽然器件形态不同，但真正决定收益的并不只是硬件本身，而是算法是否愿意为硬件让渡一部分自由度。本节不再追求给出统一分数或统一坐标，而是把前文已经核实过的工作归纳为几类常见的协同设计动作，说明这些动作在什么条件下成立，又会把风险转移到哪里。

### 5.5.1 协同设计的三层框架

从前文案例出发，协同设计大致可以分成三个层次：

**层次一：数值与数据组织适配**
在这一层，算法目标函数并不改变，修改集中在表示形式和存储布局上。例如，固定点量化让 [Liu et al.](cite:liuEnergyEfficientRuntime2023) 和 [Liu et al.](cite:liuHABFNNICPStreamingFPGA2025a) 能把更多算子塞进目标芯片；而将目标点云或索引结构长期保留在片上缓存，则使 [第 5.2 节](ref:sec:fpga) 中的多条 FPGA 流水线可以减少反复的片外访问。这一层的优点是改动相对保守，风险集中在量化误差和边界数据范围是否可控。

**层次二：搜索流程改写**
当仅靠数值和布局仍不足以支撑硬件吞吐时，研究者会开始改写最近邻搜索本身的执行流程。Tigris 用两阶段 KD-Tree 与近似搜索挖掘查询级和节点级并行 [Xu et al.](cite:xuTigrisArchitectureAlgorithms2019)；PointISA 把点云原语下沉到 ISA，并将 FPS、kNN 改写成 MP2MP 模式 [Han et al.](cite:hanPointISAISAextensionsEfficient2025)；PICK 则把距离计算和 Top-$k$ 搜索表达成阵列友好的 bit-serial 流程 [Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025)。这一层的核心收益来自“减少真正昂贵的查询和搬运”，代价是软件实现与经典算法流程开始出现可见偏离。

**层次三：搜索结构替换**
收益最大的一类协同设计，经常来自直接更换搜索结构或候选生成方式。RPS 和 SA-RPS 利用有组织 LiDAR 的扫描线拓扑，把随机树遍历替换成局部窗口搜索 [Sun et al.](cite:sunRealtimeFPGABasedPoint)[Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025)；HA-BFNN-ICP 进一步接受规则扫描和阈值筛选，以换取稳定的流式吞吐 [Liu et al.](cite:liuHABFNNICPStreamingFPGA2025a)；C²IM-NN 则把搜索改写成 CAM 相似匹配与区域预测的组合 [Shin et al.](cite:shin2IMNN2025)。这一层的风险也最直接：一旦输入点云不再满足结构化拓扑、候选分布不再受控，或区域预测失准，收益会首先回落。

![算法-硬件协同设计三层框架与代表案例映射](figures/codesign-three-layers.png)
<!-- caption: 算法-硬件协同设计三层框架示意图。该图用于说明“表示适配、流程改写、结构替换”三类动作与代表系统之间的关系，不对应统一基准下的精确加速比和误差坐标。 -->
<!-- label: fig:codesign-three-layers -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean academic conceptual diagram, not poster-like.
  Use consistent color mapping:
    deep blue #2B4C7E for compute-centric actions,
    teal blue #3C7A89 for memory/data-layout actions,
    orange #D17A22 for search-flow rewriting,
    dark green #5B8C5A for retained valid design regions,
    dark red #A23B2A for risk/tradeoff callouts,
    grays for axes and neutral blocks.
  Chinese-first labels, strict hierarchy, even spacing, minimal visual noise.
  This figure is a conceptual framework illustration, not a quantitative scoring plot.
  Conceptual three-layer algorithm-hardware co-design diagram for ICP.
  Show three horizontal bands:
    Layer 1 for numeric/data-layout adaptation,
    Layer 2 for search-flow rewriting,
    Layer 3 for search-structure replacement.
  Place representative examples qualitatively inside each layer without exact numbers.
  Add side notes for typical risks:
    "量化误差边界",
    "软件接口改写",
    "输入结构依赖".
  Clean framework diagram style, white background, publication quality.
-->

### 5.5.2 协同设计的评估原则

协同设计不适合用一个统一公式打分，因为不同论文的场景、数据规模、基线和功耗测量方式都不同。更稳妥的做法，是沿着四个问题逐项核验：

1. **算法是否真的改写了瓶颈**：如果改动没有触及对应搜索、候选筛选或数据搬运，硬件收益通常只会停留在局部算子。
2. **精度损失是否在原始论文中被显式报告**：例如 Tigris、RPS、HA-BFNN-ICP、C²IM-NN 都给出了各自场景下的精度或召回边界；没有核实的数据不应被横向拼接。
3. **硬件收益是否来自统一口径的指标**：有的论文报告子过程加速，有的报告端到端帧率，有的报告能效或面积开销。只有指标口径一致时，比较才有意义。
4. **系统代价是否被单独说明**：包括重配置开销、更新路径、接口同步、量化误差和校准复杂度。若这些代价被省略，局部加速往往无法转化为系统收益。

### 5.5.3 典型收益与典型代价

把前文工作放在一起看，可以得到几条较稳定的结论：

- 若输入点云存在扫描线或结构化拓扑，直接利用这种结构比继续优化通用树遍历更划算，[Sun et al.](cite:sunRealtimeFPGABasedPoint) 和 [Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025) 都属于这一类。
- 若目标平台更在意稳定吞吐而不是算法形式保真，规则扫描和阈值筛选会比复杂索引更容易映射到硬件，[Liu et al.](cite:liuHABFNNICPStreamingFPGA2025a) 和 [Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025) 体现了这一点。
- 若系统仍需要较强的软件通用性，就需要把协同设计限制在处理器接口层或 ISA 层，[Bakhshalipour and Gibbons](cite:bakhshalipourTartanMicroarchitectingRobotic2024) 与 [Han et al.](cite:hanPointISAISAextensionsEfficient2025) 都更接近这种路线。

对应的代价同样明确：

- 结构化搜索依赖输入点云的组织形式。
- 定点化和近似搜索依赖误差边界可控。
- PIM 和模拟匹配依赖阵列友好的数据表达以及更复杂的更新、校准与接口设计。

![协同设计 Pareto 前沿分析](figures/codesign-pareto.png)
<!-- caption: 协同设计中“收益与代价并存”的概念示意图。该图用于说明不同路线在延迟、误差、灵活性之间的相对关系，不对应统一实验条件下的精确 Pareto 前沿。 -->
<!-- label: fig:codesign-pareto -->
<!-- width: 0.85\textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean academic conceptual chart.
  Use the same chapter-wide color mapping and keep all comparisons qualitative rather than numeric.
  Chinese-first labels, restrained legend, balanced whitespace.
  This figure is a conceptual tradeoff map, not a true Pareto frontier.
  Conceptual tradeoff diagram for ICP algorithm-hardware co-design.
  X-axis "系统灵活性 (System Flexibility)" from low to high.
  Y-axis "局部热点收益 (Hotspot Benefit)" from low to high.
  Place families of approaches qualitatively:
    FPGA structured-search methods in the middle,
    ASIC hotspot-specific designs in high-benefit low-flexibility region,
    ISA-extension and robotic-processor approaches in medium-benefit medium/high-flexibility region,
    PIM approaches in high-benefit low/medium-flexibility region.
  Add callouts for "输入结构依赖", "量化/近似误差边界", and "更新与接口成本".
  Clean academic style, white background, publication quality.
-->

![PointISA 专用指令流水线与周期数分析](figures/pointisa-instructions.png)
<!-- caption: PointISA 点云专用指令与通用指令序列之间关系的机制示意图。该图用于说明“把点云原语提升到 ISA 层”这一思路，不对应统一实验条件下的精确周期数或整体 ICP 加速比。 -->
<!-- label: fig:pointisa-instructions -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean academic ISA/pipeline schematic.
  Use consistent color mapping:
    deep blue #2B4C7E for instruction execution units,
    teal blue #3C7A89 for register/memory support,
    orange #D17A22 for data flow and reduction paths,
    dark green #5B8C5A for retained software ecosystem emphasis,
    dark red #A23B2A for baseline overhead,
    gray outlines and labels.
  Chinese-first labels, strong panel alignment, minimal clutter.
  This figure is a conceptual ISA illustration, not an exact cycle-accurate benchmark chart.
  Three-panel instruction concept diagram: PointISA custom instructions vs standard RISC-V.
  Left panel:
    Show a compact point-distance instruction pipeline and a longer generic instruction sequence below it.
  Middle panel:
    Show multi-lane candidate processing followed by a tree-style reduction for point-cloud search primitives.
  Right panel:
    Summarize four instruction categories: point load/store, distance, KNN step, covariance accumulation.
    Highlight preserved software ecosystem and reduced instruction overhead.
  Clean CPU pipeline/ISA diagram style, white background, publication quality.
-->

### 5.5.4 仍待解决的问题

**深度学习与经典 ICP 的统一支持**：[第 3.7 节](ref:sec:dl-icp) 中的深度学习配准引入了与经典 ICP 不同的计算图。如何在不牺牲经典 ICP 时延优势的前提下，同时支持这些新算子，仍缺少成熟答案。

**动态场景下的在线更新**：动态数据结构和增量地图维护对 FPGA、ASIC 和 PIM 都是难点。当前多数工作更擅长处理静态或半静态搜索结构，而不擅长高频更新。

**异构集成后的系统边界**：即使未来平台能把 CPU、可重配置逻辑和近存储阵列放进更紧的封装，更新路径、接口协议、热设计和软件调度仍然需要单独解决。器件更近，并不自动等于系统更简单。

| 协同动作 | 代表工作 | 直接收益 | 主要约束 |
|---------|---------|---------|---------|
| 数值与布局适配 | Runtime Reconfigurable Localization、HA-BFNN-ICP | 降低资源占用，提升片上驻留比例 | 量化范围、误差边界、资源预算 |
| 搜索流程改写 | Tigris、PointISA、PICK | 减少昂贵查询与数据搬运 | 需要重写算法执行流程和软件接口 |
| 搜索结构替换 | RPS、SA-RPS、HA-BFNN、C²IM-NN | 最大化规则访问和阵列友好执行 | 强依赖输入结构、候选分布或预测准确性 |
<!-- caption: 第 5.5 节协同设计动作与代表工作汇总。表中强调“改了什么”和“换来了什么”，不把不同论文的异构指标强行压缩成单一分数。 -->
<!-- label: tab:codesign-comparison -->

综上，算法-硬件协同设计并不是一句口号，而是一组必须被明确写出来的交换条件：为了换取更低延迟或更高能效，算法究竟让出了哪些自由度，硬件又因此获得了哪些可利用的规则性。只要这些交换条件没有被讲清楚，所谓“硬件加速”就很容易退化成不可复现的局部结果。
