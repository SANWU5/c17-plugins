# C17 自定义库

Status C17 的公开插件规范、SDK 开发模板与分发目录。当前协议为 **API 1**，用于 Status C17 2.0 起的自定义库功能；2.0.1 / code193 增加公开仓库目录接入。主应用源码和 APK 不在本仓库。

**当前公开目录为空，不提供可直接安装的示例插件。** [`index.json`](index.json) 的 `plugins` 为 `[]`。`templates/` 只供开发者阅读、复制和改写，不列入应用中的插件下载列表，也不代表任何 ROM 已通过适配。

## 当前可以做什么

插件由单个 `.js` 或带 `plugin.json` 的 ZIP 导入，声明自己的原生设置表单，并生成宿主已开放的有限规则：

- `settings`：临时覆盖 C17 已有、可见且经过类型与范围检查的设置，不改写用户保存的主配置。
- `systemui`：对核验过的明确 SystemUI 类/方法应用文字字面修正、View 属性或基本类型返回值规则。原方法先执行，规则随后应用。

完整 JavaScript 在无主应用权限的独立隔离进程中运行，SystemUI 只消费验证后的规则。API 1 只执行入口脚本，不支持 `require/import`、文件/网络/Android/Java 桥、任意原生代码或任意 Compose 界面。新权限、服务和未开放的底层行为需要升级宿主。

导入须先查看能力并确认安装，安装和升级都默认停用。启用后的设置或规则冲突会被拒绝；停用、移除及安全模式可撤销插件覆盖。实际效果依赖宿主版本、模块激活和目标 ROM；导入成功不等于适配成功。

## 规范与政策

| 文件 | 内容 |
|---|---|
| [SPEC.md](SPEC.md) | 格式、版本、命名空间、适配、能力与分发要求 |
| [SDK](docs/SDK.zh-CN.md) | 表单、状态、settings/hooks、运行限制 |
| [免责声明](DISCLAIMER.zh-CN.md) | 风险边界、第三方责任、恢复与法定责任保留 |
| [安全政策](SECURITY.md) | 安全漏洞的私密报告渠道与禁止行为 |
| [贡献要求](CONTRIBUTING.md) | 来源、许可、适配证据、代码审查和撤回流程 |
| [行为准则](CODE_OF_CONDUCT.md) | 协作、隐私和问题反馈规范 |
| [更新记录](CHANGELOG.md) | 协议、工具与目录变更 |

## 开发与本地打包

Python 3.10+，仅用标准库。先复制 `templates/<模板>/` 到自己的开发目录，修改 ID、名称、作者、许可和行为，核验目标 ROM，再构建并导入本地测试：

```powershell
python tools/pack.py lint templates/clock-seconds
python tools/pack.py build-all --out dist
python -m unittest discover -s tests -v
```

`build/build-all` 只生成本地开发包和校验和，**不会更新公开目录**。明确准备发布实际插件时，阅读 [发布说明](docs/PUBLISHING.zh-CN.md)，使用单独的 `publish` 命令生成本地 `packages/` 与 `index.json`，经过审查再提交。工具拒绝直接把本仓库教学模板发布到目录。

ZIP 文件按名称排序，使用固定时间与权限，便于重建。`pack.py` 检查标准源码头和包结构，不执行 JavaScript；应用仍会执行真实语义校验。SHA-256 只验证下载内容一致，**不是安全认证、作者签名或代码审查结论**。

## 反馈与许可

一般问题请通过 [Issues](https://github.com/SANWU5/c17-plugins/issues) 提交脱敏的宿主版本、插件 ID/版本、Android/ROM 版本、复现步骤和撤销结果。涉及漏洞、凭据或隐私内容时，按 [SECURITY.md](SECURITY.md) 私密报告，不在公开 Issue 上传。

本仓库原创工具、规范、文档和开发模板采用 [MIT](LICENSE)。第三方插件保留各自作者和许可证，必须单独声明来源与分发授权；本仓库的 MIT 不会替第三方作品重新授权。公开收录和哈希校验不表示开发者、维护者或设备厂商对每个插件提供安全或兼容担保。
