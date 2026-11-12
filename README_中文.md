# EE3033 新增障碍物搜索版：安装与测试流程

实际 ROS 包名、Python 模块名、resource 和全部命令均为 `ee3033_project`。这是基于旧版项目补齐的完整替换包，不需要手工合并 Python 文件。保留旧版 YOLO 工具，但新任务入口不启动、不依赖 YOLO。

## 1. 能完成什么，先确认什么

流程：无目标地图 → AMCL 定位 → 自动生成可达观察点 → 搜索原地图空地中的新增回波 → 多帧、多位置确认 → 报告 map 坐标 → 取消搜索并等待 Nav2 的最终取消结果 → 自主返航 → 核验起点距离及停车状态。

- 颜色、类别和预先给定的形状不是输入；目标必须与 2D 雷达扫描平面相交，并有足够有效回波。
- 适用于“唯一新增、静止且可见的物体”。如果同时新增人、椅子等其他东西，雷达无法判断考官指定的是哪一个；程序遇到多个稳定候选物会拒绝猜测。
- 无法保证识别紧贴墙壁、藏在遮挡物后、低于雷达、透明或回波不足的目标。默认候选点距静态障碍/未知区需约 20 cm；墙边目标存在漏检可能。
- 未知物体的被遮挡部分不能从有限雷达视角唯一恢复。输出是多视角“已观测表面范围的中点”，不是任意形状物体精确几何中心。评分以什么位置为参考，应提前向考官确认。
- 要先解决地图畸变与定位错位。本版不会通过扩大协方差阈值来假装定位可靠。
- 搜索路线兼顾静态地图可见区域与行走距离；这是一种加速启发式，不保证最短时间或绝对覆盖。真实避障由现有 Nav2 costmap/controller 完成。

项目说明要求自主搜索、报告 map 中以米为单位的 (x,y)、返航到指定起始区域并停止；正式自主阶段不允许手动遥控、选导航目标或输入目标位置。以下手动选点仅用于准备和测试。

## 2. 文件和接口

| 文件 | 用途 |
|---|---|
| ee3033_project/ee3033_project/obstacle_core.py | 地图差异、聚类、多目标关联和多位置确认，无 ROS 依赖 |
| ee3033_project/ee3033_project/obstacle_detector.py | /scan、时间戳 TF、AMCL、静态墙匹配、RViz 标记 |
| ee3033_project/ee3033_project/coverage.py | 利用 360° LiDAR，减少四方向转圈和重复停靠 |
| ee3033_project/ee3033_project/mission_manager.py | 起点记录、搜索、取消、上报、返航、运行监测和 JSON 结果 |
| ee3033_project/config/obstacle.yaml | 新版完整任务参数 |
| ee3033_project/launch/obstacle_mission.launch.py | 正式任务，默认等待 start 服务 |
| ee3033_project/launch/nav_test.launch.py | 单点往返测试 |
| ee3033_project/launch/integration_demo.launch.py | 私有 ROS 接口的理想运动测试夹具 |
| install_into_workspace.py | 安装完整包，先备份旧代码，无递归删除 |

| 接口 | 含义 |
|---|---|
| /ee_project/start，std_srvs/srv/Trigger | 开始任务，起点在检查通过时自动记录 |
| /ee_project/abort，std_srvs/srv/Trigger | 请求取消任务；需要 Nav2 确认，不能替代物理急停 |
| /ee_project/status，std_msgs/msg/String | JSON 任务状态、等待原因、目标、停车核验、结果文件 |
| /ee_project/detector_status，std_msgs/msg/String | 墙匹配比例、候选物、多帧/基线等诊断 |
| /target_position，geometry_msgs/msg/PointStamped | 已通过检测器确认的观测，不是原始单帧噪声 |
| /ee_project/confirmed_target，geometry_msgs/msg/PointStamped | 任务正式上报结果，transient local |
| /ee_project/home，geometry_msgs/msg/PoseStamped | 本次任务记录的指定起点 |
| /ee_project/target_markers，visualization_msgs/msg/MarkerArray | RViz 中的候选物 |

任务节点不发布 /cmd_vel，只有现有 Nav2 负责运动。传感器/定位/检测健康连续丢失约 3 秒时会请求取消，状态变为 ABORTED；不会在失去定位时盲目返航。

## 3. 安装：在真正运行 ROS 的环境中操作

建议把编译、任务节点放在小车的 ROS 2 Humble 容器（通常是 /home/ros2_ws）中；Ubuntu 虚拟机主要运行 RViz2。**VS Code 本机终端、SSH 终端和容器终端不是同一个环境。** 以下编译和实车节点命令均指小车容器内终端。如果你的 ROS 工作区实际在虚拟机中，按实际路径替换。

1. 下载 zip，传入上述环境的 /tmp。测试前先退出旧版 mission_manager、YOLO target_localizer、路径点循环和旧导航测试节点，避免多个程序抢发目标。
2. 解压到 /tmp，安装脚本自动把原来的 src/ee3033_project 移到工作区的 ee3033_backups 下；备份目录有 COLCON_IGNORE。

```bash
python3 -m zipfile -e /tmp/EE3033_Obstacle_Mission_v2.zip /tmp
python3 /tmp/EE3033_Obstacle_Mission_v2/install_into_workspace.py --workspace /home/ros2_ws
```

3. 在独立构建目录编译，不需要删除原来的 build/install/log。先加载课程已有包。

```bash
source /opt/ros/humble/setup.bash
cd /home/ros2_ws
source install/setup.bash
colcon --log-base log_obstacle build --packages-select ee3033_project --symlink-install --build-base build_obstacle --install-base install_obstacle
source install_obstacle/local_setup.bash
ros2 pkg prefix ee3033_project
ros2 pkg executables ee3033_project
```

prefix 应指向 /home/ros2_ws/install_obstacle/ee3033_project，executables 应包含 obstacle_detector 和 mission_manager。否则当前终端还在用旧包。

依赖是课程 ROS 2 消息、Nav2、TF 和标准 Python 库，不需要安装 NumPy/SciPy/YOLO。若构建报告缺依赖，在现有课程工作区按错误信息补齐；正常已完成 Lab 5 的环境应已有 Nav2/TF。

后面每开一个新容器终端，先执行：

```bash
source /opt/ros/humble/setup.bash
source /home/ros2_ws/install/setup.bash
source /home/ros2_ws/install_obstacle/local_setup.bash
```

## 4. 测试 A：纯逻辑与理想 ROS 全流程

### A1. 无需 ROS 的回归测试

```bash
cd /home/ros2_ws/src/ee3033_project
python3 -m unittest discover -s test -v
python3 /tmp/EE3033_Obstacle_Mission_v2/test_installer.py -v
```

预期分别 73 项与 3 项通过。包括未知区/墙边过滤、地图原点旋转、模拟 360° 回波、明显 TF 偏移、多目标歧义、移动目标、取消后才返航、返航失败不能算成功等。

### A2. 在 ROS Humble 中验证消息、TF 和 action 衔接

在**专门的测试终端**使用独立 domain，另一个监控终端也设置相同值。退出后关闭这些终端，避免把模拟 domain 带到实车。

```bash
export ROS_DOMAIN_ID=183
export ROS_LOCALHOST_ONLY=1
ros2 launch ee3033_project integration_demo.launch.py
```

另一个已 source 的终端：

```bash
export ROS_DOMAIN_ID=183
export ROS_LOCALHOST_ONLY=1
ros2 topic echo /ee_project/status
```

预期状态经过 WAIT_READY、SEARCH、STOPPING、RETURN、VERIFY_HOME，最终为 DONE。日志打印 TARGET_CONFIRMED。目标 fixture 的参考圆心约 (1.2,0.8)，表面估计允许有偏差；这只检验合成场景。

测试夹具使用 /ee_project/mock_* 传感器、私有 action 和私有 TF 主题，不发布速度。它按理想运动响应目标，**不模拟车体平衡、碰撞、实际 Nav2 规划或避障**。本次交付环境没有 rclpy，因此这里的 ROS 运行验证需要你在 Humble 中完成，不能视作已经通过。

完成后 Ctrl+C 关闭。可另开一次无目标测试：

```bash
ros2 launch ee3033_project integration_demo.launch.py with_target:=false
```

预期完成搜索并返航后为 NOT_FOUND，不能报告 DONE。时间可能明显比有目标测试长。

## 5. 测试 B：无目标建图、加载地图、检查定位

回到用于实车的正常终端，ROS_DOMAIN_ID、ROS_LOCALHOST_ONLY 和 RMW 要与课程原配置一致。不要把测试 domain 183 复制到实车终端。

1. 按 Lab 4 完成无目标建图，保存 yaml/pgm。建图收尾时回到允许的起始区域。不要在地图中提前放入目标。
2. 结束 SLAM 和遥控程序。导航阶段只运行保存地图 + AMCL，不同时运行另一套 SLAM map->odom。
3. 按 Lab 5 第 3–4 页确认 balance_mapping 安装的地图与 balance_bringup launch 中引用的是刚保存的地图。地图或 launch 改过时，按讲义重建相关课程包。
4. 容器终端 1 启动课程导航系统：

```bash
ros2 launch balance_bringup balance_known_map_waypoint_bringup.launch.py start_waypoints:=false
```

此 launch 根据 Lab 5 会同时启动底盘、LiDAR、map server、AMCL 和 Nav2；不要再重复启动第二套底盘/雷达/导航。

5. 虚拟机中启动 RViz2，Fixed Frame=map，显示 /map、/scan、TF。/map Durability 设为 Transient Local。用 2D Pose Estimate 设置指定起点的真实位置和朝向。
6. 检查几面固定墙是否同时与实时雷达重合。整张图倾斜通常可以；内部墙壁错角、重影、局部变形需要先处理。

容器终端 2：

```bash
ros2 run ee3033_project preflight_check
```

若 base frame 实际是 base_link：

```bash
ros2 run ee3033_project preflight_check --ros-args -p base_frame:=base_link
```

确认 ready=true；若无 amcl_pose，先开启下一节只检测节点，它会自动调用 AMCL 的 /request_nomotion_update，再重试检查。节点不会自动伪造初始位置。

## 6. 测试 C：只检测、不运动

不要同时启动完整任务。在容器终端 2：

```bash
ros2 launch ee3033_project obstacle_mission.launch.py detection_only:=true
```

容器终端 3：

```bash
ros2 topic echo /ee_project/detector_status
```

- 空场地应 ready=true、静态匹配比例通常较高、没有稳定候选。先检查 20–30 秒。
- 准备测试时，在原地图空地放一个雷达能扫到的物体。先距离墙壁至少 0.3–0.4 m，距离小车约 1–2 m。
- 应出现 tracks、frames 增长。小车一直静止时 baseline_m≈0，**暂不报告目标是正常行为**：需要不同位置观测。
- 准备测试中可按课程允许的方式轻缓移动约 0.25–0.4 m，目标仍需在视野中。最终应 reason=confirmed，/target_position 有数据。正式自主任务中由程序移动，不得再人工遥控。
- RViz 加 MarkerArray，topic=/ee_project/target_markers，可查看候选物。

```bash
ros2 topic echo /target_position
```

测试完成 Ctrl+C 关闭只检测节点，然后结束遥控。不要让它与下一次完整任务重复启动两个 detector。

## 7. 测试 D：先单点往返

课程导航终端 1 保持运行。容器终端 2 运行单点测试，x/y 必须取自你当前地图中的实际空地，下面的 1.0、0.5 只是示例：

```bash
ros2 launch ee3033_project nav_test.launch.py dry_run:=false goal_x:=1.0 goal_y:=0.5
```

如果希望本测试与完整任务采用相同的间隙、停止和超时参数，可传配置路径：

```bash
ros2 launch ee3033_project nav_test.launch.py dry_run:=false goal_x:=1.0 goal_y:=0.5 config:=/home/ros2_ws/src/ee3033_project/config/obstacle.yaml
```

终端 3（已 source）：

```bash
ros2 service call /ee_project/start std_srvs/srv/Trigger "{}"
ros2 topic echo /ee_project/status
```

预期走到目标、返航、停车，最终 TEST_DONE。仅启动 launch 不会开始运动，必须调用 start。失败时看 waiting_for / last_error，尤其是 AMCL、scan、TF 和起点间隙。先不要直接放宽定位门槛。

这个入口会忽略目标检测。测试完成关闭终端 2 的 nav_test，避免与完整版重复运行任务节点。

## 8. 测试 E：完整自主搜索、报告、返航

1. 让小车位于指定起始区域并可靠定位；目标按测试安排在建图后放入。场内人员尽量退出雷达范围，移除其他新增物品。
2. 课程导航终端 1 保持运行，start_waypoints=false。
3. 容器终端 2：

```bash
ros2 launch ee3033_project obstacle_mission.launch.py
```

base_link 环境则加 base_frame:=base_link。map/scan 主题也可以通过 map_topic:=...、scan_topic:=... 指定。

4. 容器终端 3：

```bash
ros2 service call /ee_project/start std_srvs/srv/Trigger "{}"
```

只需发一次。检查通过时自动记录当前 map 坐标为 home；不是固定 (0,0)。

5. 容器终端 4 监控：

```bash
ros2 topic echo /ee_project/status
```

看正式上报坐标（即便晚打开终端也可读到）：

```bash
ros2 topic echo /ee_project/confirmed_target --qos-durability transient_local --qos-reliability reliable
```

预期状态：

| 状态 | 含义 |
|---|---|
| WAIT_READY | 等待地图、scan、TF、Nav2、AMCL、检测健康 |
| SEARCH | 行走和停靠期间持续检测；不同位置观测足够后确认 |
| STOPPING | 已确认，正在取消原搜索目标，等待 Nav2 的最终结果 |
| RETURN | 坐标已上报，Nav2 正在返航 |
| VERIFY_HOME | 检查距离起点及 odom 低速持续时间 |
| DONE | 目标已上报、已回到起点容差内，并满足停车核验 |
| NOT_FOUND | 搜索点用尽，未确认目标，已返航；不算任务成功 |
| TIMED_OUT | 搜索时间用尽后返航；不算任务成功 |
| FAILED / ABORTED / CANCEL_FAILED | 查看 last_error；不得把它当作完成 |

默认结果写在执行任务的环境中：

```bash
ls -lt ~/.ros/ee3033_results
```

JSON 记录坐标、单位、坐标系、估计方法、任务状态及搜索覆盖统计。dry_run 或理想 mock 结果都不能代替真实测试记录。

若需要中止准备测试：

```bash
ros2 service call /ee_project/abort std_srvs/srv/Trigger "{}"
```

这是软件取消。若取消未确认，需现场停止和检查；正式考核的人工干预按考官规则执行。

## 9. 常见问题与调参

本版启动时读取参数并缓存；修改配置后应停止相应项目节点，再重新 launch。不要仅 ros2 param set 后假定算法已动态更新。

| 现象/诊断 | 优先检查 |
|---|---|
| AMCL covariance exceeds configured thresholds | 初始位置/朝向、地图畸变、scan 与墙对齐；自动 no-motion 更新不等于能修复地图 |
| scan_map_misaligned_or_insufficient_static_returns | 墙对齐、scan 的 TF、视野里是否主要是人或目标；不是直接降低匹配阈值 |
| waiting_for_timestamped_scan_tf | 时间同步、scan.header.frame_id、TF 链和 TF 频率；节点不使用最新 TF 代替观测时刻 TF |
| waiting_for_fresh_amcl | /request_nomotion_update 服务名、AMCL lifecycle、/amcl_pose 主题；可能是还没设置 initial pose |
| tracks 有值但 baseline 很小 | 需要至少 0.20 m 的不同观测位置，继续自动搜索；静止重复扫描不能代替多位置观测 |
| multiple_new_objects | 多个稳定新增物体，不能唯一确定目标；准备测试时排除人员和其他新增物 |
| 小目标无 tracks | 扫描平面高度、有效点数、检测距离、未知区/墙边过滤 |
| Start pose lacks configured clearance | 起点贴墙或 clearance 太大；测量车体，选择真实安全起点，不要无依据减小 |
| Nav2 说成功但最终 FAILED | 起点误差过大，或 /odom 没有新消息，或尚未满足停车条件 |
| CANCEL_FAILED | 未收到 Nav2 最终取消结果；不会再发新目标，检查 Nav2 和现场车辆状态 |
| 返回旧功能/找不到新 launch | 每个终端重新 source 新 overlay，并检查 ros2 pkg prefix |
| 小车不绕开新障碍 | 检查课程 Nav2 的 obstacle layer 是否订阅 /scan；本包不修改或替代课程避障配置 |

最值得先核对的参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| mission_manager.clearance_m | 0.30 m | 保守正方形半边长，应包含实际车体和余量，需测量 |
| search_spacing_m | 0.9 m | 候选搜索点间隔；狭窄复杂地图可减小，时间会增加 |
| detection_range_m | 3.5 m | 检测器和搜索路线应使用相同值 |
| max_search_locations | 35 | 搜索点上限；大场地不足时增加，不代表无限覆盖 |
| wall_margin_m | 0.20 m | 墙/未知区隔离；更小可能多误检，更大可能漏墙边目标 |
| min_static_match_ratio | 0.65 | 保护定位质量；是启发式筛查，不是定位正确性的证明 |
| min_observation_baseline_m | 0.20 m | 多位置确认要求，不建议为了“立刻报告”设为零 |
| min_track_duration_s | 1.2 s | 稳定观测至少持续时间，另有 0.8 s 歧义等待 |
| home_tolerance_m | 0.30 m | 按考官起始区域容差修改；这里只是默认值 |

最快的可靠推进顺序：先通过单点实车往返和空场检测，再做完整任务；不要在 AMCL 明显错位时同时调检测和路径规划。完整任务默认只需一次 start，自动静止 AMCL 更新不需要你每 5 秒手工调用服务。

## 10. 已验证范围与来源

交付时执行环境为 Windows / Python 3.14；全部 Python 源码按 Python 3.10 语法解析检查通过，73 项项目逻辑测试、3 项安装器测试通过。当前没有 ROS 2/rclpy、没有连接小车，因此 colcon 构建、真实 ROS 消息/action 联调、真实避障与实车完成时间尚未验证。以上测试流程就是用于逐步完成这些验证的。

需求来源：EE3033 Project instructions.pdf，第 1–3 页；课程导航启动和 RViz 操作来源：Lab5_report.pdf，第 3–7 页。

- 项目要求：https://chatgpt.com/library?file_id=libfile_eec4689c59f88191859ca0c97eaf7aa1&account_id=personal
- Lab 5：https://chatgpt.com/library?file_id=libfile_7d71b70037208191a7ace4d17f115d62&account_id=personal
- Humble Nav2 action 取消/结果接口：https://api.nav2.org/nav2-humble/html/robot__navigator_8py_source.html
- Humble AMCL 源码（静止更新、更新门槛）：https://api.nav2.org/nav2-humble/html/amcl__node_8cpp_source.html
