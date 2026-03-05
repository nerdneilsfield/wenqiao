## 6.1 典型应用场景 (Typical Application Scenarios)
<!-- label: sec:applications -->

ICP 在不同系统里承担的角色并不相同。自动驾驶把它放在连续帧里程计闭环中，首要矛盾是“每帧能否在采样周期内完成”；工业检测把它放在 CAD 与扫描件之间，首要矛盾是“局部精修能否稳定收敛到同一个装夹基准”；机器人抓取和医疗导航则进一步要求对遮挡、对称性和失败风险作出显式处理。因此，本节不再笼统描述“ICP 被广泛应用”，而是按场景补齐部署条件、公开实验和失效链条，并把相关方法与[第 3 章](ref:sec:variants)、[第 4 章](ref:sec:software)和[第 5 章](ref:sec:hardware-accel)的技术选择对应起来。

### 6.1.1 自动驾驶：LiDAR 里程计与建图

自动驾驶前端优先选择点到面残差、局部地图配准和增量数据结构，不是因为这些方法在所有基准上都更优，而是因为车载 LiDAR 以 10 Hz 到 100 Hz 连续输出点云，配准必须在固定采样周期内完成；一旦单帧时延超过预算，后续去畸变、建图和控制都会级联失效。因此，这一场景最看重的是“同等精度下每帧处理时间”和“在退化场景中能否维持可观测性”，而不是单次离线对齐的最低 RMSE。

**LiDAR 里程计**（LiDAR Odometry）：以相邻两帧或当前帧与局部地图之间的配准估计瞬时位姿，再经积分得到轨迹。LOAM [Zhang and Singh](cite:zhangLOAMLidarOdometry2014) 的关键设计不是“用了 ICP”，而是先把全量点云压缩为角点和平面点，再把里程计和建图拆成两个频率不同的线程。原文在 KITTI 里程计基准上使用 10 Hz Velodyne 数据，给出 39.2 km 总行驶距离上的平均位置误差 0.88%；其里程计线程约 10 Hz 输出，建图线程约 1 Hz 输出。这组数字说明 LOAM 成立的前提是结构化道路、较高重叠率和可稳定提取的边/面特征；如果特征提取先退化，后面的局部 ICP 就会失去足够约束。

**FAST-LIO2** [Xu et al.](cite:xuFASTLIO2FastDirect2022) 进一步把“先提特征再配准”的依赖拿掉，改为直接把原始点注册到 ikd-Tree 维护的局部地图中。它之所以能这么做，是因为[第 4.1 节](ref:sec:data-structure)中的 ikd-Tree 把增量插入、删除和近邻查询压到了可实时的量级。原文在 19 个公开序列上比较多种 LiDAR-IMU 里程计，报告 FAST-LIO2 在其中 17 个序列上精度最佳；在大场景下，整套前端和建图可达到 100 Hz，上 Intel 处理器时每帧总处理时间约 1.82 ms，在 ARM 处理器上约 5.23 ms；针对实飞数据，平均每帧 2.01 ms，仍能承受 912–1198 deg/s 的快速翻转。这类直接法的优势在于弱特征场景下仍可利用稠密局部几何；但它依赖 IMU 去畸变和局部地图质量，一旦 IMU 外参、时间同步或法向近似先出错，点到面残差会先被系统偏差污染。

**隧道、地下停车场等弱 GPS 场景**：这类环境以平面和长走廊为主，配准先坏的多半不是最近邻搜索，而是可观测性。当前帧大部分法向垂直于行驶方向时，点到面约束对“沿隧道轴平移”几乎不给信息，优化会先在该方向产生漂移。[第 3.5 节](ref:sec:degeneracy)已经说明这种退化与 Hessian 特征值塌缩直接相关，因此工程上多把 IMU、里程计或地图先验并入状态估计；若场景更接近大尺度平面分块，NDT [Magnusson](cite:magnussonThreeDimensionalNormalDistributions2009) 也会被用来替代纯最近邻 ICP，因为它用体素分布而不是单点对应约束局部表面。但 NDT 自己依赖体素分辨率，一旦分辨率和场景尺度不匹配，局部极值同样会增多。

**三维地图构建（3D Mapping）**：局部里程计只能保证短时间一致性，长时序地图需要回环检测把远距离误差重新拉回。此时“描述子 + ICP 精修”的两阶段流程比直接对整帧做局部 ICP 更合理，因为第一阶段负责把误差压入收敛域，第二阶段才负责毫米到厘米级精修。FPFH [Rusu et al.](cite:rusuFPFHFastPoint2009) 的价值在于特征计算量相对 PFH 下降约 75%，适合 CPU 上快速生成粗对应；FCGF [Choy et al.](cite:choyFullyConvolutionalGeometric2019) 则在 3DMatch 上把平均 Registration Recall 做到 0.82，32 维描述子在 FMR 指标下达到 0.952 ± 0.029，5 cm 体素时特征提取约 0.17 s/fragment，并在 KITTI 上以 RTE 4.881 cm、RRE 0.170°、成功率 97.83% 支撑后续 RANSAC+ICP 精修。这里的局限同样明确：若回环候选来自重复立面或低重叠片段，描述子先给出偏置候选，后续 ICP 只会把错误解精修得更稳定。

### 6.1.2 工业检测：CAD 对齐与表面质量检测

工业制造中，质量检测的核心问题是将扫描获得的实测点云与 CAD 设计模型对齐（CAD-to-Scan Registration），再计算逐点偏差来发现制造缺陷。

工业检测与自动驾驶的差别在于：前者很少需要从完全未知位姿开始搜索，更多时候已有治具、标靶或坐标测量机给出的粗位姿，因此局部精修是否稳定比全局入盆能力更重要。换言之，这里关心的不是“能否扛住 70% 外点”，而是“在高重叠、低噪声、初值较准的条件下，每次装夹都能否回到同一个配准结果”。

**ICP 在工业检测中的特殊要求**（典型表述为量级需求，具体数值随行业标准与传感器配置而变）：

- **精度**：工业检测普遍要求亚毫米级配准误差，并强调可重复性；在低噪声与高重叠条件下，点到面约束更容易达到此类精度目标。
- **初始化**：CAD 模型和实测点云之间的初始位姿在很多产线中已由夹具或测量坐标系给出，ICP 只需局部精修，[第 3.6 节](ref:sec:global-init)中的全局初始化一般不是主耗时。
- **外点处理**：实测点云可能包含工装夹具、支撑结构等“非被测体”点，这时先坏的是对应排序而不是闭式位姿更新，因此常把 TrICP 或 M-估计量放在对应残差筛选环节中。[Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002) 在 Frog 数据上给出一个典型例子：在约 3000 点、70% 重叠的条件下，TrICP 88 次迭代取得 MSE 0.10、耗时 2 s，而标准 ICP 45 次迭代仍停在 MSE 5.83、耗时 7 s。换言之，只要重叠率估计合理，截断式 ICP 足以覆盖“夹具点少量污染主件”的场景；但若真实重叠率估计过低，TrICP 会先把有效约束一起裁掉。
- **非刚体变形**：薄壁件扫描时可能发生局部弹性变形（装夹应力），严格刚体 ICP 会在变形区域产生系统性偏差。对于此类情况，需引入非刚体配准（如 BCPD）或分区域刚体配准策略，已超出本综述范围。

**代表性工业软件**：GOM Inspect、PolyWorks、ZEISS CALYPSO 等商业软件多以点到面 ICP、局部特征过滤和多阶段粗精配准作为内核，但公开文档很少披露统一协议下的配准数值，因此本节不把这些产品写成“基准结果”。可核查的公开证据主要来自方法论文和公开案例，而不是厂商手册。

### 6.1.3 机器人操作与抓取：位姿估计

六自由度抓取把 ICP 放在感知链的末端，因此它的任务不是从零完成目标识别，而是在检测、分割或粗定位之后把位姿误差压缩到控制器可接受的范围。之所以还需要 ICP，是因为抓取点常对姿态误差极敏感；只靠检测网络输出的 6D pose，末端执行器经常仍会在尖边、孔洞或对称面附近累积几度误差。

**流程**：以 RGB-D 传感器获取工件的深度图，生成工件可见表面的点云，与工件 CAD 模型的 ICP 配准直接输出变换矩阵（即工件在相机坐标系的位姿），机器人控制器以此规划抓取路径。

**挑战**：
- **部分可见**：机器人多只观测到工件的局部表面，低重叠率会显著缩小 ICP 的收敛盆。此时不能直接套用工业检测那套“已知初值 + 高重叠”假设，而要先用[第 3.6 节](ref:sec:global-init)的粗配准把误差压回局部可收敛区域。以合成对象配准为例，RPM-Net [Yew and Lee](cite:yewRPMNetRobustPoint2020) 在 ModelNet40 部分可见且含噪的设置下，把 isotropic rotation / translation error 降到 1.712° / 0.018；同一设置下 DCP 在 PREDATOR 论文复现实验中为 11.975° / 0.171，说明软对应和显式外点槽对“只看到局部表面”的任务更合适。若进一步转向真实低重叠室内片段，[第 3.7 节](ref:sec:dl-icp)中的 GeoTransformer [Qin et al.](cite:qinGeometricTransformerFast2022a) 在 3DLoMatch 上可把 RR 提到 75.0%，比依赖随机采样的旧式前端更稳定。
- **堆叠工件（Bin Picking）**：多个工件堆叠时，ICP 可能将相邻工件的点云误认为同一工件。深度学习实例分割先将工件分离，再对每个实例做 ICP，是当前最有效的工程方案。
- **位姿不确定性**：安全关键应用（如协作机器人，共融机器人）需要位姿估计的置信区间，而不仅是一组点估计。[第 3.4 节](ref:sec:transform)中的 Stein ICP [Maken et al.](cite:makenSteinICPUncertainty2022) 在 RGB-D 对称物体和稀疏 LiDAR 场景里使用 100 个粒子近似后验，KL 中位数约 0.6–5.7、OVL 约 0.7–0.9，运行时间约为 Bayesian ICP 的 1/8 到 1/5。它解决的是“多解并存时该不该相信当前估计”的问题；但代价也清楚，粒子后验的计算量比常规闭式 ICP 高得多，不适合无条件放进所有抓取循环。

### 6.1.4 医疗：手术导航与术中配准

手术机器人（如达芬奇系统的改进型）和计算机辅助手术（CAS）需要将术前 CT/MRI 影像与术中实时扫描对齐——即"术中配准"（Intraoperative Registration），这是 ICP 在医疗领域的核心应用。

**脊柱外科导航**：术前 CT 提供椎骨三维模型，术中以光学追踪仪扫描椎骨表面获得稀疏点云，二者的 ICP 配准用于估计当前解剖标志的位置。这里的前提是椎骨局部可近似为刚体，因此点到面约束仍有效；但出血、残留组织和器械遮挡会先破坏术中表面提取，再把错误点送入对应搜索，所以常与[第 3.2 节](ref:sec:outlier)中的鲁棒估计联合使用。若遮挡使可见表面过少，局部精修就会先因法向约束不足而失稳。

**软组织手术（如肝脏）**：软组织在呼吸、触压下发生非刚体变形，刚体 ICP 多半难以满足精度与一致性要求。此类场景需要非刚体配准或显式的形变建模；即便如此，刚体配准仍常作为非刚体优化的初始化环节。

**医疗配准的特殊性能要求**：可重复性、不确定性量化与安全失败模式。这里最重要的不是“平均误差更小”，而是当解出现多模态时系统能否拒绝输出错误位姿。Stein ICP 正适合承担这个角色，因为它明确输出变换后验而不是单点估计；相反，标准 ICP 即使给出很小残差，也可能只是沿某个对称方向滑入了错误局部极小。

| 场景 | 代表方法 | 原文场景与条件 | 指标 | 代表性数值 | 方法成立前提 | 先失效的环节 |
|------|---------|---------------|------|-----------|-------------|-------------|
| 车载 LiDAR 里程计 | LOAM [Zhang and Singh](cite:zhangLOAMLidarOdometry2014) | KITTI 10 Hz Velodyne，39.2 km，道路场景 | 平均位置误差 | 0.88% | 可稳定提取边/面特征，帧间重叠高 | 特征提取在弱结构场景先退化 |
| LiDAR-IMU 紧耦合建图 | FAST-LIO2 [Xu et al.](cite:xuFASTLIO2FastDirect2022) | 19 个公开序列；Intel/ARM；局部地图 + ikd-Tree | 最佳序列数、每帧处理时间、频率 | 17/19 序列精度最佳；1.82 ms/scan（Intel），5.23 ms/scan（ARM）；最高 100 Hz | IMU 去畸变可靠，局部地图连续更新 | 时间同步、外参或法向近似失配时残差先偏 |
| 回环粗配准 | FCGF [Choy et al.](cite:choyFullyConvolutionalGeometric2019) | 3DMatch 5 cm 体素；KITTI RANSAC 后端 | FMR、RR、RTE/RRE | 3DMatch RR 0.82；FMR 0.952 ± 0.029；KITTI RTE 4.881 cm、RRE 0.170°、成功率 97.83% | 片段间仍有可学习几何一致性 | 重复结构或极低重叠时粗对应先偏 |
| 工业局部精修 | TrICP [Chetverikov et al.](cite:chetverikovTrimmedIterativeClosest2002) | Frog 数据，约 3000 点，70% 重叠 | MSE、时间 | MSE 0.10，2 s；标准 ICP 为 MSE 5.83，7 s | 重叠率可估，初值已在局部收敛域 | 重叠率估计失真时有效点先被裁掉 |
| 抓取局部可见配准 | RPM-Net [Yew and Lee](cite:yewRPMNetRobustPoint2020) | ModelNet40 部分可见 + 噪声，约保留 70%，717 点 | isotropic rotation / translation error | 1.712° / 0.018 | 训练分布与部署几何相近 | 跨域和未见几何先导致软对应失真 |
| 安全关键位姿估计 | Stein ICP [Maken et al.](cite:makenSteinICPUncertainty2022) | RGB-D 对称物体 + 稀疏 LiDAR，100 粒子 | KL、OVL、运行时 | KL 中位数约 0.6–5.7；OVL 约 0.7–0.9；比 Bayesian ICP 快 5× 以上 | 需要显式后验而不是单点估计 | 粒子数不足时多模态后验先被低估 |
<!-- caption: 第 6.1 节应用场景中的代表性公开结果。表中数值来自各原论文或第 3 章已整理的数据表，用于说明“何种条件下该方法被采用”，不构成跨协议统一排行。 -->
<!-- label: tab:application-evidence -->

![ICP 主要应用场景及特性需求热图](../images/ch6-application-requirements.png)
<!-- caption: ICP 四大应用场景（自动驾驶、工业检测、机器人抓取、医疗手术）在六个关键特性（实时性、精度、鲁棒性、不确定性量化、部分重叠耐受、大规模点云）上的需求热图。该图按学术机制示意绘制，用于表达相对需求强弱，不对应统一基准下的具体测量数值。 -->
<!-- label: fig:application-requirements -->
<!-- width: 0.85\textwidth -->
<!-- ai-generated: true -->
<!-- ai-prompt: |
  Create a publication-quality academic figure for a thesis/survey paper.
  Use a unified academic publication figure style:
  - White background
  - Flat clean vector illustration
  - Crisp lines
  - Balanced whitespace
  - No photorealism, no 3D rendering, no poster style, no marketing style
  - The figure must read like a survey-paper conceptual diagram, not a product graphic
  - Because the body text does not define a unified benchmark, render this as a conceptual heatmap / mechanism illustration, not as a real experimental chart
  Global color system and semantic consistency:
  - Main structure / processing units: deep blue #2B4C7E
  - Memory / storage / auxiliary blocks: teal blue #3C7A89
  - Data / intermediate state / candidate flow: orange #D17A22
  - Normal / retained / valid region: dark green #5B8C5A
  - Conflict / bottleneck / pruned / invalid: dark red #A23B2A
  - Text dark gray #333333
  - Borders medium gray #888888
  - Background blocks light gray #EDEDED
  - Keep total colors within 5-6 colors, avoid rainbow palette
  Layout:
  - Single main panel heatmap, centered, with strict alignment and even margins
  - 4 rows x 6 columns grid with thin medium-gray gridlines
  - Right-side vertical legend/colorbar, fixed and neatly aligned
  - Use rounded-rectangle outer framing and consistent spacing
  Typography:
  - Chinese-first academic labeling, concise and verifiable
  - Main title largest, axis labels second, cell labels third, note smallest
  - Clean thesis-like sans-serif with good CJK support
  - Title: "ICP 应用场景需求热图（机制示意）"
  Language:
  - All in-chart text in Chinese only
  Rows (top to bottom):
  - 自动驾驶
  - 工业检测
  - 机器人抓取
  - 医疗手术
  Columns (left to right):
  - 实时性
  - 精度
  - 鲁棒性
  - 不确定性量化
  - 部分重叠耐受
  - 大规模吞吐
  Data handling:
  - Show centered integer scores in each cell
  - Treat values as schematic ordinal levels only, not benchmark numbers
  - Values:
    自动驾驶: 5, 3, 5, 2, 3, 5
    工业检测: 2, 5, 3, 1, 2, 2
    机器人抓取: 3, 4, 4, 4, 5, 2
    医疗手术: 3, 5, 4, 5, 3, 1
  Heatmap color:
  - Sequential scale derived from the main deep blue system, from very light gray-blue to deep blue #2B4C7E
  - Keep cells readable and publication-safe
  - Colorbar ticks at 1, 2, 3, 4, 5
  Note:
  - Add a small bottom note in dark gray:
    "注：评分为机制示意，用于表达相对需求强弱，不代表统一基准下的定量结果。"
-->

### 6.1.5 场景-算法匹配总结

| 应用场景 | 推荐 ICP 变体 | 推荐加速方案 | 关键约束 |
|---------|------------|-----------|--------|
| 自动驾驶 LiDAR 里程计 | P2Pl ICP + 紧耦合里程计框架（如 FAST-LIO2） | ikd-Tree/并行化，必要时硬件加速 | 严格延迟预算、大规模点云吞吐 |
| 工业 CAD 对齐 | GICP 或 P2Pl + 鲁棒估计 | 高精度数据结构与稳定法向估计 | 亚毫米级误差控制、可重复性 |
| 机器人 6-DOF 抓取 | 全局粗配准 + ICP 精修 | 多线程 + 合理降采样 | 低重叠与遮挡、实例混叠风险 |
| 医疗术中配准 | 概率 ICP / 不确定性量化框架 | 可靠性优先的实现与验证 | 安全失败模式、不确定性告警 |
<!-- caption: 四大应用场景的 ICP 变体和加速方案推荐总结，包括关键约束条件。 -->
<!-- label: tab:application-recommendation -->

应用场景的差异决定了“先解决什么问题”。自动驾驶先解决时延和退化方向，工业检测先解决重复精度与夹具外点，机器人抓取先解决部分可见和实例混叠，医疗配准先解决错误解告警。由此可见，[第 3 章](ref:sec:variants)的方法差异并不是抽象的目标函数差异，而是不同失败模式的应对路径。[第 6.2 节](ref:sec:benchmarks)将进一步说明，为什么这些场景不能用同一组数据集和阈值做简单并排比较。
