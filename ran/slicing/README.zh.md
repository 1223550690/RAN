# slicing 接口文档

职责：把业务映射到网络切片，并输出调度器可使用的切片策略。

输入：
- `service_type`
- 未来可加入历史 QoS、拥塞状态、AI controller 输出

输出：
- `slice_id`
- `SlicePolicy`

MVP 简化：
- `video_upload -> embb`
- `game -> urllc`
- `message -> mmtc`
- AI slicing controller 仅保留函数入口，当前返回固定策略。
