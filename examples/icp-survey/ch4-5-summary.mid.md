### 4.5 本章小结

<!-- label: sec:software-summary -->

本章的结论可以归纳为两点。其一，软件加速首先是“约束重分配”而不是“单纯提速”。[第 4.1 节](ref:sec:data-structure) 说明索引结构必须与地图更新频率一起考虑：FAST-LIO2 之所以能在 19 个公开序列上稳定运行，并在大场景达到 100 Hz、在 1000 deg/s 旋转条件下保持估计，是因为它把直接配准、增量更新和树上降采样放进了同一个 ikd-Tree 框架 [Xu et al.](cite:xuFASTLIO2FastDirect2022)。如果场景持续变化而索引仍依赖整树重建，那么查询开销还未成为瓶颈之前，索引维护就会先失控。其二，采样策略只有在“保留约束”这一条件下才成立。Pomerleau 等在六类真实场景上的评测给出了一个直接对照：点到面 ICP 的精度高于点到点约 20\%--40\%，但点到点速度约快 80\%，说明减少计算量与保留有效几何约束始终处于拉扯关系 [Pomerleau et al.](cite:pomerleauComparingICPVariants2013)。Gelfand 等提出的几何稳定采样进一步把这种关系写成了条件数优化问题：当采样集中在特征贫乏区域时，先退化的是姿态约束矩阵，后果是收敛变慢甚至滑移到错误姿态 [Gelfand et al.](cite:gelfandGeometricallyStableSampling2003)。

降采样、并行化和 ANN 的作用边界也应分开看待。EA2D-LSLAM 在 KITTI 与 M2DGR 上把后端时间从 95 ms 压到 68 ms，是因为它用 Hessian 分解估计体素对位姿约束的贡献，而不是均匀删点 [Sun et al.](cite:sunEA2DLSLAMEnvironmentAnalysisbased2025)。近似搜索同样依赖误差预算是否可控：[第 4.4 节](ref:sec:approx-nn) 中的 FLANN 适合低维点云或中等维度描述子，HNSW 则补上了高召回图索引这一环节，但其原始实验对象是 SIFT、GloVe、MNIST 等向量检索任务，因此迁移到 ICP 时仍需重新核实三维点云上的召回率与延迟 [Malkov and Yashunin](cite:malkovEfficientRobustApproximate2020)。因此，本章更稳妥的结论是：软件优化已经给出了实时 ICP 的主要方法库，但每一类方法都绑定了明确的场景条件。下一章讨论硬件加速时，应把这些条件带入架构设计，而不是把软件测得的速度直接外推到 FPGA 或 ASIC。
