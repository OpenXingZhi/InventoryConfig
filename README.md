# InventoryConfig

Inventory 的设备级签名配置。GitHub 是上游，Gitee 是应用运行时源：

- GitHub: <https://github.com/OpenXingZhi/InventoryConfig>
- Gitee: <https://gitee.com/star-spider-intelligence/inventory-config>
- Runtime: `https://gitee.com/star-spider-intelligence/inventory-config/raw/main/<ANDROID_ID>.yml`

每台设备在仓库根目录对应两个文件：

```text
<ANDROID_ID>.yml
<ANDROID_ID>.yml.asc
```

`ANDROID_ID` 必须是 16 位大写十六进制，并与 `license.sn` 相同。没有默认
配置；未登记设备会失败关闭。

## 新建设备配置

```bash
python3 -m pip install -r requirements.txt
cp examples/0123456789ABCDEF.yml <ANDROID_ID>.yml
```

编辑配置：

- 首次发布使用 `revision: 1`，以后每次修改递增。
- `license.expire` 可省略，省略表示永久许可。
- 临时许可使用带引号的 `YYYY-MM-DD`。
- `server`、`reader`、`display` 是签名后的部署配置。
- 登录令牌、用户、当前盘点任务和蓝牙配对信息不放入此仓库。

验证并签名：

```bash
python3 scripts/validate-config.py <ANDROID_ID>.yml --bind-filename
./scripts/sign-config.sh <ANDROID_ID>.yml <GPG_KEY_ID>
```

也可通过 `INVENTORY_CONFIG_SIGNING_KEY` 提供密钥 ID。私钥只保存在签名
机器上，不提交到仓库。

提交 `.yml` 和 `.yml.asc`，先推送 GitHub，再同步到 Gitee：

```bash
git push origin main
git push gitee main
```

字段定义见 [`schema/inventory-config.schema.json`](schema/inventory-config.schema.json)。
