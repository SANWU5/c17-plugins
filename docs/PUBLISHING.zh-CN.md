# 本地构建与正式分发

## 开发模板

`templates/` 是教学源码，不是公开插件列表。当前 root `index.json` 的 `plugins` 必须保持为空，`packages/` 没有发行包。不要把模板的 ID、作者或 ROM 适配说明直接当成自己的正式插件。

复制某个模板到仓库外的开发目录，使用属于自己的命名空间并修改 metadata；本地导入调试仍要经过宿主完整校验。`build/build-all` 只输出开发包和逐包 SHA-256，不写公开目录：

```powershell
python -m unittest discover -s tests -v
python tools/pack.py build-all --out dist
python tools/pack.py inspect dist/dev.c17.clock-seconds-1.zip
python tools/pack.py catalog index.json
```

同一源码的 ZIP 按名称排序，固定时间与权限；相同 Python/zlib 工具链可以逐字节重建。不同压缩库版本的压缩字节可能不同，发布者应固定构建环境；相同 ZIP 的 size/SHA-256 必须一致。

## 显式准备正式包

完成源码、版权和目标 ROM 审查后，开发目录必须含 LICENSE、README.md、plugin.json、main.js 与真实作者。README 应列出来源、许可、最低宿主/API、适配版本、限制、撤销方法和变更记录。

```powershell
python tools/pack.py lint D:/my-plugin
python tools/pack.py publish D:/my-plugin --repository .
```

`publish` 拒绝直接发布本仓库 templates，要求正式包 LICENSE/README/作者，生成 `packages/<id>-<versionCode>.zip` 与校验和，更新本地根 `index.json`、`SHA256SUMS`。已有相同 ID 的升级需要更大的 versionCode；同版本只允许逐字节相同的内容，不能偷偷替换。该命令不会创建远端、提交、推送或建立 Release。

索引 `file` 使用相对于索引的 `packages/...zip`，拒绝绝对地址、路径穿越、反斜杠、查询和片段；最多 128 项。每项记录真实字节数和小写 SHA-256，索引保留 README/CHANGELOG 链接。发布前请再核对目录和包内容，由维护者通过审查后提交。

## 仓库与撤回

公开仓库是 [SANWU5/c17-plugins](https://github.com/SANWU5/c17-plugins)，默认索引 `index.json`，README 和 CHANGELOG 可供宿主浏览。宿主下载后仍需 preview、确认安装和主动启用，不会因目录收录而自动运行。

发现严重问题时先撤回相应目录条目，并在允许披露的范围内记录原因；撤回不会远程移除已安装副本。修复版本增加 versionCode，更新安装默认停用。不要提交 APK、主程序私有源码、签名、账号凭据、OEM 资源或设备资料。完整规范、贡献和安全流程见仓库根文档。
