# Inventory signed configuration

Per-device Inventory settings. Each provisioned handheld has exactly one
runtime pair at the repository root:

- `<ANDROID_ID>.yml`
- `<ANDROID_ID>.yml.asc` (detached, armored OpenPGP signature)

`ANDROID_ID` is `Settings.Secure.ANDROID_ID` in uppercase. Inventory already
exposes that value as `DeviceInfoUtil.getSN()`. The same string is the
remote-config refresh key and `license.sn`.

There is no `default.yml`, wildcard license, or fallback runtime document.
A device without its own signed file fails closed.

## Hosts and runtime URLs

| Role | Repository |
| --- | --- |
| Canonical upstream | [github.com/OpenXingZhi/InventoryConfig](https://github.com/OpenXingZhi/InventoryConfig) |
| Runtime mirror | [gitee.com/star-spider-intelligence/inventory-config](https://gitee.com/star-spider-intelligence/inventory-config) |

Inventory fetches the Gitee raw URLs:

```text
https://gitee.com/star-spider-intelligence/inventory-config/raw/main/<ANDROID_ID>.yml
https://gitee.com/star-spider-intelligence/inventory-config/raw/main/<ANDROID_ID>.yml.asc
```

Example for placeholder `0123456789ABCDEF` (not a real device):

```text
https://gitee.com/star-spider-intelligence/inventory-config/raw/main/0123456789ABCDEF.yml
https://gitee.com/star-spider-intelligence/inventory-config/raw/main/0123456789ABCDEF.yml.asc
```

## Authoritative vs session state

Signed YAML is deployment policy. It is not a dump of `share_data`
SharedPreferences.

**In the signed file**

Signed `server`, `reader`, and `display` settings are authoritative
deployment policy. The `reader` and `display` objects, and every modeled
field inside them, are mandatory. A valid signed configuration must never
silently inherit mutable SharedPreferences or Inventory local defaults.

| YAML | Inventory source | Notes |
| --- | --- | --- |
| `revision` | new, required | Positive integer. `remote-config` 1.2.0 `MonotonicLongRevisionPolicy` rejects a lower revision and same-revision content changes. |
| `license.sn` | `DeviceInfoUtil.getSN()` | Uppercase 16-digit hex Android ID. |
| `license.expire` | `license-library` 1.0.2 `License.Temporary` | Optional. Omit for `License.Permanent`. |
| `server.url` | `AppConst.ServerAddr` | Required. HTTP(S) Retrofit base URL. Prefer a trailing slash. Inventory’s UI sample is `R.string.server_addr_Sample` (`http://192.168.2.12:5000/`). `AppConst.DefaultServerAddr` exists but is unused. Neither is a repository fallback. |
| `reader.deviceType` | `AppConst.DevType` / `DefaultDevType` | Required. Inventory source currently uses `RPAN`; that local default is not a signed-config fallback. |
| `reader.commType` | `AppConst.CommType` / `DefaultCommType` | Required. Inventory source currently uses `Bluetooth`; that local default is not a signed-config fallback. |
| `reader.rfidType` | `AppConst.CurrentRfidType` | Required. `HF`=0, `UHF`=1. Inventory’s scan path currently uses HF; that local default is not a signed-config fallback. |
| `reader.dataFormat` | `AppConst.CurrentDataFormat` | Required. `ISO`=0, `CUSTOM`=1. Inventory’s current selection is ISO; that local default is not a signed-config fallback. |
| `reader.checkSecurity` | `AppConst.CurrentCheckSecurity` | Required boolean. Inventory’s settings checkbox currently starts unchecked; that local default is not a signed-config fallback. |
| `reader.securityType` | `AppConst.CurrentSecurityType` | Required. `AFI_EAS`=0, `EAS`=1, `AFI`=2. |
| `reader.afiInLib` | `AppConst.CurrentAfiInLib` | Required. Two hex digits. Settings hint `07`. |
| `reader.afiOutLib` | `AppConst.CurrentAfiOutLib` | Required. Two hex digits. Settings hint `C2`. |
| `reader.onlyReadBookUid` | `AppConst.OnlyReadBookUID` | Required boolean. Inventory’s scan path currently uses false; that local default is not a signed-config fallback. |
| `display.showShelfDescription` | `AppConst.ShowShelfDescription` | Required boolean. `InventoryAdapter` currently uses false; that local default is not a signed-config fallback. |
| `display.sort` | `AppConst.CurrentSort` | Required. `SHELF_AND_CLC`=0, `SHELF`=1, `CLC`=2. |

**Must not appear in remote config**

These keys are local session, pairing, or current-task state:

- `CurrentInvId`, `CurrentInvName`
- `CurrentUserID`, `CurrentUserName`, `RememberMe`
- `accessToken`, `encryptedAccessToken`, `refreshToken`, `token`
- `Configured`, `UpdateFile`, `MaxSupportedVersion`
- `AdminUser`, `AdminPwd`, `AdminUserId`, hardcoded `Admin` / `Pwd`
- `DevPath`, `ConnectionString` (Bluetooth pairing; `Name=` is device-local)
- `AuthorizationCode`, `LicFileName`, or any `VALID_HASH` activation material
- per-UID shelf-id cache entries

`additionalProperties` is false. Extra keys fail validation.

## License expiry format

`license-library` 1.0.2 models expiry as `kotlinx.datetime.LocalDate`
(`kotlinx-datetime` 0.6.1). This repository’s config decoder accepts only a
quoted four-digit `YYYY-MM-DD` calendar date and passes that string to
`LocalDate.parse`:

```yaml
expire: "2027-12-31"
```

Default `LocalDate.parse` uses extended ISO-8601 and may accept other
lexical forms; those are outside this repository’s contract. Quote the
value so YAML 1.1 loaders do not coerce it to a timestamp. Do not write a
time, offset, slash date, or locale date. Policy is inclusive:
`expire < trustedDate` is expired, so the expire date itself remains valid.
Temporary licenses also require trusted time. Permanent licenses omit
`expire`.

## Provision a device

1. Read the uppercase Android ID from the handheld (`DeviceInfoUtil.getSN()`).
2. Copy [`examples/0123456789ABCDEF.yml`](examples/0123456789ABCDEF.yml) to
   `/<ANDROID_ID>.yml` at this repository root. Do not leave the example
   filename at the root.
3. Set `license.sn` to that Android ID. Set or omit `expire`.
4. Set `server.url` and every required `reader` and `display` field for
   that library. Do not omit a modeled deployment field.
5. Set `revision` to `1` for the first publish. Increment it on every later
   content change.
6. Sign (see below) and commit both `.yml` and `.yml.asc`.
7. Push to GitHub, then update the Gitee mirror’s `main` to the same commit.

## Sign a configuration

Requires `bash`, `python3`, and `gpg`. The script contains no key material.
Pass the signing key as the second argument or `INVENTORY_CONFIG_SIGNING_KEY`.

```bash
./scripts/sign-config.sh <ANDROID_ID>.yml
# or
./scripts/sign-config.sh <ANDROID_ID>.yml 0123456789ABCDEF0123456789ABCDEF01234567
```

The signer:

- accepts only a 16-digit uppercase hex `<ANDROID_ID>.yml`
- rejects `default.yml` and other wildcard names
- requires `license.sn` to equal the filename stem
- requires a positive integer `revision`
- refuses secret-like keys (`token`, `password`, `authorizationCode`, …)
- optionally increments `revision` with `--bump-revision`
- writes a detached armored `$file.asc` and verifies it

It does not mutate the YAML unless `--bump-revision` is passed. Increment
`revision` yourself before signing a content change, or use that flag.

Keep the private key outside this repository. Bundle the matching public key
with Inventory; do not download a trust root from the same mutable origin as
the YAML.

## Mirror GitHub to Gitee

GitHub is canonical. After a reviewed GitHub `main` update, fast-forward the
Gitee `main` branch to the same commit so the raw URLs above serve the signed
bytes Inventory will verify. Do not edit runtime files only on Gitee: a
mirror-only change has no signed GitHub history and will drift.

## Consume from Inventory

Do not change Inventory in this repository. When Inventory adopts
`com.xingzhi:remote-config:1.2.0` and `com.xingzhi:license:1.0.2`:

```kotlin
val key = DeviceInfoUtil.getSN(context) // uppercase ANDROID_ID
val client = RemoteConfigClient(
    source = HttpConfigSource(
        contentUri = { id ->
            URI("https://gitee.com/star-spider-intelligence/inventory-config/raw/main/$id.yml")
        },
        signatureUri = { id ->
            URI("https://gitee.com/star-spider-intelligence/inventory-config/raw/main/$id.yml.asc")
        },
    ),
    store = FileConfigStore(context.filesDir.toPath()),
    decoder = ConfigDecoder(::decodeYaml),
    validator = ConfigValidator { snapshot, config ->
        signatureVerifier.verify(
            content = snapshot.content,
            signature = requireNotNull(snapshot.signature),
            publicKey = trustedPublicKey,
        ).getOrThrow()
        require(config.license.sn == key)
        require(config.revision > 0)
    },
    revisionPolicy = MonotonicLongRevisionPolicy { config -> config.revision },
)
client.refresh(key).getOrThrow()
```

Decode `license` into `License.Permanent(sn)` or
`License.Temporary(sn, LocalDate.parse(expire))`, then run `LicenseVerifier`.
A 404, bad signature, serial mismatch, or non-monotonic revision must not
invent a default configuration.

Machine-readable schema: [`schema/inventory-config.schema.json`](schema/inventory-config.schema.json).

```bash
./scripts/validate-config.py --check-repo
./scripts/test.sh
```
