## 5. 硬件加速：FPGA、ASIC 与近存储计算

<!-- label: sec:hardware-accel -->

第 4 章已经说明，软件侧的并行化、数据结构重排和近似搜索能够明显压缩 ICP 延迟，但瓶颈并未消失，而是集中暴露在最近邻搜索的数据访问阶段。以自动驾驶 LiDAR 配准为例，[Xu 等](cite:xuTigrisArchitectureAlgorithms2019)在 KITTI 上比较多种设计点后指出，KD-Tree 搜索始终主导运行时间；其专用处理器 Tigris 在同一任务上将 KD-Tree 子过程相对 RTX 2080 Ti 的速度提升到 77.2 倍，同时把功耗降为后者的约 $1/7.4$。这一现象并不限于 ASIC：面向高吞吐点云 kNN 的 HBM-FPGA 原型 ParallelNN 在 KITTI 上相对 CPU 和 GPU 分别达到 107.7 倍和 12.1 倍加速，能效增益分别达到 73.6 倍和 31.1 倍 [Chen 等](cite:chenParallelNNParallelOctreebased2023a)。这些结果共同指向同一问题：当访问模式仍由随机树遍历主导时，性能上限更多受片外带宽和数据搬运限制，而不是受浮点算力限制。

因此，本章关注的不是“把同一套软件再移植一遍”，而是分析不同硬件路线如何改写最近邻搜索的实现前提。FPGA 路线通过重排数据组织，把随机访问改成适合流水线的规则访问：RPS-ICP 面向有组织车载 LiDAR 点云，在对应搜索阶段达到 18.6 FPS，对应搜索速度比既有 FPGA 实现快 13.7 倍，能效比 GPU 高 50.7 倍 [Sun 等](cite:sunRealtimeFPGABasedPoint)；HA-BFNN-ICP 在 3.4 W 功耗约束下，对 3D LiDAR 建图任务取得相对 CPU 17.36 倍加速 [Liu 等](cite:liuHABFNNICPStreamingFPGA2025a)。ASIC 路线则把 KD-Tree 搜索和小矩阵算子直接固化到专用数据通路中，以换取更低的控制开销和更高的单位能效 [Xu 等](cite:xuTigrisArchitectureAlgorithms2019)。PIM 路线继续向存储侧推进：PICK 在 KITTI、S3DIS、DALES 等数据集上的 kNN 搜索，相对此前设计实现 4.17 倍加速和 4.42 倍节能 [Nie 等](cite:niePICKSRAMbasedProcessinginmemory2025)；C²IM-NN 在 28 nm CMOS 上把 CAM 搜索与 1D-CNN 预测结合，报告了 23.08 倍能效提升和 48.4\% 存储占用下降 [Shin 等](cite:shin2IMNN2025)。这些工作之间的差别，不只在器件类型，还在于它们分别接受了哪些算法改写、数据格式约束和精度折中。

基于上述观察，本章按“瓶颈分析、平台路线、协同方法”三层展开。[第 5.1 节](ref:sec:hardware)首先从最近邻搜索的访存特征出发，量化通用处理器在带宽、缓存命中率和能效上的限制，并建立硬件设计空间。[第 5.2 节](ref:sec:fpga)讨论 FPGA 如何通过流式缓存、规则化搜索结构和运行时可重配置机制压缩延迟，但也指出这一路线对点云组织形式、片上存储容量和定点量化较为敏感。[第 5.3 节](ref:sec:asic)分析专用处理器怎样用固定数据通路换取极低延迟，同时说明算法一旦切换，其硬件复用空间会迅速收缩。[第 5.4 节](ref:sec:pim)进一步讨论把距离计算和 Top-$k$ 维护推入存储阵列后的收益与代价，重点说明哪一类带宽瓶颈可以被消除、哪一类可靠性和工艺问题会先暴露。[第 5.5 节](ref:sec:codesign)最后回到算法-硬件协同设计，整理数据结构替换、低精度表示和固定时延执行三类共设计策略，并据此归纳后续系统选型所需的判断标准。
