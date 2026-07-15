# transport 接口文档

职责：表示 RAN 到核心网/数据网之间的传输边界。

输入：

- `TransmissionResult`
- `N3ForwardingResult`

输出：

- 经 backhaul、N3、N6 处理后的结果。

MVP 简化：

- N3 固定 2 ms。
- N6 固定 8 ms。
- backhaul 默认不拥塞，只保留容量限制接口。
