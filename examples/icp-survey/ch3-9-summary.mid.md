## 3.9 本章小结
<!-- label: sec:variants-summary -->

本章将 ICP 视为“可替换模块的迭代流水线”并据此组织变体：[第 3.1 节](ref:sec:correspondence) 通过改变度量与约束形态提升对应质量（从 P2P/P2Pl 到 NDT 与语义引导）[Pomerleau et al.](cite:pomerleauReviewPointCloud2015)；[第 3.2 节](ref:sec:outlier) 通过截断估计、鲁棒核与图论筛选增强外点鲁棒性（如 TrICP、Sparse ICP、SUCOFT）[Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002)；[第 3.3 节](ref:sec:convergence) 则在“已处于正确盆地”的前提下，通过 Anderson 加速与 MM/GNC 框架降低迭代成本并稳定优化轨迹 [Pavlov et al.](cite:pavlovAAICPIterativeClosest2017)；[第 3.4 节](ref:sec:transform) 回顾了从闭式解到概率化估计的变换更新策略（如 Horn/Kabsch 型解法、GICP、Stein ICP），强调参数化选择与不确定性建模会直接影响数值稳定性与收敛行为 [Horn](cite:hornClosedformSolutionAbsolute1987)。

与“单帧、局部、几何最小二乘”的经典设定相比，[第 3.5 节](ref:sec:degeneracy)至[第 3.8 节](ref:sec:opt-solvers) 进一步把 ICP 推向工程系统所需的更强假设边界：[第 3.5 节](ref:sec:degeneracy) 揭示了几何退化本质上是可观测性不足的问题，并给出检测与约束提交的处理路径 [Hinduja et al.](cite:hindujaDegeneracyAwareFactorsApplications2019)；[第 3.6 节](ref:sec:global-init) 通过全局初始化与可认证估计把误差压入可收敛区域，为局部 ICP 提供“可用起点”（FGR、Go-ICP、TEASER++ 等）[Yang et al.](cite:yangTEASERFastCertifiable2021)；[第 3.7 节](ref:sec:dl-icp) 讨论学习型特征、软对应与端到端网络在低重叠和重复结构中的优势与风险 [Wang and Solomon](cite:wangDeepClosestPoint2019)；[第 3.8 节](ref:sec:opt-solvers) 从求解器视角统一这些方法，说明鲁棒核、稀疏范数与可认证松弛分别对应不同的优化结构与计算代价边界 [Rosen et al.](cite:rosenSESyncCertifiablyCorrect2019)。

在实践中，算法层面的鲁棒化与初始化只是“让问题可解”，而系统级实时性往往受制于近邻查询与线性代数的吞吐。第 4 章将围绕该计算瓶颈，从数据结构、降采样、并行化与近似搜索四个层面总结可复用的软件加速策略。
