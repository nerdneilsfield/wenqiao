### 5.6 本章小结

<!-- label: sec:hardware-summary -->

硬件加速的根本动机，在于点云对应搜索和 kNN 查询会把系统瓶颈推向数据访问侧，而不是继续停留在通用算术吞吐上。本章沿 FPGA、ASIC 与 PIM 三条路线展开，实际讨论的都是同一个问题：为了减少随机访存和数据搬运，算法愿意让出哪些自由度，硬件又因此获得了哪些可利用的规则性。

[第 5.2 节](ref:sec:fpga) 表明，可重配置逻辑的优势不只是“把搜索做快”，而是允许研究者围绕具体输入结构重写搜索流程：RPS 和 SA-RPS 利用扫描线拓扑把随机搜索改成局部窗口搜索 [Sun et al.](cite:sunRealtimeFPGABasedPoint)[Deng et al.](cite:dengEnergyefficientRealtimeFPGA2025)，HA-BFNN-ICP 则接受规则扫描与阈值筛选以换取稳定流式吞吐 [Liu et al.](cite:liuHABFNNICPStreamingFPGA2025a)。[第 5.3 节](ref:sec:asic) 说明，若热点已经足够稳定，专用处理器可以把这种协同进一步固化：Tigris 围绕 KD-Tree 搜索建立两阶段搜索和向量化数据通路 [Xu et al.](cite:xuTigrisArchitectureAlgorithms2019)，Tartan 与 PointISA 则分别在处理器微架构层和 ISA 层保留了更强的软件通用性 [Bakhshalipour and Gibbons](cite:bakhshalipourTartanMicroarchitectingRobotic2024)[Han et al.](cite:hanPointISAISAextensionsEfficient2025)。[第 5.4 节](ref:sec:pim) 进一步把问题改写为“怎样减少搬运本身”：PICK 用 SRAM bit-serial 阵列压低 kNN 的搬运成本 [Nie et al.](cite:niePICKSRAMbasedProcessinginmemory2025)，C²IM-NN 则把 CAM 相似匹配和区域预测结合起来继续扩大量效收益 [Shin et al.](cite:shin2IMNN2025)。[第 5.5 节](ref:sec:codesign) 的总结因此可以归结为一句话：收益最高的硬件加速，几乎都伴随着搜索结构、数值表示或数据组织的同步改写。

从 [第 4 章](ref:sec:software) 的软件优化到本章的专用硬件设计，ICP 的工程问题已经不再只是“能不能算完”，而是“为了在目标平台上算完，需要先改哪些算法前提”。这一点也决定了后续评测不能只看局部算子。第 6 章将转向应用与基准，讨论这些硬件和算法选择在具体场景里该如何比较、如何取舍。
