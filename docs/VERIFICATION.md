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
- SDK未找到可靠的令牌有效期字段/单位；业务域过期错误码尚无完整证据。只对明确的HTTP401/90016尝试刷新；未知业务错误保守处理为协议失败，不猜测触发刷新。

## 本版本验收

运行结果将在打包时写入。单元/集成测试全部使用合成身份、车号、令牌与公共测试坐标，不含真实位置或账号数据。

刷新端点参数已经静态核实；真实过期令牌轮换尚未由用户实账号验证。首版需要在用户HA安装后观察实际过期响应及重新认证行为。真实服务器未提供的错误分支不能以模拟测试宣称通过实测。
