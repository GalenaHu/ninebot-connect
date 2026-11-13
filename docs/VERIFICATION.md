# 九号车联验证记录

## 已有实账号证据（2026-11-13）

用户在自己终端输入账号密码，未通过聊天传递。独立 Python 验证程序完成 Passport /v6 密码登录、业务登录、车辆列表和动态数据解密。电量93、精准续航36.7公里与用户 App 一致。此结果验证协议路径，不能当作本集成已在用户 HA 安装后的运行证明。

## 官方 App 静态证据

APK 为用户从官方网站下载的国内版6.10.13，SHA256 `040549277664993e1b5c27d92c297f2c1512781a3e3d7a88ec9fd6790c748376`。

- PassportApiClient.refreshAccessToken：`/v3/user/refresh`，body 为 `access_token`、`refresh_token`、`device=ANDROID`；签名包含公共客户端参数、clientKey、毫秒timestamp、url及body。
- Passport success 为90000（兼容整数/字符串）；SDK90016过期错误。车辆业务成功0/1单独处理。
- LocationCard V2/V3将响应latitude/longitude解析后传入gps84_To_Gcj02；GPSUtil实现包含WGS84→GCJ02变换。HA保留原始WGS84。
- DynamicViewHolder→UtilsKt.toBool先尝试严格布尔字符串，再比较字符串"1"。charging用于setChargingSync；pwr用于mainBatteryOnline。
- lock_status的UI与acc_status组合，不能证明独立1/0对应已锁/未锁。首版仅展示原始代码，默认关闭。
- 同APK的assets/cap_center/feature_core_1.json，feature_trace_recent明确绑定动态数据端点的total_mileage，公制km/factor1、英制mi/factor0.621，累计里程单位为公里。lastupdatetime与除以1000后的serverTime直接比较，已确认秒；gnss_time尚未在静态调用中确认，按数值形态兼容Unix秒/毫秒，非法值保持未知。
- SDK未找到可靠的令牌有效期字段/单位；业务域过期错误码尚无完整证据。只对明确的HTTP401/90016尝试刷新；未知业务错误保守处理为协议失败，不猜测触发刷新。

## 本版本验收

环境：Python3.14.7、Home Assistant2026.11.0、aiohttp3.14.5、cryptography50.0.2。2026-11-13最终验证：**38项测试全部通过**；ruff check、ruff format --check、mypy（12个组件源码文件）通过。

覆盖：Passport/业务成功码区分、并发过期只刷新一次、令牌轮换与身份核对、失败进入重认证、重定向拒绝、解压后响应大小限制、HTTP429暂停、12车队列中止、单车异常隔离、消失车辆不可用、空列表小时缓存、固定加密向量、真实aiohttp本机网关的RSA/AES完整请求响应往返；以及HA配置、去重、重新认证、选项更新、实体与GPS注册、卸载重载、新HA实例从磁盘令牌恢复、删除条目清除存储、诊断脱敏。

两项独立审查发现的令牌保存触发重载、限流后继续启动排队请求均已修复并回归验证，复核通过。细节见REVIEW.md（源码包内）。

单元/集成测试全部使用合成身份、车号、令牌与公共测试坐标，不含真实位置或账号数据。HA核心框架真实运行，九号网络由本机网关或请求边界模拟；未在用户的HA实例中安装运行，不能将这些测试宣称为实际车辆持续运行结果。

刷新端点参数已经静态核实；真实过期令牌轮换尚未由用户实账号验证。首版需要在用户HA安装后观察实际过期响应及重新认证行为。真实服务器未提供的错误分支不能以模拟测试宣称通过实测。
