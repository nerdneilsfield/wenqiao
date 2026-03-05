## 3.7 深度学习驱动的类 ICP 方法 (Deep Learning-Based Registration Methods)
<!-- label: sec:dl-icp -->

传统 ICP 在“低重叠 + 外点多 + 结构重复”的场景里最容易失手：最近邻几乎只认欧氏距离，碰上对称结构或遮挡，错误对应会被迭代一步步放大。2019 年以后，点云表征学习与可微模块逐渐成熟，研究者开始把神经网络嵌到配准流水线上：有的只替换某一环节（比如特征或对应），有的干脆把“对应 + 求解”合在一次前向里，甚至直接学“怎么执行 ICP”。

本节按“保留 ICP 结构的程度”由强到弱梳理：先看 PointNetLK 这种把迭代结构保留下来的方法，再看 DCP / RPM-Net 这类用软对应替代硬最近邻的端到端框架，最后落到 GeoTransformer / PointDifformer / NAR-\*ICP 这类把一致性、鲁棒性和可解释性一起往前推的路线。

![深度学习配准架构谱系](../images/ch3-dl-icp-taxonomy.png)
<!-- caption: 深度学习点云配准方法的架构谱系（示意）。横轴：与经典 ICP 框架的保留程度（从最大保留到更端到端）。纵轴：对外点/低重叠的鲁棒性。主要方法从左到右：PointNetLK（ICP 结构 + DL 表征）→ DCP（软对应替代硬对应）→ RPM-Net（Sinkhorn 软对应）→ GeoTransformer（Transformer 特征 + LGR）→ PointDifformer（扩散过程生成对应）。气泡大小仅用于强调代表性方法的相对影响力，不对应固定评测数值。 -->
<!-- label: fig:dl-icp-taxonomy -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Academic publication figure style for thesis/survey paper.
  White background, clean flat vector illustration, no photorealism, no 3D rendering, no poster style, no marketing style.
  Use conceptual diagram or mechanism illustration unless explicitly drawing a verified data figure from the paper.
  Emphasize structural clarity, strict alignment, readable hierarchy, balanced whitespace, crisp lines, and publication quality.
  Use consistent color mapping across all figures:
  - computation or processing units: deep blue #2B4C7E
  - storage, cache, or memory: teal blue #3C7A89
  - data flow, candidate flow, or intermediate states: orange #D17A22
  - valid region, retained path, or normal state: dark green #5B8C5A
  - conflict, bottleneck, pruned, or failed region: dark red #A23B2A
  - neutral text #333333, border #888888, light background block #EDEDED
  Limit total colors to 5-6 and keep the same semantic-to-color mapping across figures.
  Chinese-first labels, optional English in parentheses only when necessary.
  Use concise academic wording only; avoid promotional claims.
  Prefer multi-panel layout with consistent spacing and strict alignment.
  Rounded rectangles for modules, grid or bank layout for memory, horizontal chained blocks for pipelines, top-down layout for trees or hierarchies.
  Use dark red crosses, dashed lines, or fading for pruning, failure, and conflict.
  Place legend consistently at top-right or bottom-right.
  If no verified numeric data exist, do not show exact values, exact axes, exact ratios, exact timings, or fake statistics.
  Output should be suitable for thesis or survey paper.
  Chapter 3 figure mode: method-variant mechanism comparison.
  Focus on correspondence construction, outlier suppression, convergence acceleration, transform estimation, degeneracy handling, global initialization, deep registration, and solver structure.
  Use multi-panel comparative diagrams showing baseline step, modified step, failure condition, and effect on optimization path.
  If a figure is not redrawn from verified paper data, explicitly keep it conceptual and avoid exact numeric plots.
  Academic diagram showing taxonomy of deep learning point cloud registration methods (schematic).
  Horizontal axis labeled in Chinese only: "ICP 框架保留程度" from "保留更多" on left to "端到端更多" on right.
  Vertical axis labeled in Chinese only: "对外点/低重叠的鲁棒性" from "低" (bottom) to "高" (top).
  Show 5 method bubbles positioned in this 2D space, each bubble colored differently; bubble size is qualitative (no numeric legend):
    - "PointNetLK" (blue, small): bottom-left
    - "DCP" (orange, medium): center-left
    - "RPM-Net" (green, medium): center
    - "GeoTransformer" (red, large): right-upper
    - "PointDifformer" (purple, large): top-right
  Each bubble labeled with method name and a short Chinese tag (e.g., "软对应", "几何注意力", "扩散").
  White background, clean publication style, no English axis text.
-->

### 3.7.1 PointNetLK：将 Lucas-Kanade 迁移到点云

**PointNetLK** [Aoki et al.](cite:aokiPointNetLKRobustEfficient2019) 是将深度学习引入 ICP 框架的先驱工作之一。其核心思想借鉴了 Lucas-Kanade（LK）类迭代：用可微分的表征函数构造 Jacobian，并通过一阶近似迭代估计变换。PointNetLK 将 PointNet 的全局特征向量作为可微分表征函数 [Qi et al.](cite:qiPointNetDeepLearning2016)，将 LK 迭代展开为递归深度神经网络：

$$
\Delta \boldsymbol{\xi}^{(k)} = J_{\Phi}^{+} \left(\Phi(\mathcal{Q}) - \Phi\!\left(T^{(k)}(\mathcal{P})\right)\right)
$$
<!-- label: eq:pointnetlk -->

其中 $\Phi$ 为 PointNet 特征提取函数，$J_{\Phi}^+$ 为其伪逆 Jacobian（在训练中学习），$\Delta\boldsymbol{\xi}^{(k)} \in se(3)$ 为李代数更新量。PointNetLK 将该迭代展开为固定深度的网络并端到端训练，使位姿误差可通过反向传播直接监督表征学习。

PointNetLK 的关键点在于：它不再在点空间里做最近邻，而是让“变换前后的全局特征”对齐。这里用到的 PointNet 表征并不是凭空而来，原始 PointNet 在 ModelNet40 分类上给出的整体准确率为 89.2%（原文表 1）[Qi et al.](cite:qiPointNetDeepLearning2016)，PointNetLK 直接复用这种全局几何编码作为 $\Phi(\cdot)$，把“配准”变成“特征差的迭代逼近”。

PointNetLK 的实验比较集中在“初值有扰动、但还没完全错开”的范围内：在 ModelNet40 上，测试时的初始平移取 $[0,0.3]$，初始旋转取 $[0,90]^{\\circ}$，并且 PointNetLK 与 ICP 都固定迭代 10 次[Aoki et al.](cite:aokiPointNetLKRobustEfficient2019)。更直观的一组结果来自 Stanford bunny：ICP 的旋转/平移误差为 $(175.51^{\\circ}, 0.22)$，Go-ICP 为 $(0.18^{\\circ},10^{-3})$，PointNetLK 为 $(0.2^{\\circ},10^{-4})$；耗时上，ICP 约 0.36 s，PointNetLK 约 0.2 s，而 Go-ICP 约 80.78 s [Aoki et al.](cite:aokiPointNetLKRobustEfficient2019)。这说明 PointNetLK 在中等初值误差下能比传统 ICP 更快收敛到正确解，但当初值已经落到错误吸引域时，它和 ICP 一样没有把局部配准改成全局配准。

它的问题也很明确：全局特征会把局部几何平均掉。当输入只剩局部可见区域，或者物体由细碎结构构成时，特征差对位姿的梯度会变弱，LK 更新会提前停在残差仍然偏大的位置 [Aoki et al.](cite:aokiPointNetLKRobustEfficient2019)。

### 3.7.2 DCP：软对应与 Transformer 注意力

**DCP（Deep Closest Point）** [Wang and Solomon](cite:wangDeepClosestPoint2019) 以三个创新替代了经典 ICP 的最近邻硬对应：（1）以 DGCNN 提取逐点局部特征；（2）以 Transformer 注意力机制计算源点云与目标点云之间的软对应权重；（3）以加权 SVD 估计变换。

**Transformer 软对应**：对于源点 $p_i$，计算其与目标点云所有点的对应权重：

$$
a_{ij} = \text{softmax}\!\left(\frac{f_i^P \cdot f_j^Q}{\sqrt{d}}\right), \quad \tilde{q}_i = \sum_j a_{ij} q_j
$$
<!-- label: eq:dcp-attention -->

其中 $f_i^P, f_j^Q$ 为经过 Transformer 交叉注意力的特征向量，$d$ 为特征维度。软对应 $\tilde{q}_i$ 是所有目标点的加权平均，可微分地传递到 Kabsch/SVD 变换估计步骤。整个流程端到端训练，监督信号为变换参数的均方误差。

**与经典 ICP 的关键区别**：DCP 的对应不需要也不利用当前位姿估计——特征匹配直接在原始坐标空间中进行，不是点变换后的最近邻。这意味着 DCP 在一次前向传播中完成所有迭代，而不是真正的"迭代"，从根本上改变了 ICP 的算法结构 [Wang and Solomon](cite:wangDeepClosestPoint2019)。

这篇工作用的是 ModelNet40 上最常见的一套合成配准设置：三轴旋转均匀采样于 $[0,45]^{\\circ}$，平移采样于 $[-0.5,0.5]$，训练集和测试集按“类别不重叠”拆开 [Wang and Solomon](cite:wangDeepClosestPoint2019)。在这组设置下，DCP-v2 的 RMSE(R) 为 1.1434°、MAE(R) 为 0.7706°，RMSE(t) 为 0.001786、MAE(t) 为 0.001195；作为参照，同样条件下 PointNetLK 的 RMSE(R) 为 15.0954°，FGR 为 9.3628°[Wang and Solomon](cite:wangDeepClosestPoint2019)。推理速度方面，在 i7-7700 + GTX 1070 上，512 点输入时 DCP-v2 约 0.0079 s，1024 点时约 0.0083 s（原文表 4）[Wang and Solomon](cite:wangDeepClosestPoint2019)。

DCP 的前提也比经典 ICP 更强。它要求训练得到的特征空间能把真对应和假对应分开；测试分布一旦偏离训练分布，或者局部几何存在大面积重复，注意力矩阵就会把错误对应整体抬高。由于 DCP 只做一次前向传播，前面这一步一旦偏掉，后面的 SVD 会直接给出带偏变换，没有经典 ICP 那种逐轮修正的机会 [Wang and Solomon](cite:wangDeepClosestPoint2019)。

![DCP 端到端网络架构详解](../images/ch3-dcp-architecture.png)
<!-- caption: DCP（Deep Closest Point）端到端网络架构示意，展示从输入点云到变换估计的三段式数据流：（a）DGCNN 提取逐点特征；（b）Transformer 交叉注意力形成软对应（对应矩阵为连续权重而非硬匹配）；（c）可微分 SVD（Kabsch）从软对应中回归刚体变换，并将梯度回传到特征提取模块，实现端到端训练。 -->
<!-- label: fig:dcp-architecture -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Academic publication figure style for thesis/survey paper.
  White background, clean flat vector illustration, no photorealism, no 3D rendering, no poster style, no marketing style.
  Use conceptual diagram or mechanism illustration unless explicitly drawing a verified data figure from the paper.
  Emphasize structural clarity, strict alignment, readable hierarchy, balanced whitespace, crisp lines, and publication quality.
  Use consistent color mapping across all figures:
  - computation or processing units: deep blue #2B4C7E
  - storage, cache, or memory: teal blue #3C7A89
  - data flow, candidate flow, or intermediate states: orange #D17A22
  - valid region, retained path, or normal state: dark green #5B8C5A
  - conflict, bottleneck, pruned, or failed region: dark red #A23B2A
  - neutral text #333333, border #888888, light background block #EDEDED
  Limit total colors to 5-6 and keep the same semantic-to-color mapping across figures.
  Chinese-first labels, optional English in parentheses only when necessary.
  Use concise academic wording only; avoid promotional claims.
  Prefer multi-panel layout with consistent spacing and strict alignment.
  Rounded rectangles for modules, grid or bank layout for memory, horizontal chained blocks for pipelines, top-down layout for trees or hierarchies.
  Use dark red crosses, dashed lines, or fading for pruning, failure, and conflict.
  Place legend consistently at top-right or bottom-right.
  If no verified numeric data exist, do not show exact values, exact axes, exact ratios, exact timings, or fake statistics.
  Output should be suitable for thesis or survey paper.
  Chapter 3 figure mode: method-variant mechanism comparison.
  Focus on correspondence construction, outlier suppression, convergence acceleration, transform estimation, degeneracy handling, global initialization, deep registration, and solver structure.
  Use multi-panel comparative diagrams showing baseline step, modified step, failure condition, and effect on optimization path.
  If a figure is not redrawn from verified paper data, explicitly keep it conceptual and avoid exact numeric plots.
  Three-stage academic architecture diagram for DCP (Deep Closest Point), white background, flat vector style.
  All in-figure text Chinese only.
  Layout: three blocks left-to-right with arrows:
  Block (1) "特征提取": two point cloud icons "源点云" and "目标点云" go through shared-weight feature extractor "DGCNN" to produce "逐点特征".
  Block (2) "交叉注意力": show a soft correspondence matrix heatmap labeled "软对应矩阵" produced by attention.
  Block (3) "可微 SVD": show a "SVD" icon producing outputs "R" and "t", plus a dashed feedback arrow labeled "端到端梯度".
  Keep the diagram uncluttered: no explicit tensor sizes, no benchmark numbers.
-->

### 3.7.3 DeepVCP：显式关键点检测与对应

**DeepVCP** [Lu et al.](cite:luDeepVCPEndtoEndDeep2019) 明确将配准分解为两个子问题：可重复关键点检测（repeatable keypoint detection）和可微分对应估计（differentiable correspondence estimation）。关键点检测器以点特征权重对原始点云加权聚合为稳定三维关键点，对应估计网络预测每对候选关键点的匹配概率，最终以全连接网络直接回归变换参数：

$$
(R,t) = \text{FCNet}\!\left(\{(k_i, c_j, s_{ij})\}_{i,j}\right)
$$
<!-- label: eq:deepvcp -->

其中 $k_i$ 为源关键点，$c_j$ 为目标关键点，$s_{ij}$ 为匹配分数。论文把“关键点检测要避开动态物体”作为核心卖点，并用端到端结构把检测器也一起拉进训练里 [Lu et al.](cite:luDeepVCPEndtoEndDeep2019)。

从结果看，DeepVCP 在真实车载数据上的精度是能站住的：在 KITTI 上，“Ours-Duplication” 的旋转误差均值/最大值为 0.164°/1.212°，平移误差均值/最大值为 0.071 m/0.482 m（原文表 1）；在 Apollo-SouthBay 上，对应数值分别为 0.056°/0.875° 和 0.018 m/0.932 m（原文表 2）[Lu et al.](cite:luDeepVCPEndtoEndDeep2019)。但它的代价也写得很清楚，端到端推理仍在秒级，柱状图读出来大约是 2 s[Lu et al.](cite:luDeepVCPEndtoEndDeep2019)。

DeepVCP 的重点在于把关键点和对应一起学出来，而不是把每帧推理压到里程计前端能接受的时延。关键点若在遮挡、稀疏采样或跨域场景下失去重复性，后面的匹配分数和位姿回归会一起失真；再加上单次推理约 2 s，它不能直接充当实时前端 [Lu et al.](cite:luDeepVCPEndtoEndDeep2019)。

### 3.7.4 RPM-Net：Sinkhorn 归一化与退火对应

**RPM-Net（Robust Point Matching Network）** [Yew and Lee](cite:yewRPMNetRobustPoint2020) 将经典点集匹配中的 Softassign/Sinkhorn 归一化引入深度学习框架，解决 DCP 中 softmax 对应矩阵的两个问题：（1）行归一化但不列归一化，导致多对一匹配；（2）对位姿的全局变化不鲁棒。

**Sinkhorn 层**：对以混合特征（位置 + 法向）计算的相似度矩阵 $M$，应用多轮 Sinkhorn 迭代确保行列同时归一化：

$$
S^{(0)} = \exp(M/T_\text{anneal}), \quad S^{(l+1)} = \text{ColNorm}\!\left(\text{RowNorm}\!\left(S^{(l)}\right)\right)
$$
<!-- label: eq:rpm-sinkhorn -->

其中 $T_\text{anneal}$ 为温度参数。**退火策略**：从高温逐步降到低温，让对应矩阵从“分得开但不尖锐”过渡到“更接近一一匹配”[Yew and Lee](cite:yewRPMNetRobustPoint2020)。RPM-Net 还显式加了 “dustbin” 槽位来吸收无对应的源点，从结构上把“外点”这件事写进匹配矩阵。

RPM-Net 的实验仍然放在 ModelNet40 上做，但比 DCP 多推了两步：一是把模型统一采样到 2048 点并归一化到单位球，二是专门把噪声和部分可见性单独拎出来看[Yew and Lee](cite:yewRPMNetRobustPoint2020)。在干净数据上，RPM-Net 的各向同性误差为 0.056°（旋转）与 0.0003（平移），明显优于 PointNetLK 的 0.847° 与 0.0054（原文表 1）；加入高斯噪声 $\\mathcal{N}(0,0.01)$ 并裁剪到 $[-0.05,0.05]$ 后，DCP-v2 的各向同性误差为 2.426° 与 0.0141，而 RPM-Net 能压到 0.664° 与 0.0062（原文表 2）[Yew and Lee](cite:yewRPMNetRobustPoint2020)。再往前走一步，在部分可见实验里，作者用随机半空间保留约 70% 的点并下采样到 717 点，PointNetLK 还要再加一个 $\\tau=0.02$ 的可见性筛选；在“部分可见 + 噪声”下，DCP-v2 的各向同性误差为 2.994° 与 0.0202，而 RPM-Net 为 1.712° 与 0.018（原文表 3）[Yew and Lee](cite:yewRPMNetRobustPoint2020)。

这种改进不是没有代价。作者在 3.0 GHz i7-6950X + Titan RTX 上按 5 次迭代统计每对点云的平均推理时间：512 点时 RPM-Net 为 25 ms，而 DCP-v2 只有 5 ms；1024 点时分别为 52 ms 与 9 ms；2048 点时进一步拉开到 178 ms 与 21 ms（原文表 5）[Yew and Lee](cite:yewRPMNetRobustPoint2020)。也就是说，Sinkhorn 双随机归一化和退火策略确实把匹配矩阵做得更规整，但计算账也更重，点数一上去增长得很快。

![RPM-Net Sinkhorn 对应矩阵退火演化](../images/ch3-rpm-sinkhorn-annealing.png)
<!-- caption: RPM-Net 中 Sinkhorn 归一化与温度退火的对应矩阵演化示意。高温阶段对应矩阵更“软”（分布更均匀），随着温度降低与 Sinkhorn 迭代，矩阵逐步变尖锐并趋向一一匹配；外点可被分配到“外点槽（dustbin）”。右侧以示意曲线展示温度下降与对应不确定性（如熵/分布宽度）降低的同步趋势。 -->
<!-- label: fig:rpm-sinkhorn-annealing -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Academic publication figure style for thesis/survey paper.
  White background, clean flat vector illustration, no photorealism, no 3D rendering, no poster style, no marketing style.
  Use conceptual diagram or mechanism illustration unless explicitly drawing a verified data figure from the paper.
  Emphasize structural clarity, strict alignment, readable hierarchy, balanced whitespace, crisp lines, and publication quality.
  Use consistent color mapping across all figures:
  - computation or processing units: deep blue #2B4C7E
  - storage, cache, or memory: teal blue #3C7A89
  - data flow, candidate flow, or intermediate states: orange #D17A22
  - valid region, retained path, or normal state: dark green #5B8C5A
  - conflict, bottleneck, pruned, or failed region: dark red #A23B2A
  - neutral text #333333, border #888888, light background block #EDEDED
  Limit total colors to 5-6 and keep the same semantic-to-color mapping across figures.
  Chinese-first labels, optional English in parentheses only when necessary.
  Use concise academic wording only; avoid promotional claims.
  Prefer multi-panel layout with consistent spacing and strict alignment.
  Rounded rectangles for modules, grid or bank layout for memory, horizontal chained blocks for pipelines, top-down layout for trees or hierarchies.
  Use dark red crosses, dashed lines, or fading for pruning, failure, and conflict.
  Place legend consistently at top-right or bottom-right.
  If no verified numeric data exist, do not show exact values, exact axes, exact ratios, exact timings, or fake statistics.
  Output should be suitable for thesis or survey paper.
  Chapter 3 figure mode: method-variant mechanism comparison.
  Focus on correspondence construction, outlier suppression, convergence acceleration, transform estimation, degeneracy handling, global initialization, deep registration, and solver structure.
  Use multi-panel comparative diagrams showing baseline step, modified step, failure condition, and effect on optimization path.
  If a figure is not redrawn from verified paper data, explicitly keep it conceptual and avoid exact numeric plots.
  Multi-panel academic diagram showing Sinkhorn soft assignment matrix evolution with temperature annealing in RPM-Net (schematic).
  White background, clean vector style, all in-figure text Chinese only.
  Left: three heatmaps stacked vertically labeled "高温", "中温", "低温" showing soft-to-hard correspondences.
    Rows labeled "源点 p1..pN", columns labeled "目标点 q1..qM" plus one column "外点槽".
    Add a colorbar labeled "对应权重".
  Right: one small line chart showing "温度"下降与"不确定性"下降（两条曲线，均无数值刻度）。
  Avoid any numeric annotations; focus on qualitative sharpening and dustbin usage.
-->

### 3.7.5 GeoTransformer：几何自注意力与 RANSAC-free 求解

**GeoTransformer** [Qin et al.](cite:qinGeometricTransformerFast2022a) 是将“可学习特征”与“基于一致性的全局估计”紧密耦合的代表性方法。它的目标并不是把 ICP 的每一步都替换为黑盒，而是让网络输出的候选对应在几何上更一致，从而减少对随机采样与硬阈值的依赖。其三个核心机制：

**1. 几何自注意力（Geometric Self-Attention）**：在 Transformer 注意力层中显式编码点对的距离和三元组的角度关系：

$$
e_{ij} = \frac{(f_i + r^D_{ij})(f_j + r^D_{ij})^\top}{\sqrt{d}} + \frac{\max_x r^A_{ijx} \cdot f_i}{\sqrt{d}}
$$
<!-- label: eq:geotransformer-attention -->

其中 $r^D_{ij}$ 为点对距离的嵌入，$r^A_{ijx}$ 为三元组角度嵌入。这一设计使得注意力权重对刚体变换保持严格不变性，而不依赖于外部坐标系，大大提升了低重叠场景的内点比 [Qin et al.](cite:qinGeometricTransformerFast2022a)。

**2. 超点到密点的层次化匹配**：先在下采样的超点（superpoint）级别做全局匹配，再将超点对应通过局部传播回到稠密点，以兼顾计算可行性与几何细节。

**3. LGR（Local-to-Global Registration）**：在对应质量足够高时，可用局部-全局一致性求解替代随机采样估计（RANSAC）来求解刚体变换，使求解过程更确定、更易并行，并减少“采样失败”对结果的影响 [Qin et al.](cite:qinGeometricTransformerFast2022a)。

GeoTransformer 的说服力主要来自低重叠场景。作者在 3DMatch 和 3DLoMatch 上分别取重叠率大于 30% 和 10%–30% 的点云对，并保留了文献里常见的 50K 次 RANSAC 统计口径 [Qin et al.](cite:qinGeometricTransformerFast2022a)。在 RANSAC-50k、采样 5000 对对应的条件下，GeoTransformer 的 RR(%) 为 92.0 / 75.0（3DMatch / 3DLoMatch），总耗时约 1.633 s（原文表 1）；同一条件下，采用粗到细对应传播的 CoFiNet [Yu et al.](cite:yuCoFiNetReliableCoarsetofine2021) 为 89.3 / 67.5，专门针对低重叠区域建模 overlap-attention 的 PREDATOR [Huang et al.](cite:huangPredatorRegistration3D2021) 为 89.0 / 59.8。真正关键的是把 RANSAC 拿掉以后：若直接用加权 SVD，GeoTransformer 的 RR 为 86.5 / 59.9，总耗时约 0.078 s；换成 LGR 后 RR 提到 91.5 / 74.0，总耗时约 0.088 s（原文表 2）。如果只看求解阶段，LGR 相比它自己的 RANSAC-50k 版本，从 1.633 s 降到 0.088 s，约快 18.6 倍；和 CoFiNet 的 LGR（0.143 s）相比也快约 1.6 倍（原文表 2）[Qin et al.](cite:qinGeometricTransformerFast2022a)。

GeoTransformer 能把 RANSAC 拿掉，前提是前端给出的超点对应已经足够一致。若场景跨域明显、重叠率继续下降，或者局部几何存在重复结构，LGR 接收到的对应集就会失去一致性，此时求解阶段同样会失败 [Qin et al.](cite:qinGeometricTransformerFast2022a)。

![GeoTransformer 超点层次化匹配与几何注意力可视化](../images/ch3-geotransformer-superpoint.png)
<!-- caption: GeoTransformer 的关键直观：层次化超点匹配把“全局搜索”放在低分辨率表示上完成，再把对应传播回稠密点；几何自注意力热力图展示注意力权重更倾向于几何一致的结构对应，而非仅由欧氏距离决定。该图为机制示意，非特定数据集的定量复现。 -->
<!-- label: fig:geotransformer-superpoint -->
<!-- width: \textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Academic publication figure style for thesis/survey paper.
  White background, clean flat vector illustration, no photorealism, no 3D rendering, no poster style, no marketing style.
  Use conceptual diagram or mechanism illustration unless explicitly drawing a verified data figure from the paper.
  Emphasize structural clarity, strict alignment, readable hierarchy, balanced whitespace, crisp lines, and publication quality.
  Use consistent color mapping across all figures:
  - computation or processing units: deep blue #2B4C7E
  - storage, cache, or memory: teal blue #3C7A89
  - data flow, candidate flow, or intermediate states: orange #D17A22
  - valid region, retained path, or normal state: dark green #5B8C5A
  - conflict, bottleneck, pruned, or failed region: dark red #A23B2A
  - neutral text #333333, border #888888, light background block #EDEDED
  Limit total colors to 5-6 and keep the same semantic-to-color mapping across figures.
  Chinese-first labels, optional English in parentheses only when necessary.
  Use concise academic wording only; avoid promotional claims.
  Prefer multi-panel layout with consistent spacing and strict alignment.
  Rounded rectangles for modules, grid or bank layout for memory, horizontal chained blocks for pipelines, top-down layout for trees or hierarchies.
  Use dark red crosses, dashed lines, or fading for pruning, failure, and conflict.
  Place legend consistently at top-right or bottom-right.
  If no verified numeric data exist, do not show exact values, exact axes, exact ratios, exact timings, or fake statistics.
  Output should be suitable for thesis or survey paper.
  Chapter 3 figure mode: method-variant mechanism comparison.
  Focus on correspondence construction, outlier suppression, convergence acceleration, transform estimation, degeneracy handling, global initialization, deep registration, and solver structure.
  Use multi-panel comparative diagrams showing baseline step, modified step, failure condition, and effect on optimization path.
  If a figure is not redrawn from verified paper data, explicitly keep it conceptual and avoid exact numeric plots.
  Two-column academic diagram (schematic) for GeoTransformer mechanisms.
  White background, clean vector style, all in-figure text Chinese only.

  Left column "层次化超点匹配":
  - A 3-level pyramid: top = "稠密点云", middle = "超点", bottom = "稠密对应".
  - Show downsampling arrow from dense to superpoints labeled "下采样".
  - Between source and target superpoints, draw a double arrow labeled "几何注意力".
  - From superpoint matches, draw a propagation arrow back to dense correspondences labeled "传播".
  - Do not include any point counts, matrix sizes, ratios, or speedup numbers.

  Right column "几何自注意力热力图":
  - Show two partial-overlap indoor silhouettes (e.g., "桌椅") with superpoints as circles.
  - Show a separate attention heatmap (rows=源超点, cols=目标超点) with qualitative high/low regions.
  - Add 2-3 example correspondence lines labeled "结构对应" (no numeric weights).
-->

### 3.7.6 PointDifformer：神经扩散与对应生成

**PointDifformer** [She et al.](cite:shePointDifformerRobustPoint2024) 将神经网络偏微分方程（Graph PDE）和热核签名（Heat Kernel Signature，HKS）引入点云配准，以扩散过程增强特征表示的鲁棒性。

**热扩散特征提取**：通过图神经 PDE 模块在点云图上传播特征，等价于在点云上求解热方程 $\partial_t F = \Delta_{\mathcal{G}} F$（$\Delta_{\mathcal{G}}$ 为图拉普拉斯算子）。热核签名描述了在时间 $t$ 从点 $p_i$ 出发的热量仍然留在 $p_i$ 的概率，对等距变换严格不变——即便形状发生非刚体小变形，签名变化也有限，使 PointDifformer 对高斯噪声和三维形状扰动的鲁棒性更强 [She et al.](cite:shePointDifformerRobustPoint2024)。

**可学习 SVD**：最终变换估计通过带可学习权重的 SVD 模块完成——对应矩阵中每对点的权重由网络预测，而不是固定为内点/外点的二元分类。变换估计损失为

$$
\mathcal{L}_\text{mse} = \frac{1}{K'}\sum_{i=1}^{K'}\|\hat{R}x_i + \hat{t} - y_i\|_2^2
$$
<!-- label: eq:pointdifformer-loss -->

PointDifformer 没有只在合成物体上报数，而是把重点放回真实扫描。3DMatch / 3DLoMatch 上，它的 RR 分别为 93.0% / 75.2%；换到 KITTI，常规测试下的平移 MAE/RMSE 为 4.14 cm / 8.86 cm，旋转 MAE/RMSE 为 0.14° / 0.23°，RR 为 97.7%[She et al.](cite:shePointDifformerRobustPoint2024)。为了说明扩散特征对噪声和扰动更稳，作者又专门在 KITTI 上加了两组破坏：叠加高斯噪声（例如 $\\mathcal{N}(0,0.25)$）时，PointDifformer 的平移 RMSE 为 9.00 cm，而 GeoTransformer 为 14.43 cm（原文表 VI）；局部移除点形成形状扰动时，前者为 8.99 cm，后者为 13.08 cm（原文表 VIII）[She et al.](cite:shePointDifformerRobustPoint2024)。与此同时，工程代价也没有藏着：推理时间约 0.072 s，GPU 显存占用约 2.44 GB（原文表 XI）[She et al.](cite:shePointDifformerRobustPoint2024)。

这条路线的代价也很直接。扩散式特征提取、图上的 PDE 演化和后面的加权求解串起来以后，推理时间为 0.072 s，显存占用为 2.44 GB，训练和部署开销都高于 DCP、RPM-Net；因此它不能直接替代高频在线前端 [She et al.](cite:shePointDifformerRobustPoint2024)。

### 3.7.7 NAR-*ICP：神经算法推理与可解释配准

**NAR-\*ICP** [Panagiotaki et al.](cite:panagiotakiNARICPNeuralExecution2025) 基于神经算法推理（Neural Algorithmic Reasoning，NAR）范式，以图神经网络（GNN）学习"执行"经典 ICP 的每一步中间计算。与 DCP/GeoTransformer 将 ICP 替换为黑盒不同，NAR-\*ICP 保留 ICP 的迭代结构作为归纳偏置（inductive bias），GNN 只学习每一步最近邻选择、权重计算和变换估计中的参数：

$$
\boldsymbol{\xi}^{(k+1)}_\theta = \text{GNN}_\theta\!\left(\mathcal{P},\, \mathcal{Q},\, \boldsymbol{\xi}^{(k)}\right)
$$
<!-- label: eq:nar-icp -->

训练监督为每步中间状态，而不只看最终位姿，这让它的“可解释”不是口号：你能把每一步输出当成 ICP 中间量去检查（对应、相位、是否该停）。

NAR-\*ICP 的实验思路和前面几篇不太一样，它不是只看最后有没有对齐上，而是看“学出来的执行过程”能不能在不同扫描条件下稳住。作者从 SemanticKITTI 中抽取带语义标签的物体中心点，按 KITTI 常见的 RTE/RRE 指标评估 [Panagiotaki et al.](cite:panagiotakiNARICPNeuralExecution2025)。在合成数据和三档扫描间距（平均 1.6 m / 11.3 m / 24 m）的对比里，24 m 这一档最能看出差异：P2P-ICP 的 RTE/RRE 为 0.934 / 1.912，而 NAR-P2L 为 0.391 / 0.796；再加上文中提出的 ground-truth optimisation 后，NAR-GICP+ 可进一步降到 0.222 / 0.458（原文表 II、表 III）[Panagiotaki et al.](cite:panagiotakiNARICPNeuralExecution2025)。横向和学习型基线比较时，作者把 RR 定义为 “RTE < 2 m 且 RRE < 0.6° 的成功率”，并同时报告 RTEGT/RREGT/RRGT：GeoTransformer 为 0.335/0.512/85.2%，Predator 为 0.433/0.371/74.1%，DCP 为 0.147/0.376/99.4%，NAR-P2Pv2+ 为 0.148/0.334/98.2%（原文表 V）[Panagiotaki et al.](cite:panagiotakiNARICPNeuralExecution2025)。效率方面，在同一 GPU 上，GeoTransformer 平均约 0.13 s/对，Predator 约 0.34 s/对，DCP 约 0.03 s/对，而 NAR-P2Pv2 为 0.02 s/对；参数量约 773k（原文表 VI）[Panagiotaki et al.](cite:panagiotakiNARICPNeuralExecution2025)。

NAR-\*ICP 更依赖训练时给出的中间监督。若训练阶段只覆盖少量扫描间距、少量几何类型或固定的执行顺序，网络学到的就是那一套 ICP 过程；测试时一旦超出这组条件，中间步骤就会先失真，最终位姿也会跟着偏掉 [Panagiotaki et al.](cite:panagiotakiNARICPNeuralExecution2025)。

### 3.7.8 深度学习方法与经典 ICP 的系统对比

| 方法 | 学到的对象 | 变换估计方式 | 优势（相对经典） | 主要风险/代价 | 部署友好度（定性） |
|------|-----------|--------------|----------------|--------------|------------------|
| P2P ICP [Besl & McKay](cite:beslMethodRegistration3D1992) | 无（几何规则） | 硬对应 + 闭式解 | 可解释、可控、易验证 | 对低重叠/外点敏感 | 极高 |
| PointNetLK [Aoki et al.](cite:aokiPointNetLKRobustEfficient2019) | 全局表征 + 可微 Jacobian | LK 式迭代（展开） | 在特征空间缓解噪声/密度扰动 | 全局特征易丢局部细节，收敛域受限 | 中 |
| DCP [Wang and Solomon](cite:wangDeepClosestPoint2019) | 点特征 + 软对应 | 加权 SVD | 端到端、对应可微、避免硬最近邻 | 注意力代价高，跨域需谨慎 | 低 |
| RPM-Net [Yew and Lee](cite:yewRPMNetRobustPoint2020) | 双随机软匹配（含外点槽） | 加权 SVD（迭代/退火） | 软对应更稳定、更接近一一匹配 | 仍依赖训练分布与算力 | 低 |
| GeoTransformer [Qin et al.](cite:qinGeometricTransformerFast2022a) | 几何一致性特征 + 层次匹配 | LGR（局部-全局一致性求解） | 低重叠下更易获得一致对应，减少采样不确定性 | 对训练数据与评测设置较敏感，工程落地需监控失败模式 | 中 |
| PointDifformer [She et al.](cite:shePointDifformerRobustPoint2024) | 扩散式鲁棒表征/对应权重 | 可学习 SVD | 对噪声与扰动更稳健 | 训练复杂、推理开销偏高 | 低 |
| NAR-\*ICP [Panagiotaki et al.](cite:panagiotakiNARICPNeuralExecution2025) | “如何执行 ICP” | GNN 预测每步中间量 | 可解释、对结构外推更友好 | 仍需精心设计监督与泛化评测 | 中 |
<!-- caption: 第 3.7 节深度学习点云配准方法综合对比（定性）：学习对象、变换估计方式、优势与代价，以及部署友好度。 -->
<!-- label: tab:dl-comparison -->

| 方法 | 数据集与设置 | 指标与数值（摘录） | 运行时/硬件（摘录） |
|---|---|---|---|
| PointNet [Qi et al.](cite:qiPointNetDeepLearning2016) | ModelNet40 分类 | overall accuracy 89.2%（原文表 1） | - |
| PointNetLK [Aoki et al.](cite:aokiPointNetLKRobustEfficient2019) | Stanford bunny；对比 ICP/Go-ICP | ICP (175.51°, 0.22)，Go-ICP (0.18°, 1e-3)，PointNetLK (0.2°, 1e-4) | ICP 0.36 s；PointNetLK 0.2 s；Go-ICP 80.78 s |
| DCP [Wang and Solomon](cite:wangDeepClosestPoint2019) | ModelNet40（类别不重叠；旋转[0,45]°；平移[-0.5,0.5]） | DCP-v2: RMSE(R)=1.1434°，MAE(R)=0.7706°；RMSE(t)=0.001786，MAE(t)=0.001195（原文表 1） | 512 点：0.007932 s；1024 点：0.008295 s（原文表 4；i7-7700+GTX1070） |
| DeepVCP [Lu et al.](cite:luDeepVCPEndtoEndDeep2019) | KITTI / Apollo-SouthBay | KITTI: rot mean/max 0.164°/1.212°，trans mean/max 0.071 m/0.482 m；Apollo: rot mean/max 0.056°/0.875°，trans mean/max 0.018 m/0.932 m（原文表 1/2） | 端到端推理约 2 s（原文图 3） |
| RPM-Net [Yew and Lee](cite:yewRPMNetRobustPoint2020) | ModelNet40（类别不重叠；噪声 $\\mathcal{N}(0,0.01)$ 裁剪到 $[-0.05,0.05]$；部分可见约保留70%并下采样717点） | 噪声下：isotropic err 0.664°/0.0062（rot/trans，原文表 2）；部分可见+噪声：1.712°/0.018（原文表 3） | 512/1024/2048 点：25/52/178 ms（原文表 5；i7-6950X+Titan RTX；5 iter） |
| GeoTransformer [Qin et al.](cite:qinGeometricTransformerFast2022a) | 3DMatch（重叠>30%）/3DLoMatch（10%–30%）；RANSAC-50k | RANSAC-50k: RR 92.0/75.0，总 1.633 s（原文表 1）；LGR: RR 91.5/74.0，总 0.088 s（原文表 2） | 见左（Model/Pose/Total） |
| PointDifformer [She et al.](cite:shePointDifformerRobustPoint2024) | 3DMatch/3DLoMatch；KITTI；噪声/扰动鲁棒性 | RR: 93.0%/75.2%（3DMatch/3DLoMatch，原文表 X）；KITTI: RR 97.7%，trans RMSE 8.86 cm，rot RMSE 0.23°（原文表 III） | 推理 0.072 s；显存 2.44 GB（原文表 XI） |
| NAR-\*ICP [Panagiotaki et al.](cite:panagiotakiNARICPNeuralExecution2025) | SemanticKITTI 派生数据；KITTI 风格 RTE/RRE；RR: RTE<2 m 且 RRE<0.6° | 与学习基线：NAR-P2Pv2+ 的 RTEGT/RREGT/RRGT 为 0.148/0.334/98.2%（原文表 V） | 推理 0.02 s；参数量约 773k（原文表 VI） |
<!-- caption: 第 3.7 节关键学习型方法的“数据集-指标-数值”摘录汇总（每条均对应原论文的表格/图示设置）。 -->
<!-- label: tab:dl-data -->

### 3.7.9 训练范式与迁移学习

深度学习配准方法的训练面临三个核心挑战：

**1. 监督信号设计**：早期方法（DCP、RPM-Net）以位姿真值监督（regression loss），需要精确的地面真值变换。GeoTransformer 以对应内点比（IR）作为辅助监督，更直接地引导特征学习。NAR-\*ICP 以每一步 ICP 的中间状态监督，提供最细粒度的信号。

**2. 域偏移（Domain Shift）**：合成数据与真实扫描在噪声模型、密度分布、遮挡与采样机制上差异显著，导致“在合成上训练的模型”跨域到真实数据时性能下降。域适配（自训练、对抗训练等）可缓解这一问题，但难以彻底消除。

**3. 零样本泛化**：基础大模型（如 Point-MAE、PointBERT）的出现使得预训练-微调范式开始应用于点云配准。以自监督大模型特征替代从头训练的 FCGF/DGCNN，可在新场景上零样本部署，无需任何标注数据，是当前研究的热点方向。

### 3.7.10 深度学习 vs 经典 ICP：互补而非替代

深度学习方法并非全面取代经典 ICP，二者形成明确的互补关系：

- **经典 ICP（见[第 3.1 节](ref:sec:correspondence)至[第 3.4 节](ref:sec:transform)）** 在以下场景仍不可替代：对确定性行为与可解释误差传播要求高、算力/功耗受限（无 GPU 或仅轻量算力）、需要可验证的稳定性与工程可控性的安全关键系统、以及以低延迟为硬约束的实时闭环。

- **深度学习方法** 在以下场景更容易体现收益：重叠不足或遮挡严重、外点与重复结构多、需要跨域鲁棒性（传感器/采样机制变化）、以及对语义一致性有需求的应用。

**更稳妥的工程组合**：由深度学习模块提供粗初始位姿或过滤后的高质量候选对应，再由经典 ICP（GICP 或 FRICP）完成可控的几何精修，并以传统几何/统计检验作为兜底。第 4 章和第 5 章将分别从软件和硬件两个维度讨论如何加速经典 ICP，以缩小其与深度学习方法在推理时延上的差距。
