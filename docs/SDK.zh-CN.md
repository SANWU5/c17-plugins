# C17 插件 SDK · API 1

宿主起始版本：Status C17 2.0 / code192。插件自身的 `version` 和 `versionCode` 独立递增，`apiVersion` 当前只能为 1。

公开仓库目录接入用于 2.0.1 / code193。仓库 `templates/` 仅供开发参考，不列入公开可安装目录；当前目录为空。格式、命名空间、版权来源、适配和分发规则见根 [SPEC.md](../SPEC.md)，使用边界见 [免责声明](../DISCLAIMER.zh-CN.md)。

## 文件与入口

可导入单个 UTF-8 `.js`，或根目录含 `plugin.json` 与其 `entry` 指向脚本的 ZIP。ZIP 中不应再套一层目录。`plugin.json` 只有元数据与 `entry`，不能包含 `ui/settings/hooks`；这些由脚本提供。

API 1 只执行 `entry` 这一份脚本。包里可以附带其他 JS 源码供阅读，但不会自动执行它们；没有 `require`、`import`、模块加载器、文件读取或相对路径资源加载桥。需要共用代码时，请先在开发端合并到入口脚本，再打包。

```json
{
  "id": "io.github.yourname.clock-seconds",
  "name": "我的时钟插件",
  "version": "1.0.0",
  "versionCode": 1,
  "apiVersion": 1,
  "description": "独立控制秒数和字号比例，不改写原设置。",
  "author": "yourname",
  "capabilities": ["settings"],
  "entry": "main.js"
}
```

脚本必须且只能调用一次 `C17.define(普通对象)`。其结果只允许 JSON 数据，不接受函数、`undefined`、循环引用或 Java 对象。未知字段会被拒绝。

标准构建器采用开发模板的写法：`var plugin = {严格 JSON 元数据};`，之后赋值 `plugin.ui`、`plugin.settings` 与 `plugin.hooks`，最后 `C17.define(plugin)`。构建器读取这个 JSON 元数据头并与 manifest 比对。应用也接受直接 `C17.define({...})` 的独立脚本；标准构建器不负责解析所有 JavaScript 语法。

manifest 中声明的 `id/name/version/versionCode/apiVersion/description/author/capabilities` 必须与脚本一致，capabilities 的顺序也必须一致。宿主允许 manifest 省略 description、author、capabilities；标准构建器要求 manifest 与源码元数据头完全一致，包括可选字段是否出现。元数据不能随表单状态变化。

从在线仓库下载还有独立的目录一致性检查：目录与脚本的 `id/name/version/versionCode/apiVersion` 逐项相同，目录非空白作者与脚本作者相同，能力按集合完全相同；`description` 仅用于展示，不参与这一层的包一致性比较。**目录缺少 capabilities 按空数组处理**；若脚本声明 settings 或 systemui，就必须在目录如实列出，否则下载内容即使通过 size/SHA-256 也会取消导入。这与 ZIP manifest 的可选字段省略规则是不同层次的检查。

## 表单与状态

`ui` 最多 64 项；每项 `title` 必填，最多 120 字符，`description` 可选且最多 512 字符。可编辑控件需要唯一 `key`，格式 `[a-zA-Z][A-Za-z0-9_.-]{0,63}`，禁止保留对象键。

| type | 数据与默认值 |
|---|---|
| `text` | 说明文字，无状态 key |
| `switch` | 布尔值；缺省 `default:false` |
| `slider` | 数字；必填 `min/max`，范围在 ±100000 内且 min < max；step > 0 且不大于范围，缺省 1；default 缺省 min |
| `input` | 文字；缺省空串，最多 4096 字符 |
| `select` | `options:[{value,label}]`，1–64 个唯一字符串值；default 缺省第一项 value |
| `button` | 点击后把 `value` 写入该 key 并重新编译；value 缺省 true，可用字符串/数字/布尔值；不是任意回调 |

读取 `C17.state.<key>`。首次评估状态可能为空，脚本应给出回退值；宿主取得声明后补齐默认值和已保存的状态，再评估一次。每次更改表单重新编译规则，脚本修改临时 `C17.state` 对象不会写回保存值。不要让元数据或能力声明依赖状态。

## settings 能力

声明 `capabilities:["settings"]` 后，通过 `settings` 输出最多 64 项可见的 C17 设置覆盖。键必须在当前宿主真实 `SettingsCatalog` 中，类型和范围与内置设置一致。数字超范围会拒绝，不自动截断。隐藏项、诊断/安全模式、资源导入和内部配置不能覆盖。

例如默认时钟需要 `clock_controls_enabled:true`、`clock_enabled:true` 与 `clock_pattern:"HH:mm:ss"`；字号还需要 `clock_size_enabled:true` 与 `clock_scale:100`。`clock_scale` 是 25–250 的百分比，不是 sp 字号。

覆盖在运行时合并到配置副本，不写用户保存的偏好。多个已启用插件不能覆盖相同设置键；冲突会拒绝启用或更新，不会按加载顺序覆盖另一插件。升级必须用更大的 `versionCode`，保留仍符合新控件约束的表单状态，其余使用新默认值，并默认停用。关闭、删除和安全模式可撤销覆盖。

## systemui 能力

声明 `systemui` 后使用 `hooks`，每插件最多 32 条，全部启用插件合计最多 64 条。每条共同字段如下：

```json
{"id":"am-label","className":"com.android.systemui.statusbar.policy.Clock","method":"updateClock","argCount":0,"kind":"text","find":"AM","replace":"上午"}
```

`className` 必须为精确类名，限 `com.android.systemui.`、`com.oplus.systemui.`、`com.oplusos.systemui.`、`com.oplus.keyguard.` 前缀。`method` 是该类实际声明的 Java 方法，`argCount` 为 0–8；同名同参数数量的重载有歧义时拒绝，也不支持 native/abstract/bridge/synthetic 或 Object 生命周期方法。没有 `process`、通配符、任意 Java 代码或 dex 加载字段。

| kind | 专属字段 | 边界 |
|---|---|---|
| `text` | `find/replace` 成对，另可有 `prefix/suffix` | 操作当前 TextView 文字；纯字面替换，非正则。find 非空，每字段 ≤256 字符；至少一项动作 |
| `property` | `property`、数字 `value` | View 的 alpha 0–1、scaleX/scaleY 0.1–4、translationX/translationY ±200dp |
| `result` | `value` | 先执行原方法，再把返回结果替换为 bool/有限数字/单字符字符串；必须匹配真实非 void 基本返回类型与数值边界 |

`text/property` 仅适用于目标类自己的非 static View 实例，text 还必须为 TextView。规则不保证任何 ROM 都有同一方法；无法核验的目标保持原生，不表示修复成功。

所有规则在原方法正常返回后应用，不跳过原方法及其副作用。规则作用位置由 `className + method + argCount + kind` 决定；property 还包含属性名。同一作用位置不能同时启用多条规则，启用或更新时明确拒绝冲突。不同 kind 或不同属性不视作同一位置，但仍需开发者核验组合效果。

示例 Clock/updateClock 取自 [AOSP Clock.java](https://android.googlesource.com/platform/frameworks/base/+/ac387ca9f3c2a304ff0b19c143c60517c916b1b8/packages/SystemUI/src/com/android/systemui/statusbar/policy/Clock.java)。AOSP 的实现不是对 Oplus/ColorOS 或后续系统版本的兼容承诺。平移规则由宿主把 dp 换算为 Android [View 平移属性](https://developer.android.com/reference/android/view/View#setTranslationY(float))需要的像素。

## 运行与容量

完整 JavaScript 在 `CustomPluginService` 中由 Rhino 解释执行，服务声明 `isolatedProcess=true`，使用独立隔离 UID，不获授主应用权限或 Root 身份；脚本没有 Android/Java 对象桥、文件、网络、定时器或第三方库加载能力。主设置应用在后台经 Binder 传入脚本与纯数据状态，接收并再次校验 JSON；SystemUI 不执行导入脚本。它适合调用宿主已开放的设置和有限 SystemUI 规则；新权限、新 Android 服务、任意 Compose UI、原生算法或底层缺陷修复需要升级宿主。

单脚本最多 256KiB，传入状态最多 48KiB，输出 JSON 最多 128KiB、4096 节点、12 层，数组最多 256 项。Rhino 使用 200000 指令、约 600ms 检查点与 64 层解释栈预算；独立看门狗在单次执行超过 1.5 秒时终止隔离进程，覆盖无法被解释器计数中断的正则/分配；调用方最多等待 5 秒，随后解除绑定并报错，不阻塞主界面。

ZIP 最多 32 个条目、总解压数据 1MiB、单项 256KiB；大于 64KiB 的条目压缩比不得超过 200。仅允许小写扩展的 `.js/.md/.txt`、根 `plugin.json` 与 `LICENSE` 文件，所有文件必须为无 NUL 的 UTF-8 文本；其他 JSON 不受支持。拒绝加密、ZIP64、分卷、目录穿越、大小写规范化后重复条目、链接及不支持的压缩格式。标准构建器只生成无目录条目的 stored/deflate 兼容 ZIP，不需要解压到手机文件系统。

## 验收

先导入并审查能力，确认安装后再手动启用。检查表单默认值、修改状态、与已有设置冲突、停用/移除/安全模式的恢复行为，再在目标 ROM 测试。导入成功、schema 通过或文件哈希一致均不能代替系统界面的实际效果验收。
