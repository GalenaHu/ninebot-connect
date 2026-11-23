# 九号车联 · Ninebot Connect

将中国大陆九号电动车云端信息接入 Home Assistant。集成域 `ninebot_connect`，可与 `ninebot` 并存。面向 **Home Assistant 2026.11.x / Python 3.14**。

## 安装

### Marketplace / HACS

需要 Home Assistant **2026.11.0 或更新版本**。本仓库可通过链接添加，无需在默认目录中搜索。

1. 打开「设置 → Marketplace」，选择右上角 **Add from link**。
2. 按提示连接 GitHub，输入 `https://github.com/GalenaHu/ninebot-connect`，选择 **Add**；如果要求选择类型，选择 **Integration**。
3. 打开「九号车联」并安装。如果 HA 提示需要重启，先重启。
4. 在「设置 → 设备与服务 → 添加集成」中搜索「九号车联」，输入九号账号密码。

使用仍提供 **Custom repositories** 菜单的 HACS 时，输入相同仓库地址，类型选择 **Integration**，添加后下载安装。HA 版本仍须符合上述最低要求。

也可通过 [My Home Assistant 链接](https://my.home-assistant.io/redirect/hacs_repository/?owner=GalenaHu&repository=ninebot-connect&category=integration) 打开仓库。

官方参考：[添加自定义仓库](https://www.home-assistant.io/integrations/marketplace/#custom-repositories)、[仓库结构](https://contributors.home-assistant.io/marketplace/reference/repository-structure/)。

### 手动安装

1. 在本仓库选择「Code → Download ZIP」下载源码并解压，将 `custom_components/ninebot_connect` 整个目录放入 HA 配置目录的 `custom_components` 中；也可使用本地构建的安装包。
2. 重启 Home Assistant。
3. 在「设置 → 设备与服务 → 添加集成」搜索「九号车联」（英文界面为 Ninebot Connect）。
4. 输入与中国大陆九号 App 密码登录时相同的账号和密码。

密码仅在本次认证时发送给固定的九号官方认证服务器，**不写入集成配置**。访问令牌、刷新令牌、账户标识和随机设备标识保存在 HA 的配置条目中；它们同样敏感，请保护 HA 配置及备份。删除配置条目会删除该条目保存的令牌，不等于在九号服务器撤销会话。

无需抓包、代理、临时根证书、APK、ninecli、命令行脚本或额外服务。之前抓包用过的手机 Wi-Fi HTTP 代理应关闭；完成抓包后可以移除临时证书。

## 信息与更新

每辆车独立创建设备，包含电量、精准预计续航、充电、主电池在线、累计里程、车况上报时间、定位上报时间、查询时间与 GPS 地图实体。

- 默认每 **120 秒**查询；集成选项可调为 **30–3600 秒**。车辆列表每小时更新，新增车辆自动出现。
- 地图显示九号云端最后一次上报的 **WGS84** 坐标，定位时间单独显示。查询成功不代表车辆刚刚上传位置；休眠、离线、无卫星信号时位置可能较旧。
- `pwr` 已从 App 确认表示**主电池在线**，不能据此判断整车是否启动。
- `lock_status` 的独立枚举含义尚未完成确认。提供默认关闭的「锁状态代码」传感器，仅保留0/1，不据此声称已锁或未锁；其他值显示未知。
- 缺失或不合法数值显示未知，不补零。单车查询失败只令该车不可用；从账号列表消失的车辆保留实体并标为不可用。
- 无控车实体或服务，不提供解锁、启动、鸣笛、开座桶、轨迹、行程和电池详情。

## 认证与故障

登录分为 Passport 认证和车辆业务会话。SDK 确认的刷新请求会在识别到过期响应时执行一次，并更新完整令牌对；失败或刷新后仍被拒绝时，HA 提示重新认证。重新认证必须使用原账号。由于官方 SDK 未提供已核实的令牌有效期字段，插件不猜测有效期。

HTTP 429 会暂停查询并遵守有上限的 Retry-After。网络错误、协议结构变化与单车失败不会触发反复密码登录。验证码或风控请先在官方 App 完成；插件不绕过验证。

九号没有为本项目提供公开的稳定接口承诺。首版仅使用已核对的中国大陆北京域名及路由；其他地区不在支持范围内。服务端变更可能需要升级插件。

## 安全与隐私

网络请求只允许代码中列出的 HTTPS 主机和路径，保持 TLS 校验，拒绝重定向。所有密码、令牌均不放在 URL 中。生产代码不运行子进程、不下载或执行二进制。完整响应仅在当前请求期间处理，投影后只保留必要的车况字段；不保存车主资料、蓝牙密钥或完整车辆档案。

HA 状态及历史中会含车辆位置和时间；请自行设置 recorder 排除规则和地图访问权限。插件诊断只导出版本、数量、更新状态和是否有刷新令牌，不导出账户、车辆标识、令牌或坐标。请勿在问题反馈中上传 HA `.storage` 或原始抓包。

## 协议来源与验证

参见[验证记录](docs/VERIFICATION.md)。源码随包交付，可自行审查 [api.py](custom_components/ninebot_connect/api.py) 的固定路由、[config_flow.py](custom_components/ninebot_connect/config_flow.py) 的存储字段与 [models.py](custom_components/ninebot_connect/models.py) 的响应投影。

加密算法改编自 kxn/ninebot-recon，原代码 MIT 许可保留在组件的 [LICENSE.kxn](custom_components/ninebot_connect/LICENSE.kxn)，来源固定提交记录在 [PROVENANCE.md](custom_components/ninebot_connect/PROVENANCE.md)。项目不代表九号或 Home Assistant 官方。

项目图标为自制电动车图形，按本仓库 MIT 许可提供，不使用九号或 Home Assistant 官方标识。

## 本地开发

使用独立的Python3.14虚拟环境安装 `requirements-dev.txt` 后，运行 `python -m pytest`、`ruff check custom_components tests scripts` 和 `mypy custom_components/ninebot_connect`。HTTP测试只启动本机回环服务器。`python scripts/build_release.py` 生成允许列表内的安装包和完整源码包；不会打包工作目录中的抓包、APK或个人验证材料。
