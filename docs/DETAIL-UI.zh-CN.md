# 插件详情三段布局与开发映射

本文把已有 code210 契约映射到插件详情界面，适用于第三方插件。它不增加协议字段、专用业务入口或新的最低宿主版本；类型、长度与 ABI 以 [SDK](SDK.zh-CN.md) 和 [Schema](../schema/descriptor.schema.json) 为准。

## 一、前置条件

先展示使用说明和功能概况，再展示声明的应用作用域及各作用域是否已在框架勾选。

| 内容 | 作者声明 | 宿主负责 |
|---|---|---|
| 使用说明与概况 | `usage` 写使用顺序、影响区域、生效条件和恢复方法；`description` 保持简短 | 优先展示 `usage`；旧包没有时使用 `description`，均缺失时明确作者未提供说明 |
| 最低宿主与能力 | `minimumHost` 与实际依赖的 `features` | 校验真实版本和能力，不能把 API 2 当作所有接口已存在 |
| 应用作用域 | `scopes` 使用真实包名；组件区域写在 `usage` | 分别展示声明与框架实际选择；旧运行包继续沿用原有 SystemUI 环境 |
| 是否已勾选 | 插件不得填写、持久化或伪造勾选结果 | 框架成功返回且包含包名为“已勾选”，成功返回但不包含为“未勾选”；不可读取为“未知” |

框架断开、查询失败或从框架管理器返回后须重新核验；过去成功的结果不能充当新的实时证据。插件启用、框架勾选、当前引擎支持和运行就绪是不同状态。当前运行引擎只支持 SystemUI；声明其他应用作用域仍须显示不支持并阻止启用。

## 二、功能与设置

启用入口、全部可调功能和复杂设置入口放在此段。普通控件使用 `ui`；缺少 `section` 时默认属于 `features`。按数组顺序排列同段控件，`group` 标识连续的一组，重复出现在不连续位置的组名不会自动合并或重新排序。

| 需要呈现的内容 | 已有通用入口 |
|---|---|
| 开关、范围、文字、模式 | `switch/slider/input/select`，声明真实默认值与边界 |
| 补充说明 | `text` 与控件 `description` |
| 用户点击后执行一次的功能 | API 2 `action` 与 `C17.onAction` |
| 实际运行结果 | API 2 `status` 与 `C17.publishStatus`；不写进持久配置 |
| 复杂、多页或自定义交互 | API 2 包内 `nativeSettings`，复用固定 View/异步状态桥接 ABI |

例如只调整展示位置，可保留原 key 与数据约束：

```javascript
plugin.ui = [
  {"type":"switch","key":"enabled","title":"启用功能","default":false,"section":"features","group":"基本设置"},
  {"type":"slider","key":"intensity","title":"强度","min":0,"max":100,"default":50,"unit":"%","group":"基本设置"},
  {"type":"select","key":"mode","title":"模式","options":[{"value":"system","label":"跟随系统"},{"value":"custom","label":"自定义"}],"default":"system","group":"显示"},
  {"type":"action","key":"capture","title":"保存数据","section":"management","group":"数据管理"},
  {"type":"status","key":"saved_at","title":"保存时间","section":"management","group":"数据管理"}
];
```

这是表单片段，不是可直接安装或已适配的业务插件。将实际适配逻辑与原生设置界面放在插件自己的运行入口和 DEX 中，不要求宿主识别插件 ID、业务 key、类名或特定板块。使用现有能力新增功能、改布局或重新分组，只递增插件 `versionCode`；只有确实依赖新增宿主能力才提高 `minimumHost`。复杂界面仍应完整呈现既有参数，不能以迁移为由丢失有效用户配置。

## 三、插件管理

插件自己的维护操作、维护状态与其他管理设置使用 `section:"management"`，可继续用 `group` 分组。它不改变控件类型或保存语义：管理段的 `input/select/switch/slider` 仍为持久参数，管理段的 `action/status` 仍不进入 `C17.state`。

删除、从文件更新、恢复默认、插件资料和相关宿主设置入口由宿主统一提供。不要用同名插件动作伪装成宿主删除或更新，也不要为了移动宿主管理入口新增不受支持的 section。第一段由宿主根据元数据组织，不是 `section:"prerequisites"`。

## 升级与验收

1. 保存各类控件的非默认值；递增插件版本，调整标题、`group`、`section` 和顺序，再导入升级。有效值必须按 key 保留，升级默认停用，其他插件配置不变。
2. 核对 manifest 与真实脚本的 `usage/scopes/minimumHost/features/nativeSettings` 一致；在线目录仍只有分发元数据，不能加入勾选结果或原生页面代码。
3. 核对三段顺序、所有功能与管理入口可达；覆盖旧包缺少新字段、无原生入口和提供原生入口的包。
4. 核对勾选、未勾选、查询不可用及返回后变化，不以插件已启用或历史缓存判断。查询成功的空列表表示未勾选，不能误写未知。
5. 原生设置页分别验证停用时配置、异步保存、退出、更新、删除、重新导入同 ID/版本和安全模式；旧页面回调不得写回已替换的安装。

结构与桌面契约检查不能代替真实页面的视觉、触摸和生命周期验收；报告应分别记录已测与未测。完整流程见[运行与交互验收](VALIDATION.zh-CN.md)。
