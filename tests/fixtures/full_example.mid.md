<!-- documentclass: article -->
<!-- classoptions: [12pt, a4paper] -->
<!-- packages: [amsmath, graphicx, ctex, hyperref, algorithm2e] -->
<!-- bibliography: refs.bib -->
<!-- bibstyle: IEEEtran -->
<!-- title: 基于 FPGA 的实时点云配准方法 -->
<!-- author: Wuchao -->
<!-- date: 2026 -->
<!-- abstract: |
  本文提出了一种基于 FPGA 的实时点云配准方法，
  通过硬件加速 4PCS 算法实现了 10 倍性能提升。
-->

# 绪论
<!-- label: sec:intro -->

点云配准是三维视觉领域的基础问题[Wang et al.](cite:wang2024)。
传统方法如 RANSAC[1](cite:fischler1981) 存在计算效率低的问题，
而 4PCS 方法[Aiger et al.](cite:aiger2008)提供了更优的理论保证。

本文的贡献如下：

1. 提出了一种适合 FPGA 实现的 4PCS 变体算法
2. 设计了流水线化的硬件架构
3. 在 ZCU102 平台上实现了实时处理

## 相关工作
<!-- label: sec:related -->

如[图1](ref:fig:pipeline)所示，现有方法可分为三类。

![点云配准流程](figures/pipeline.png)
<!-- caption: 点云配准方法分类与本文方法定位 -->
<!-- label: fig:pipeline -->
<!-- width: 0.85\textwidth -->
<!-- ai-generated: true -->
<!-- ai-model: dall-e-3 -->
<!-- ai-prompt: |
  Academic diagram showing taxonomy of point cloud registration methods,
  tree structure with three branches: correspondence-based, global, learning-based,
  clean minimal style, white background, blue accent color
-->
<!-- ai-negative-prompt: photorealistic, 3D render, complex -->

实验结果对比见[表1](ref:tab:results)。

| Method   | RMSE (cm) | Time (ms) | Platform |
|----------|-----------|-----------|----------|
| RANSAC   | 2.3       | 150       | CPU      |
| 4PCS     | 1.8       | 80        | CPU      |
| Ours     | 1.9       | 8         | FPGA     |
<!-- caption: 不同方法在 ModelNet40 数据集上的性能对比 -->
<!-- label: tab:results -->

由[公式1](ref:eq:transform)定义刚体变换：

$$
T = \begin{bmatrix} R & t \\ 0 & 1 \end{bmatrix}
$$
<!-- label: eq:transform -->

## 结论

实验证明本文方法在保持精度的同时实现了 $10\times$ 加速，
详见[第2节](ref:sec:related)的分析。
