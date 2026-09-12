# Loop 调研笔记 · 2026-09-12（gh cli 同类经验汲取）

> loop 指令：以 gh cli 调研别人普通人怎么做为准。本轮两题：EdgeTTS 残项怎么修、P2P 缓存怎么起步。

## 1. EdgeTTS（P0 残项）：不要修，采纳

豆包在 Radxa 上手搓的 EdgeTTS 客户端正与 rustls 双 provider 冲突、WSS 403（UA/Origin）、X-Timestamp Z 后缀、Sec-MS-GEC 时钟窗口搏斗——**这些坑别人已经踩平并发布成 crate**：

| crate | 版本 | 下载量 | 更新 | 关键证据 |
|---|---|---|---|---|
| **msedge-tts** | 0.4.0 | **25058** | 2026-05-20 | 源码含 `Sec-MS-GEC`(2处) + `trustedclienttoken`(1处)，DRM 令牌机制已实现（gh code search 实测） |
| kothok-edge-tts | 0.2.10 | 780 | 2026-07-26（最新鲜） | Nayeem170/kothok-edge-tts |
| edge-tts-rust | 0.1.3 | 3148 | 2026-04-05 | 备选 |

**建议动作（给豆包）**：lly 的 EdgeTTS 模块改为依赖 `msedge-tts` crate（25k 下载=实战检验），自研代码退位为薄封装。信条 3：有先例不埋头修轮子。预期一次替换解决全部 403/rustls/时钟问题。

## 2. P2P 编译缓存（P1 零竞争项）：参考模式确认

新一轮检索（"attic nix cache" / "ipfs package cache" / "p2p build cache" / "webrtc compute sharing"）依旧零 P2P 命中，空白确认。找到两个参考实现模式：

- **zhaofengli/attic**（2063★，Rust，活跃）——多租户 Nix 二进制缓存：**节点侧缓存服务**的成熟形态（content-addressed blob 存储 + API 层）。非 P2P，但其存储/校验设计可直接借鉴。
- **buildfarm/buildfarm**（773★）——Bazel Remote Cache 协议参考实现：若节点暴露该协议，天然兼容 bazel 系工具。

**MVP 形态（原子化拆解，下轮开工）**：
1. 内容寻址 KV：blob 按 sha256 存取（~200 行 Rust，axum + 本地目录）
2. HTTP 前端：兼容 attic/bazel-remote 的 GET/PUT /cache/{hash}
3. libp2p gossip：节点间 hash 清单交换 + 就近取块（WebRTC transport，NAT 穿透）
4. 验收：Radxa ↔ 本机互取一个真实 cargo 产物，hash 校验通过

## 3. 下一轮（loop tick）计划

- 起步 P2P 缓存 MVP 第 1 原子（内容寻址 KV，Rust）
- 持续以 gh cli 调研"普通人怎么做"：下一个课题 = 记忆市场的普通人先例（除技能市场外的 agent 记忆/经验复用实践）
