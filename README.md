# lystack —— 个人零边际成本 AI 能力栈

> 注：栈名 lystack（lyco + stack）。zerostack 特指真实开源产品 gi-dellav/zerostack（Rust 极简 coding agent），已采纳接入而非同名。

> 状态面板（P0-P3 v2，2026-09-12 更新，合并 lain42.top/Radxa 实际进展）
> 主线：计算机消失，意图常驻。记忆包协议 → 工具层 → 节点网格 → 记忆市场。

## 0. 豆包侧进展核实（2026-09-12，AI 生成内容逐条核验）

| 声明 | 核验结果 | 证据 |
|---|---|---|
| zerostack = gi-dellav/zerostack，纯 Rust 极简 agent | ✅ 真 | 1666★，GPL-3.0，Rust，活跃（pushed 09-10）；latest **v1.8.4** |
| Radxa 已装 zerostack 1.7.2 | ✅ 真（但**落后一版**） | 最新为 1.8.4（09-07 发布），建议升级 |
| lly（EdgeTTS/Transcribe/FileTool）基于 lilyco | ✅ 真 | `--list` 输出与 `lilyco-core/src/registry.rs` 的 aliases/CommandSchema/ArgKind 完全吻合 |
| rustls 0.23 双 provider（ring+aws_lc_rs）需 install_default | ✅ 真 | rustls 0.23 文档行为：双特性并存时进程级 CryptoProvider 不会自动安装，首次 TLS 即 panic |
| EdgeTTS Sec-MS-GEC 5 分钟时钟窗口 | ✅ 真 | 微软 DRM 机制；Radxa 时钟偏差会导致 403/断连，查时钟方向正确 |
| uv 版本（server 0.11.32 / Radxa 0.12.13） | ✅ 真 | uv 最新即 0.12.13；server 侧落后可升 |
| Clash 订阅导入失败 | ✅ 根因已定位 | base64 解出 `vless://…` —— 订阅是 v2ray 节点列表**不是 Clash YAML**，导入器行为正确；需 subconverter 转换或换支持节点列表的客户端 |
| lly/whisper 已在 Radxa 编译成功、FileTool 通 | ⚠️ 设备侧，未复核 | 本机无法直查 Radxa 状态；以豆包会话日志为准 |

## 1. P0-P3 v2（ROI 更新版）

> 打分 1-5（成本高分=便宜）。对比 v1：**两项被豆包提前完成，一项从自研改为采纳（信条 3：不重复造轮子）**。

| 项 | 需求 | 协同 | 成本 | 护城河 | 变化 | **P级** |
|---|---|---|---|---|---|---|
| ~~Radxa 节点上线~~ agent 代码+lly+whisper+zerostack 已上机 | 3 | 5 | 4 | 2 | ✅ 豆包完成大半 | **P0 残项** |
| EdgeTTS（P0 残项） | 4 | 4 | 4 | 1 | ✅ **已解决：lly v0.2.1 换 msedge-tts crate，GitHub CI 构建（zigbuild musl），Radxa 实测 32112B 有效 MP3**——自研协议层退役 | **P0 ✅** |
| ~~lilyco 转化补漏~~ install.sh sha256 + topics + roadmap | 4 | 4 | 5 | 1 | ✅ 本会话完成 | **P0 ✅** |
| ~~记忆包 spec+Python 原型~~ mpkg verify 全绿+篡改检测 | 5 | 5 | 5 | 5 | ✅ 本会话完成 | **P0 ✅** |
| lly 收编入 git + 每调用产 trace（mpkg 素材） | 4 | 5 | 4 | 3 | 🆕 取代原"自研 filetools" | **P1** |
| 采纳并配置 zerostack（升 1.8.4 + commandcode provider + MCP 接 lly） | 5 | 5 | 5 | 2 | 🔄 自研→采纳（GPL-3.0 自托管无碍；lilyco 经 MCP/进程边界互操作无传染） | **P1** |
| P2P Rust 编译缓存节点（libp2p/webrtc，零竞争） | 4 | 3 | 2 | 5 | ✅ **cache-node v0.2.0 完成：内容寻址 KV + /manifest + /sync，三平台（Win/WSL/Radxa）三节点收敛 3 blobs/1328312B，1.3MB 真实产物字节级一致**；libp2p/WebRTC 传输归 P2 | **P1 ✅** |
| 订阅格式转换器（base64 vless → Clash YAML） | 3 | 2 | 5 | 1 | 🆕 已核实根因，一次性小工具 | **P1 低** |
| 视频知识蒸馏管线+格式 spec（ffmpeg→ASR→切片→OCR 验证） | 4 | 4 | 1 | 5 | ✅ **机制验收达成：kbv-distill.sh 六原子 CLI 化，自举测试视频（lly tts 合成旁白）→ 查询 cargo new 命中切片+帧图+OCR 证据**；真实教程视频接入待内容 | **P2 ✅** |
| 记忆市场注册表 MVP（publish/search/verify/结算） | 5 | 5 | 2 | 5 | ✅ **MVP+信任复利上线**：2 包 3 attestation（跨 Win/Linux 双平台回放），attest 计数入索引，gh api 实时读取；结算待 lain42.top | **P2 ✅** |
| openvibe（暂名，对比语料层：prompt 谱系+每步溯源+跨作者对比） | 5 | 5 | 2 | 5 | 🆕 spec §8 已留钩子；名字已被占需另定 | **P2** |
| 算力平台 WebRTC 化 + 降级链路由 + GUI-grounding 基准 | 3 | 4 | 2 | 4 | ✅ **WebRTC Phase 1 信令平面上线**：signal-relay 常驻 lain42.top（/signal/* HTTPS，pingap 反代+systemd），外部读写实测；Phase 2 = cache-node 接 webrtc-rs 数据通道 | **P2 半 ✅** |

**本期主题校准**（商业=痛点，痛点=Token 解决）：商业软件的护城河从"拥有软件"转移到"拥有语料与验证"。openvibe 是**需求侧传感器**（收痛点+解法），mpkg 市场是**供给侧资产**（可验证程序性知识），lilyco/zerostack 是**能力总线**，Radxa 网格是**零边际成本底盘**——四件套互相喂养。

## 2. 目录

```
spec/mpkg-v0.md          记忆包格式规范 v0（含 openvibe provenance 钩子 §8）
proto/py/mpkg.py         build/check/verify CLI（Python 原型；Rust 基建后继）
proto/py/examples/make-snake-game/   验收示例：回放→可玩贪吃蛇，attestation 全绿
nodes/cache-node/        P1-2 第一原子：内容寻址 (sha256) KV 缓存节点（Rust/axum）
docs/research-loop-20260912.md       EdgeTTS 采纳建议 + P2P 缓存参考模式
```

**cache-node 跨平台实测矩阵（2026-09-12，同一份源码，零改动）**

| 平台 | 二进制 | 角色 | 结果 |
|---|---|---|---|
| Windows x86_64 (MSVC) | debug exe | 服务端 | ✅ 201/dedup/roundtrip/篡改400/404 |
| WSL Ubuntu-24.04 (x86_64-musl 静态 1.2MB) | 单文件 | 服务端 | ✅ 同套验收全绿 |
| Radxa Debian (aarch64-musl 静态 1019KB) | 单文件，**常驻运行** | 节点 | ✅ PID 见 /home/radxa/cn.log |
| Windows 客户端 → WSL 服务端 | 跨机 TCP | 联调 | ✅ 201/roundtrip 一致/篡改 400 |
| Windows 客户端 → Radxa (真实 LAN) | 跨机 TCP | 联调 | ✅ 201/roundtrip 一致/篡改 400 |

复现：`BASE=http://192.168.10.165:9910 bash nodes/cache-node/smoke.sh`

复现：
```bash
python proto/py/mpkg.py build  proto/py/examples/make-snake-game
python proto/py/mpkg.py check  proto/py/examples/make-snake-game/dist/*.mpkg
python proto/py/mpkg.py verify proto/py/examples/make-snake-game/dist/*.mpkg --out att.json
# 预期: ok:true, steps 3/3, verify 1/1, id=sha256:032bfc02…
```

## 3. 技术分工（已定，2026-09-12 升级：CI 自动编译架构）

- **构建 = GitHub Runner 全自动**（用户指令：不做本地/设备编译）：`release.yml` 触发规则——推 tag `v*` 或手动 dispatch → zigbuild 容器交叉 musl（aarch64 + x86_64）+ windows MSVC → **sccache**（mozilla-actions，GHA 缓存后端）加速 → SHA256SUMS → 自动发 Release。设备侧只需下载预编译产物，零工具链依赖。
- **Python/TS**：原型、市场前端、spec 参考实现（快迭代，验证想法）
- **Rust**：基础设施性能压榨——lilyco（能力总线，已在 crates.io）、cache-node（P2P 缓存节点，已建仓 CI 化）、mpkg 的 Rust 版 verifier、zerostack（采纳，不自研）
- **连通性教训**：Clash fake-ip 劫持 + 坏订阅 = GitHub 间歇全断；Radxa 自愈守护（push-when-up.sh）在连通窗口自动完成 tag 推送与触发——设备端自动化对不可靠网络是刚需。
