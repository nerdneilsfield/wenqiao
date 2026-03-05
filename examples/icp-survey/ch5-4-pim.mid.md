## 5.4 近存储计算（PIM）(Processing-in-Memory)

<!-- label: sec:pim -->

[第 5.2 节](ref:sec:fpga)和 [第 5.3 节](ref:sec:asic) 展示了两种思路：要么重写搜索结构并围绕其建立流水线，要么把已经稳定的搜索热点固化进专用处理器。PIM 采取的切入点不同。它默认“数据搬运本身就是瓶颈”，因此不优先继续强化执行核心，而是把距离计算、候选筛选和 Top-$k$ 维护尽量推向存储阵列附近。

### 5.4.1 内存带宽墙与 PIM 的动机

PIM 研究的出发点是，点云 kNN 和对应搜索包含大量“取数据、做少量比较、更新候选”的短链路操作。对这类负载而言，外部存储带宽和访问时延经常先于算术吞吐量成为限制因素。[Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025) 直接把点云 kNN 的主要挑战概括为“计算强度高且内存需求大”；[Shin et al.](cite:shin2IMNN2025) 也把设计重点放在减少存储占用和提升能效，而不是继续堆叠通用计算核心。换句话说，PIM 关心的不是“每次距离计算有多复杂”，而是“为了完成这些距离计算，系统需要搬多少数据”。

因此，PIM 的价值不应被理解为某个统一倍数的加速，而应理解为一种新的瓶颈转移方式：只要距离比较和候选维护能够在阵列内部完成，外部总线就不再承担全部数据往返，系统瓶颈会从“搬数据”转向“阵列内部如何组织并行计算”。

### 5.4.2 PICK：SRAM-PIM 加速 KNN 搜索

PICK [Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025) 是面向点云 kNN 搜索的 SRAM-PIM 代表工作之一，重点展示了如何把距离计算和 Top-$k$ 维护压进 SRAM 阵列。

**架构设计**：PICK 基于 BS-PIM（Bit-Serial Processing-in-Memory）原理：在 6T SRAM 阵列的每列末端添加 1 位加法器（adder cell），使 SRAM 可以在不读出数据的情况下，在片内逐位执行加法运算。KNN 搜索中的距离计算被分解为逐位的"bit-serial 乘加"操作：

$$
d^2 = \sum_{k=1}^{3}(p_k - q_k)^2 = \sum_{b=0}^{B-1} 2^b \cdot \text{PopCount}(P_{k,b} \oplus Q_{k,b})
$$
<!-- label: eq:bit-serial-dist -->

其中 $B$ 为量化位宽，$P_{k,b}$ 和 $Q_{k,b}$ 为坐标第 $b$ 位的二进制值，PopCount 由片内硬件完成。通过这种方式，候选点的距离计算不再要求把全部数据先搬到外部计算单元，再回写结果。

**自定义电路优化**：PICK 的设计重点不是单个阵列单元，而是三类配套机制：
1. **位宽裁剪**：在保证精度影响可控的前提下减少 bit-serial 计算长度。
2. **筛选与选择策略**：让任意 $k$ 值下的 Top-$k$ 搜索保持接近常数时间复杂度。
3. **两级流水线**：把距离计算和 Top-$k$ 搜索并行化，以隐藏一部分阵列内部时延。

**性能结果**：在 KITTI、SONN、S3DIS 和 DALES 等真实点云数据上，PICK 相对前一代代表设计达到 4.17 倍加速和 4.42 倍节能 [Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025)。这一结果说明，若 kNN 可以被表述成适合 bit-serial 阵列执行的形式，PIM 的收益会直接体现在能效和数据搬运缩减上。它的前提是坐标表示和搜索流程都要适配阵列执行方式；如果算法需要频繁动态更新复杂索引，收益会先被更新成本吞掉。

![PICK SRAM-PIM 逐位距离计算与早停电路详解](figures/pick-bit-serial.png)
<!-- caption: PICK 的 bit-serial 阵列执行与候选筛选机制示意图。该图用于说明阵列内距离计算、位宽裁剪和候选维护之间的关系，不对应单一实验中的精确时延分解或每列候选规模。 -->
<!-- label: fig:pick-bit-serial -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean circuit-style academic schematic, not photorealistic.
  Use consistent color mapping:
    deep blue #2B4C7E for compute/comparison logic,
    teal blue #3C7A89 for memory arrays,
    orange #D17A22 for data/query flow,
    dark green #5B8C5A for retained/selected candidates,
    dark red #A23B2A for terminated/pruned candidates,
    gray outlines and support text.
  Chinese-first labels, strict 3-panel layout, rounded annotation boxes, crisp circuit arrows.
  This figure is a conceptual circuit/mechanism illustration, not a transistor-accurate or timing-accurate plot.
  Three-panel detailed concept diagram: PICK-style SRAM-PIM bit-serial KNN computation.
  Left panel "6T SRAM 阵列 (SRAM Array with PIM Cells)":
    Show an SRAM array, per-column bit-serial logic, and in-place accumulation.
    Emphasize that candidate comparison happens inside the array.
  Middle panel "逐位距离计算 (Bit-Serial Distance Computation)":
    Show a broadcast query bit, local XOR/comparison, population count, and accumulation.
    Indicate repeated bit-serial steps without exact cycle counts.
  Right panel "早停电路 (Early Termination Circuit)":
    Show partial sums being compared against a running threshold and some candidates terminating early.
    Add a small qualitative latency comparison inset for baseline vs optimized PIM execution.
  Clean circuit/VLSI diagram style, white background, publication quality.
-->

### 5.4.3 C²IM-NN：CAM-PIM 与 CNN 预测协同

C²IM-NN [Shin et al.](cite:shin2IMNN2025) 采取了与 PICK 不同的路线：不是在 SRAM 阵列里做 bit-serial 计算，而是利用 CAM 的相似匹配特性，把查询过程表达成“在存储阵列中直接找最相近的内容”。

**CAM-PIM KNN 原理**：论文用模拟 CAM 表达近似相似度搜索，让每个存储单元直接参与“查询点与存储点有多接近”的比较，再由片内电路输出候选结果。这样做的目的，是继续减少数字域中的显式数据搬运和逐点比较。

**1D-CNN 预测剪枝**：C²IM-NN 的另一层改写来自搜索前的区域预测。论文用轻量级 1D-CNN 先预测查询更可能落在哪个区域，再让 CAM 只在该区域内执行相似匹配。这样做的前提是区域预测本身足够轻，同时误判率不能把后续搜索精度拖垮。

**性能结果**：在 28 nm CMOS 验证下，C²IM-NN 相对之前的 ASIC 加速器达到 23.08 倍能效提升，并减少 48.4\% 存储占用 [Shin et al.](cite:shin2IMNN2025)。这一结果说明，若允许引入模拟匹配和预测剪枝，PIM 的收益可以继续扩大；但代价是设计会明显更依赖工艺、校准和可靠性控制。

![C²IM-NN CAM 模拟搜索与 1D-CNN 预测剪枝流程](figures/c2im-cnn-pruning.png)
<!-- caption: C²IM-NN 的 CAM 搜索与预测剪枝协同示意图。该图用于说明模拟匹配、区域预测和系统流水线之间的关系，不对应单一实验中的精确预测准确率、模拟延迟或总帧时延。 -->
<!-- label: fig:c2im-cnn-pruning -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean academic mixed analog/digital schematic.
  Use consistent color mapping:
    deep blue #2B4C7E for compute/control modules,
    teal blue #3C7A89 for CAM/storage arrays,
    orange #D17A22 for query/data flow,
    dark green #5B8C5A for selected candidate regions,
    dark red #A23B2A for discarded search space,
    gray outlines and neutral support blocks.
  Chinese-first labels, balanced 3-panel composition, minimal clutter.
  This figure is a conceptual system illustration, not a measured timing/energy chart.
  Three-panel system concept diagram: C²IM-NN dual-module architecture (CAM-PIM + 1D-CNN pruning).
  Left panel "模拟 CAM 搜索 (Analog CAM Search)":
    Show an analog CAM array performing similarity-style matching in place.
    Emphasize direct matching inside the memory array.
  Middle panel "1D-CNN 预测剪枝 (1D-CNN Candidate Pruning)":
    Show a lightweight 1D-CNN receiving local features and selecting one likely search region.
    Emphasize reduced candidate region rather than exact partition counts.
  Right panel "系统流水线 (System Pipeline)":
    Show prediction and CAM search as two coordinated stages.
    Add a qualitative inset for reduced energy and storage overhead.
  Clean mixed analog/digital circuit and system diagram style, white background, publication quality.
-->

### 5.4.4 PIM 在 ICP 系统中的集成挑战

尽管 PIM 在 KNN 搜索上性能出色，将其集成到完整 ICP 系统仍面临工程挑战：

**1. 点云更新问题**：ICP 每帧都会引入新的查询点云，而建图系统中的目标点云也可能增量更新。PIM 若要保持高收益，就需要控制这些写入和重组织成本，否则阵列内部节省的数据搬运会被更新代价抵消。对增量维护问题，可参考 [第 4.1 节](ref:sec:data-structure) 的动态数据结构思路，但如何把它们映射到 PIM 友好的更新路径仍未定型。

**2. 稀疏访问模式**：PIM 阵列更喜欢规则、成批的并行访问，而标准树遍历带有大量随机跳转。要让 PIM 真正发挥作用，算法经常需要先把搜索流程改写成阵列友好的形式。

**3. 与主控处理器的接口**：即便核心搜索已经下沉到阵列内部，系统仍要处理查询下发、结果回读和控制同步。接口协议和 DMA 调度没有处理好，PIM 的阵列收益仍可能在系统边界被吞掉。

![PIM 架构原理与 PICK/C²IM 对比](figures/pim-architecture.png)
<!-- caption: 传统存储架构、SRAM-PIM 与 CAM-PIM 的机制对比示意。该图用于说明“外部搬运主导”与“阵列内部执行主导”两类路线的差异，不对应统一实验条件下的精确带宽或能效坐标。 -->
<!-- label: fig:pim-architecture -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Unified academic publication figure style.
  White background, flat vector illustration, clean publication-quality comparison schematic.
  Use consistent color mapping:
    deep blue #2B4C7E for compute units,
    teal blue #3C7A89 for memory arrays,
    orange #D17A22 for data movement,
    dark green #5B8C5A for near-data execution benefits,
    dark red #A23B2A for bandwidth bottlenecks,
    gray outlines and labels.
  Chinese-first labels, strict 3-panel alignment, simple legend, rounded blocks.
  This figure is a conceptual architecture comparison, not a quantitative bandwidth or GFLOPs/W chart.
  Three-panel comparison diagram of memory architectures for KNN search acceleration.
  Left panel "传统架构 (Traditional)":
    Show CPU and external DRAM connected by a narrow bandwidth bottleneck.
    Emphasize data movement dominating execution.
  Middle panel "PICK (SRAM-PIM)":
    Show an SRAM array with in-memory comparison and top-k logic.
    Emphasize computation near data.
  Right panel "C²IM-NN (CAM-PIM)":
    Show a CAM-based in-memory matcher with an attached CNN pruning block.
    Emphasize further reduction in candidate set and data movement.
  Bottom: qualitative energy-efficiency comparison among the three styles.
  Clean academic style, white background, publication quality.
-->

### 5.4.5 PIM 方案综合对比

| 方案 | PIM 类型 | 主要机制 | 已报告结果 | 主要代价 |
|------|---------|---------|----------|--------|
| PICK [Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025) | SRAM bit-serial PIM | 阵列内距离计算 + 位宽裁剪 + 两级流水线 | 4.17× 加速，4.42× 节能 | 需要让 kNN 流程适配 bit-serial 执行与片上存储组织 |
| C²IM-NN [Shin et al.](cite:shin2IMNN2025) | CAM-based PIM | 模拟相似匹配 + 1D-CNN 预测剪枝 | 23.08× 能效提升，48.4\% 存储占用下降 | 更依赖模拟电路设计、工艺校准和系统可靠性控制 |
<!-- caption: 第 5.4 节 PIM 代表方案汇总。表中仅保留论文明确报告的机制与结果，不对不同实现的总时延和工艺可迁移性做未经验证的统一排序。 -->
<!-- label: tab:pim-comparison -->

PIM 的意义在于提供了一种不同于 FPGA 和 ASIC 的问题重述方式：如果带宽墙才是主瓶颈，那么就不必先从执行核心下手，而可以先改变数据与计算的相对位置。它的工程门槛同样明显，包括更新路径、接口协议和阵列友好型算法表达。[第 5.5 节](ref:sec:codesign)将把 [第 5.2 节](ref:sec:fpga) 到本节的几条路线放到同一共设计框架下，讨论哪些算法改写值得换取硬件收益。
