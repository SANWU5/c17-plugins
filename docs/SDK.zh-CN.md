# C17 插件 SDK · API 1/2

宿主起始版本：Status C17 2.0 / code192。插件自身的 `version` 和 `versionCode` 独立递增。API 1 是隔离的声明式规则；API 2 是完整运行扩展，需要支持 API 2 的宿主。

**本文的 `action/status` 表单及 `C17.onAction/publishStatus` 最低需要 2.1.0_beta.008 / code206。code205 虽支持 API 2，也不能导入这两类控件。** API 编号保持 2，不能用它代替宿主版本检查；当前 manifest/目录不支持最低宿主字段，请在发行说明与 README 写清所需宿主版本。

公开仓库目录接入用于 2.0.1 / code193。仓库 `templates/` 仅供开发参考，不列入公开可安装目录；当前目录为空。格式、命名空间、版权来源、适配和分发规则见根 [SPEC.md](../SPEC.md)，使用边界见 [免责声明](../DISCLAIMER.zh-CN.md)。

## 文件与入口

可导入单个 UTF-8 `.js`，或根目录含 `plugin.json` 与其 `entry` 指向脚本的 ZIP。ZIP 中不应再套一层目录。`plugin.json` 只有元数据与 `entry`，不能包含 `ui/settings/hooks`；这些由脚本提供。

API 1 只执行 `entry` 这一份脚本。包里可以附带其他 JS 源码供阅读，但不会自动执行它们；没有 `require`、`import`、模块加载器、文件读取或相对路径资源加载桥。需要共用代码时，请先在开发端合并到入口脚本，再打包。

API 2 的 `entry` 仍是导入时用于身份、表单和预览的 `main.js`。它必须提供 `runtime` 能力，并在 manifest 和元数据中声明相同的 `runtime.entry`（ZIP 内另一份 `.js`）或 `runtime.source`（非空运行脚本）。运行入口只会在用户主动启用后，由宿主装入 SystemUI。ZIP 可附带 DEX、图片、字体、数据文件和其他二进制资源；API 2 不使用 API 1 的 32 项文件、1MiB 总容量、256KiB 单项文件/脚本配额，`entry` 路径可至 4096 字符。运行入口不套用 API 1 执行预算；导入元数据仍在隔离进程中编译并有计算和时间预算，不能在此入口执行插件主体。仍需遵守有效 ZIP 路径和 ROM/Android 文件系统能力。

```json
{
  "id": "io.github.yourname.systemui-extension",
  "name": "我的 SystemUI 扩展",
  "version": "1.0.0",
  "versionCode": 1,
  "apiVersion": 2,
  "author": "yourname",
  "capabilities": ["runtime"],
  "entry": "main.js",
  "runtime": {"entry": "runtime.js"}
}
```

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

标准构建器采用开发模板的写法：`var plugin = {严格 JSON 元数据};`，之后以 `plugin.ui = [严格 JSON 控件声明];` 声明完整表单，再赋值 `plugin.settings` 与 `plugin.hooks`，最后 `C17.define(plugin)`。构建器读取元数据头与 manifest 比对，并静态检查唯一的表单声明、类型、默认值和至少一个可编辑项；它不执行脚本，因此不能证明后续脚本没有改写表单或每个参数都关联功能，宿主仍会对实际输出强制检查。应用也接受直接 `C17.define({...})` 的独立脚本；一般动态脚本可直接交宿主验证导入，标准构建器不负责解析所有 JavaScript 语法。

manifest 中声明的 `id/name/version/versionCode/apiVersion/description/author/capabilities` 必须与脚本一致，capabilities 的顺序也必须一致。宿主允许 manifest 省略 description、author、capabilities；标准构建器要求 manifest 与源码元数据头完全一致，包括可选字段是否出现。元数据不能随表单状态变化。

从在线仓库下载还有独立的目录一致性检查：目录与脚本的 `id/name/version/versionCode/apiVersion` 逐项相同，目录非空白作者与脚本作者相同，能力按集合完全相同；`description` 仅用于展示，不参与这一层的包一致性比较。**目录缺少 capabilities 按空数组处理**；若脚本声明 settings 或 systemui，就必须在目录如实列出，否则下载内容即使通过 size/SHA-256 也会取消导入。这与 ZIP manifest 的可选字段省略规则是不同层次的检查。

## 表单与状态

API 1 的 `ui` 包含 1–64 项，API 2 不设表单总项数配额。两个 API 都必须至少有一个真实关联功能的 `switch/slider/input/select`，完整呈现插件全部可调参数；只有说明文字或按钮会被拒绝导入。每项 `title` 必填，最多 120 字符，`description` 可选且最多 512 字符。可编辑控件需要唯一 `key`，格式 `[a-zA-Z][A-Za-z0-9_.-]{0,63}`，禁止保留对象键。旧版已安装无配置插件保留原记录，不自动删除或改启用状态，作者应发升级包补全。

| type | 数据与默认值 |
|---|---|
| `text` | 说明文字，无状态 key |
| `switch` | 布尔值；缺省 `default:false` |
| `slider` | 数字；必填 `min/max`，范围在 ±100000 内且 min < max；step > 0 且不大于范围，缺省 1；default 缺省 min；2.0.4 / code196 起可选 `unit` 显示单位（最多 16 字符） |
| `input` | 文字；缺省空串，最多 4096 字符 |
| `select` | `options:[{value,label}]`，1–64 个唯一字符串值；default 缺省第一项 value |
| `button` | 点击后把 `value` 写入该 key 并重新编译；value 缺省 true，可用字符串/数字/布尔值；不是任意回调 |
| `action` | API 2、code206 起提供的一次性运行操作；必填唯一 key，不接受 default/value，也不进入 C17.state |
| `status` | API 2、code206 起提供的只读运行文字；必填唯一 key，由 C17.publishStatus 提供，不进入 C17.state |

读取 `C17.state.<key>`。首次评估状态可能为空，脚本应给出回退值；宿主取得声明后补齐默认值和已保存的状态，再评估一次。每次更改表单重新编译规则，脚本修改临时 `C17.state` 对象不会写回保存值。不要让元数据或能力声明依赖状态。

完整配置应逐项声明在 `ui` 中；宿主不会把一个模式选择自动展开成多个未声明的设置。API 1 的当前控件键和类型必须保持稳定，不支持通过增删有状态控件保存隐藏配置。可根据已保存的状态调整说明文字与输出规则，但不能让现有状态因控件类型、选项或范围变化而失效。`unit` 只用于滑块显示，不参与数值换算；需要兼容 code192–195 时请省略该字段。

名称和说明宜简短，详细操作与诊断可链接到发行文档。整理文案时保留现有键、类型、选项值、默认值和有效范围，并用已有非默认值验证升级前后仍然一致；不能通过移除控件实现“精简”。完整参数要求与简洁界面应同时满足。

2.0.4 / code196 起，插件详情可将该插件的所有独立配置一次恢复为声明的默认值。宿主从空状态解析默认值，最多四轮稳定生成且重复结果一致后才提交；身份、权限或默认规则异常、与其他插件冲突时保留原配置及启用状态。恢复默认不写入用户的 C17 原设置，也不撤销其他插件的配置。

## settings 能力

声明 `capabilities:["settings"]` 后，通过旧声明式 `settings` 通道输出最多 64 项可见的 C17 设置覆盖。API 2 如使用此兼容通道也遵循相同约定；任意 Java/Android 扩展由 `runtime` 实现。键必须在当前宿主真实 `SettingsCatalog` 中，类型和范围与内置设置一致。数字超范围会拒绝，不自动截断。隐藏项、诊断/安全模式、资源导入和内部配置不能覆盖。

例如默认时钟需要 `clock_controls_enabled:true`、`clock_enabled:true` 与 `clock_pattern:"HH:mm:ss"`；字号还需要 `clock_size_enabled:true` 与 `clock_scale:100`。`clock_scale` 是 25–250 的百分比，不是 sp 字号。

code202 起，宿主移除控制中心自由编辑的页面和业务实现。已发布的 `qs_card_*` 声明式输出只保留旧库读取、配置维护和升级兼容，不再修改宿主运行布局；旧别名与行数键仍参与冲突校验。新实现应由 API 2 插件自带 DEX、独立状态与恢复逻辑。

### 控制中心自由编辑的旧输出

以下表格记录旧 API 1 输出的含义，供已有插件升级使用。code202 的控制中心布局、音乐 4×2 和更多磁贴完全由独立 API 2 插件实现；宿主只提供通用运行时和图片资源。表内同名键可继续作为插件独立 `state` 使用，但经 `settings` 输出已不再激活宿主功能。

code197 为试验宿主，实机编辑前的尺寸查询暴露了扩展索引进入原生网格的风险；code198 补齐前置尺寸查询的来源与范围保护，新插件不应面向 code197 启用。API 1 尚无独立的最低宿主版本字段，请在插件首行说明、README 和发布说明中明确所需版本；这些说明不代表设备效果已验收。

| 设置键 | 类型与范围 | 行为 |
|---|---|---|
| `qs_card_grid_rows` | 整数 4–7 | 顶部固定 4 列，可编辑行数；受屏幕可用空间和适配结果限制，不能承诺所有设备都能显示 7 行 |
| `qs_card_large_media_enabled` | bool | 解锁音乐卡片的手动尺寸调整；启用时不自动放大，用户在原生编辑界面拖拽为 4×2 |
| `qs_card_native_resize_enabled` | bool | 解锁已适配原生卡片的手动尺寸调整，包括音乐卡片；未知卡片保持原生 |
| `qs_card_small_tiles_2x1_enabled` | bool | 将原生小磁贴添加到顶部扩展区后显示为 2×1 |
| `qs_card_small_tiles_mode` | `always/hidden/more` | 原生底部始终显示、隐藏，或使用顶部「更多磁贴」入口进入独立页面 |
| `qs_card_hide_idle_controls_enabled` | bool | 没有媒体时隐藏音乐播放控件 |
| `qs_card_wallpaper_enabled` | bool | 使用宿主中已配置的音乐卡片壁纸；插件不能读取或导入文件 |
| `qs_card_wallpaper_opacity` | 数字 0–100 | 壁纸不透明度百分比 |

`more` 模式进入控制中心时显示顶部编辑区域，点击「更多磁贴」才打开原生小磁贴页面。更多页保留原生磁贴点击、长按和横向分页；页面返回入口与系统返回键回到顶部，原生弹窗和编辑返回优先。上划关闭控制中心后再次下拉从顶部页开始，不把普通滑动解释为打开更多页。code196 的旧值 `swipe` 在 code197 运行副本中兼容为 `more`，不重写保存值；新插件的选项应列 `more`，不能向 code196 承诺此新交互。

顶部顺序与扩展尺寸只保存到宿主独立配置；原生状态、缓存、Room、原生备份必须保留原几何。关闭、未生效、安全模式、横屏、适配失败或空间不足时，应撤回扩展并恢复原生可访问界面。更多入口只有在原生 UI 消费者实际提交成功后才能隐藏底部小磁贴；入口或页面失效时必须保留原生访问路径。插件 README 应分别记录这些回退、尺寸拖拽、返回与重新下拉的真实设备验证结果，不能以导入成功或桌面检查替代。

覆盖在运行时合并到配置副本，不写用户保存的偏好。多个已启用插件不能覆盖相同设置键；冲突会拒绝启用或更新，不会按加载顺序覆盖另一插件。升级必须用更大的 `versionCode`，保留仍符合新控件约束的表单状态，其余使用新默认值，并默认停用。关闭、删除和安全模式可撤销覆盖。

## systemui 能力

声明 `systemui` 后使用旧声明式 `hooks` 通道，每插件最多 32 条，全部启用插件合计最多 64 条。API 2 如使用此兼容通道也遵循相同约定；`runtime` 中的任意方法 Hook 不使用这里的数量、目标类或参数限制。每条共同字段如下：

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

API 1 的入口脚本在 `CustomPluginService` 隔离 UID 中运行。它不获授主应用权限或 Root 身份，也不能直接调用 Android/Java、文件、网络、计时器或第三方库。SystemUI 只接收宿主核验过的 JSON 设置和有限规则。

API 2 在 SystemUI 进程内执行完整 JavaScript，直接使用 Rhino LiveConnect、Java/Android 对象、反射、任意类和方法、构造器/方法 Hook、DEX 加载、接口代理、文件和线程等宿主进程可用能力。`C17.context`、`C17.pluginDir`、`C17.state`、`C17.findClass`、`C17.hook/hookAll/hookAllConstructors/hookNative`、`C17.deoptimize`、`C17.proxy`、`C17.loadDex`、`C17.require`、`C17.onClassLoader`、`C17.onCleanup`、`C17.runOnMain`、`C17.dataDir`、`C17.save/load` 和 `C17.log` 是便捷 API；API 2 不对脚本的 Java 类或系统功能做白名单限制。

运行入口可使用以下接口。`C17.state` 是本次启用的完整表单状态；只更新表单状态时保留运行实例、DEX 和 Hook，通过 `onStateChanged` 通知新旧状态。`C17.context` 是 SystemUI Context，`C17.moduleClassLoader` 是宿主模块 ClassLoader，`C17.pluginDir` 是本版本经过校验的只读资源目录（`java.io.File`）。

| 接口 | 参数与返回 |
|---|---|
| `findClass(name[, loader])` | 查找类，返回 `java.lang.Class`；省略 loader 时搜索宿主、系统和已加载 DEX |
| `hook(executable, callback)` | Hook 反射 `Method/Constructor`，返回取消函数 |
| `hook(className, method, parameterTypeNames, callback)` | 精确参数类型列表，例如 `["int", "java.lang.String"]`；构造器用 `"<init>"`；返回取消函数 |
| `hookAll(className, method, callback)` | Hook 目标类声明的同名重载；返回取消函数 |
| `hookAllConstructors(className, callback)` | Hook 目标类声明的构造器；返回取消函数 |
| `hookJava(executable, invocationHandler[, retainOnDisable])` | code205 起使用标准 JDK `InvocationHandler` 接收原生调用，返回 JDK `Runnable`；调用 `run()` 取消 Hook。不要求动态 DEX 引用框架 API |
| `hookNative(executable, javaHooker[, retainOnDisable])` | 接受 Java `XposedInterface.Hooker`，返回原生 `HookHandle`；默认为停用时 unhook |
| `deoptimize(executable)` | 请求框架反优化指定方法或构造器 |
| `proxy(interfaceClassOrName, callbacks[, propagateErrors])` | 创建 Java 接口代理；callbacks 可为单函数或按方法名映射的函数对象；默认捕获异常并停用实例。code201 起第三参数 `true` 将异常交回 Java 调用者，由其处理可选接口回退；未处理异常仍由外层运行入口隔离。类继承应使用 DEX |
| `loadDex(path)` | 相对资源目录或绝对路径，返回 ClassLoader，并供后续类查找和 Hook 使用 |
| `require(path)` | 执行并缓存 CommonJS 模块，支持 `exports/module.exports`、相对 require；省略 `.js` 可补全 |
| `onClassLoader(callback)` | 接收已有及后续发现的 ClassLoader，返回取消函数 |
| `onStateChanged(callback)` | 表单状态改变时在主线程接收 `(next, previous)`，保留当前实例；返回取消函数 |
| `onAction(key, callback)` | code206 起注册一个已声明 action 的主线程回调，接收 `{requestId, instanceId, action}`；返回取消函数 |
| `publishStatus(values)` | code206 起合并已声明 status 的只读文字，例如 `{saved_at:"2026-10-20 15:30"}`；每项最多4096字符，单次更新及合并后状态各最多64KiB UTF-8 |
| `runOnMain(callback)` | 排入 Android 主线程，返回取消函数；停用时取消未执行任务 |
| `onCleanup(callback)` | 注册按后进先出顺序调用的恢复函数；应使用事先捕获的 Java 对象完成恢复 |
| `dataDir()` | 返回本插件跨版本保留的可写数据目录（`java.io.File`） |
| `save(name, value)` / `load(name[, fallback])` | 保存 JSON 值，或读取已保存值；不存在时返回 fallback |
| `log(message)` | 写入带插件 ID 的模块诊断日志 |

### 一次性动作与只读状态

表单动作由用户每次点击生成新的随机 requestId，并绑定正在运行的实例 instanceId。结果报告重试只返回该次已记录的结果，不再次调用插件；插件替换、停用、安全模式或 SystemUI 重载后，旧实例的请求会被拒绝。请求和结果不写进插件配置或磁盘命令文件；宿主沿用现有主线程命令分发通道，不为动作创建服务或工作线程。安全模式仍暂停整个插件，动作不能绕过它。

回调可以返回字符串，或包含 `message` 的 JSON 对象作为完成提示，结果最多64KiB UTF-8；抛出的异常会显示本次操作失败，这次请求仍已消费。需要保存的数据由插件自行原子提交，保存成功后再发布实际保存时间。只读状态本身不持久化，插件应在运行入口读取自己的已保存数据并发布初始状态，再在动作完成后更新；不要用设置计数器模拟按钮或在 `onStateChanged` 中重放命令。例如，元数据入口除完整身份与 runtime 声明外提供：

```javascript
plugin.ui = [
  {"type":"switch","key":"enabled","title":"启用功能","default":false},
  {"type":"action","key":"capture","title":"保存数据"},
  {"type":"status","key":"saved_at","title":"保存时间","description":"尚未保存"}
];
```

运行入口注册回调，并从插件自己的已保存记录初始化只读文字：

```javascript
C17.publishStatus({saved_at: C17.load("saved-meta", {displayTime:"尚未保存"}).displayTime});
C17.onAction("capture", function (request) {
  var saved = captureAndCommit(); // 插件自身负责采集条件、原子覆盖与错误恢复
  C17.publishStatus({saved_at: saved.displayTime});
  return {message: "已保存"};
});
```

`action/status` 最低需要 code206，code205 不支持。状态或动作之间及与可编辑设置之间的 key 必须唯一；只允许 `type/key/title/description`，不接受持久值、数值范围或选项字段。它们不能替代至少一个真实功能设置。操作只在启用、已就绪且非安全模式的当前实例上执行；业务开关关闭是否允许某个操作，由插件校验自己的业务条件。旧 `button` 的持久赋值语义保持不变。

JS Hook 回调接收 Chain：`getExecutable()`、`getThisObject()`、`getArgs()`、`getArg(index)`、`proceed()`、`proceed(Object[])`、`proceedWith(receiver)`、`proceedWith(receiver,Object[])`。回调返回新结果；`proceed` 使用原方法结果并保留原异常，重复调用不会重复执行原方法。要传入 Java 数组，可通过 Java 反射创建匹配参数类型的数组。类暂未出现时，命名 Hook 会在后续 ClassLoader 到达后重试。

`hookJava` 直接调用 Java `InvocationHandler.invoke(receiver, method, frame)`，不经 Rhino 解释器。`method` 是目标 `Method`，构造器时为 null；`frame` 为四项 `Object[]`：原 receiver、参数快照 `Object[]`、continuation `InvocationHandler`、目标 `Executable`。调用 `continuation.invoke(selectedReceiver, null, replacements)` 继续原生链；replacements 为 null 时沿用原参数，传入新数组可替换参数，selectedReceiver 可替换 receiver。只允许在当前同步回调线程、回调返回前使用；重复继续读取同一次原生执行的缓存结果，原异常身份保持。回调结束会撤销并释放宿主 continuation 对原生链的引用。返回值和异常直接交给原生调用链；插件须自行正确处理 Java 返回类型。普通 handle 同时由宿主管理，在停用时取消；保留选项与下段的旧对象保护语义相同。

部分框架禁止反射或动态代码直接解析其 API 类，此时 `hookNative` 及带框架 API 类型的自定义代理接口不可用，应使用 `hookJava` 的 JDK 边界。宿主不改变框架的保护策略。该运行属性由 [libxposed API](https://github.com/libxposed/api/blob/master/api/src/main/java/io/github/libxposed/api/XposedInterface.java) 的 `PROP_RT_API_PROTECTION` 描述。

`hookNative(..., true)` 专用于停用后仍须保护已交给系统的旧视图或扩展索引。此模式的 Hook 保留到 SystemUI 重启；Java Hooker 必须自行判断启用状态、恢复扩展布局，并在停用后只保留必要的兼容保护。宿主不会替任意原生 Hooker 自动实现这些语义。插件普通 Hook 和任务应使用默认生命周期；发行 README 必须说明是否使用保留保护及其退出条件。

API 2 与 API 1 有意采用不同的信任模型。启用 API 2 等同于允许该作者在 SystemUI 权限下执行代码。安全模式、停用和卸载会撤销普通受管 Hook，并让普通代理回调失效；显式保留的原生兼容保护遵循上一段约定。宿主无法撤销插件直接写入的系统数据、终止插件自行创建的线程或恢复它自行修改的进程状态。任何 JS 在主线程无限循环、内存耗尽或破坏系统界面都可能让 SystemUI 重启。代码只获得 SystemUI 本身拥有的权限，不会自动变成 Root。

插件的异步布局与恢复逻辑须独立遵守对象归属和实例生命周期。测量尚未就绪时保留原生界面，后续按相关几何变化重试；几何不变的连续帧不得反复提交布局。已停用、解绑或属于旧实例的回调不得恢复扩展，成功应用后应结束无用等待。视图被复用时同时核验外层布局和内部子视图是否回到当前原生状态，恢复只作用于插件拥有的对象。宿主清理 Hook 不会替插件完成任意 View 属性与监听器恢复。

API 1 继续使用单脚本 256KiB、输出 JSON 128KiB/4096 节点/12 层/256 数组项。导入元数据求值对两个 API 都采用隔离 UID、200000 条指令、约 600ms 解释器检查点、64 层解释栈和 1.5 秒独立看门狗；API 2 的独立运行入口不受这些预算约束。API 2 元数据 JSON 不使用 API 1 的字节、节点、数组项数配额，但仍限制 64 层数据嵌套。

API 1 ZIP 最多 32 项、总解压 1MiB、单项 256KiB；大于 64KiB 的条目压缩比不得超过 200。API 1 只接受 `.js/.md/.txt`、根 `plugin.json` 与 `LICENSE` 文本。两个 API 都拒绝 ZIP 路径穿越、重复规范路径、链接、加密或分卷；API 2 资源可为二进制。当前导入器使用经典 ZIP 的 16/32 位字段，不支持 ZIP64；这是档案格式边界。在线下载还受 Java 字节数组可表示的包长度和实际可用内存约束。路径、磁盘和 Android 运行机制同样不能由插件协议解除。

## 验收

先导入并审查能力，确认安装后再手动启用。检查表单默认值、修改状态、与已有设置冲突、停用/移除/安全模式的恢复行为，再在目标 ROM 测试。导入成功、schema 通过或文件哈希一致均不能代替系统界面的实际效果验收。

[运行与交互验收指南](VALIDATION.zh-CN.md) 给出配置兼容、异步测量、视图复用、媒体原生拖动、背景复用和文字显示的黑盒步骤。指南不提供业务实现，也不表示新增 API 或任何设备已经通过验收。
