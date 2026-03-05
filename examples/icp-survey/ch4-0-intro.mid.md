## 4. 软件加速：数据结构、降采样与近似算法

<!-- label: sec:software -->

第 3 章讨论了 ICP 在目标函数、对应筛选和初始化策略上的改进，但这些变体仍共享同一计算核心：在目标点云 $\mathcal{Q}$ 中为源点云 $\mathcal{P}$ 的每个点搜索对应邻域。Pomerleau 等在六类真实场景上的公开评测表明，ICP 的配准表现不仅受误差模型影响，也直接受输入点数、采样方式和查询实现约束；在相同实验协议下，点到面变体的精度比点到点高约 20\%--40\%，但点到点实现的运行速度约快 80\% [Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。由此可见，软件实现并非附属问题，而是决定 ICP 是否能进入实时预算的前提条件。

本章转向软件实现层面的四条主线。[第 4.1 节](ref:sec:data-structure) 比较 KD-Tree、体素哈希、Octree 与增量索引的适用边界，并以 FAST-LIO2 的 ikd-Tree 为例说明动态地图维护为何必须与近邻查询一并设计；该系统在 19 个公开序列上完成评测，在大场景中达到 100 Hz，并在最高 1000 deg/s 的旋转条件下仍能给出稳定状态估计 [Xu et al.](cite:xuFASTLIO2FastDirect2022)。[第 4.2 节](ref:sec:downsampling) 讨论降采样如何改变信息密度分布，而不仅是减少点数；其中 EA2D-LSLAM 在 KITTI 和 M2DGR 上将后端运行时间从 95 ms 降到 68 ms，前提是按体素信息矩阵保留对位姿约束更强的区域 [Sun et al.](cite:sunEA2DLSLAMEnvironmentAnalysisbased2025)。[第 4.3 节](ref:sec:parallelism) 分析 SIMD、多线程与 GPU 的分工关系，[第 4.4 节](ref:sec:approx-nn) 则讨论近似最近邻的误差容忍机制，并补入 HNSW 这类图索引在高召回近似搜索中的桥接作用 [Malkov and Yashunin](cite:malkovEfficientRobustApproximate2020)。本章的目标不是罗列优化技巧，而是说明这些策略各自依赖什么场景假设，以及在什么条件下会先失效。
