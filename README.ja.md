<!--
Copyright 2025 nw-check contributors
SPDX-License-Identifier: Apache-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
-->

# nw-check

[English](README.md) | 日本語

**nw-check**は、LLDP（Link Layer Discovery Protocol）を使用してネットワーク配線が意図した設計と一致しているかを検証するツールです。実際の物理接続（SNMPを介して検出）と期待される配線計画（CSVファイルで定義）を比較し、不一致を強調表示します。

## 目次

- [クイックスタート](#クイックスタート)
- [インストールと前提条件](#インストールと前提条件)
  - [システム要件](#システム要件)
  - [Python依存関係のインストール](#python依存関係のインストール)
  - [SNMPツールのインストール](#snmpツールのインストール)
- [基本的な使い方](#基本的な使い方)
  - [入力ファイルの準備](#入力ファイルの準備)
  - [最初のチェックの実行](#最初のチェックの実行)
  - [出力の理解](#出力の理解)
- [高度な機能](#高度な機能)
  - [ドライランモード](#ドライランモード)
  - [出力のフィルタリング](#出力のフィルタリング)
  - [出力形式](#出力形式)
  - [ネットワーク図の生成](#ネットワーク図の生成)
  - [Webコントロール付きスーパーバイザーモード](#webコントロール付きスーパーバイザーモード)
- [よくある問題とトラブルシューティング](#よくある問題とトラブルシューティング)
- [完全なリファレンス](#完全なリファレンス)
  - [デバイスインベントリCSV形式](#デバイスインベントリcsv形式)
  - [To-Be配線CSV形式](#to-be配線csv形式)
  - [すべてのCLI引数](#すべてのcli引数)
  - [終了コード](#終了コード)
  - [出力ファイル形式](#出力ファイル形式)
- [技術詳細](#技術詳細)
  - [要件](#要件)
  - [データモデル](#データモデル)
  - [収集設計（SNMP LLDP）](#収集設計snmp-lldp)
  - [正規化ルール](#正規化ルール)
  - [リンク推論と重複排除](#リンク推論と重複排除)
  - [To-Be vs As-Is差分ロジック](#to-be-vs-as-is差分ロジック)
- [開発](#開発)
  - [開発コマンド](#開発コマンド)
  - [テスト計画](#テスト計画)
  - [実装計画](#実装計画)

## クイックスタート

**せっかちなユーザー向け** — 3ステップで始める方法:

1. **前提条件のインストール**:
   ```bash
   # Ubuntu/Debianの場合
   sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv snmp
   
   # Homebrewを使用したmacOSの場合
   brew install python3 net-snmp
   
   # Windowsの場合（WSL推奨）
   # WSLを使用してUbuntuの手順に従ってください
   ```

2. **nw-checkのインストール**:
   ```bash
   git clone https://github.com/icecake0141/nw-check.git
   cd nw-check
   python3 -m venv .venv
   source .venv/bin/activate  # Windowsの場合: .venv\Scripts\activate
   pip install -e .
   ```

3. **チェックの実行**:
   ```bash
   nw-check --devices samples/devices.csv --tobe samples/tobe.csv --out-dir output/
   ```

`output/`ディレクトリで結果を確認してください！

## インストールと前提条件

### システム要件

- **オペレーティングシステム**: Linux、macOS、またはWSL（Windows Subsystem for Linux）を使用したWindows
- **Python**: バージョン3.10以降
- **SNMPツール**: `snmpwalk`コマンドラインツール（net-snmpパッケージから）
- **ネットワークアクセス**: SNMPを介してネットワークデバイスに到達できる能力

### Python依存関係のインストール

**仮想環境の使用（推奨）**:

仮想環境は、Pythonパッケージを分離し、システムパッケージとの競合を防ぎます。

```bash
# リポジトリのクローン
git clone https://github.com/icecake0141/nw-check.git
cd nw-check

# 仮想環境の作成
python3 -m venv .venv

# 仮想環境の有効化
# Linux/macOSの場合:
source .venv/bin/activate
# Windowsの場合:
.venv\Scripts\activate

# nw-checkとその依存関係のインストール
pip install -e .

# 開発用（テストとリントツールを含む）:
pip install -e .[dev]
```

**インストールの確認**:

```bash
# nw-checkがインストールされていることを確認
nw-check --help

# 利用可能なオプションを含むヘルプメッセージが表示されます
```

### SNMPツールのインストール

このツールは、ネットワークデバイスにクエリを実行するために`snmpwalk`コマンドが必要です。

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install -y snmp
```

**CentOS/RHEL/Fedora**:
```bash
sudo yum install -y net-snmp-utils
# または新しいシステムの場合:
sudo dnf install -y net-snmp-utils
```

**macOS（Homebrewを使用）**:
```bash
brew install net-snmp
```

**Windows**:
- **推奨**: WSL（Windows Subsystem for Linux）を使用して、上記のUbuntuの手順に従ってください
- **代替**: Windows用のnet-snmpを非公式ソースからインストール（本番環境での使用は推奨されません）

**SNMPツールの確認**:
```bash
# snmpwalkが利用可能であることを確認
snmpwalk -V

# 次のようなバージョン情報が表示されます:
# NET-SNMP version: 5.9.1
```

## 基本的な使い方

### 入力ファイルの準備

nw-checkを実行するには、2つのCSVファイルが必要です:

1. **デバイスインベントリ** (`devices.csv`): ネットワークデバイスとそのSNMP認証情報をリストします
2. **To-Be配線** (`tobe.csv`): 意図したネットワーク接続を定義します

**デバイスインベントリの例** (`devices.csv`):
```csv
name,mgmt_ip,snmp_version,snmp_community,snmp_user,snmp_auth,snmp_priv
leaf01,10.0.0.1,2c,public,,,
spine01,10.0.0.2,3,,snmpuser,sha:authpass,aes:privpass
spine02,10.0.0.3,3,,snmpuser,SHA-256:authpass,AES-256:privpass
```

- SNMPv1/v2cデバイスの場合: `snmp_community`を提供
- SNMPv3デバイスの場合: `snmp_user`、`snmp_auth`（オプション）、`snmp_priv`（オプション）を提供

**To-Be配線の例** (`tobe.csv`):
```csv
device_a,port_a,device_b,port_b
leaf01,Eth1/1,spine01,Eth1/1
leaf01,Eth1/2,spine02,Eth1/1
```

各行は、2つのデバイス間の1つの物理リンクを表します。

**サンプルファイル**は、参照用に`samples/`ディレクトリで利用可能です。

### 最初のチェックの実行

```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/
```

**何が起こるか**:
1. ツールはデバイスインベントリとTo-Be配線ファイルを読み取ります
2. SNMPを介して各デバイスに接続し、LLDPネイバー情報を収集します
3. 実際の接続（As-Is）と意図した設計（To-Be）を比較します
4. `output/`ディレクトリにレポートを生成します

**ヒント**: `--show-progress`を追加して、ツールが何をしているかを確認します:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --show-progress
```

### 出力の理解

nw-checkを実行した後、出力ディレクトリに次のファイルが見つかります:

1. **`asis_links.csv`**: LLDPを介して検出されたすべての物理接続
   - ネットワークで実際に接続されているものを示します
   - 信頼度レベル（`observed`、`partial`、`unknown`）を含みます

2. **`diff_links.csv`**: To-BeとAs-Isの比較
   - 各意図したリンクが現実と一致するかどうかを示します
   - ステータス値:
     - `EXACT_MATCH`: 完全一致 ✓
     - `PORT_MISMATCH`: デバイスは一致しますが、ポートが異なります
     - `DEVICE_MISMATCH`: ポートは一致しますが、デバイスが異なります
     - `MISSING_ASIS`: この意図したリンクに対する実際の接続が見つかりません
     - `PARTIAL_OBSERVED`: 接続が見つかりましたが、情報が不完全です
     - `UNKNOWN`: 曖昧または競合する情報

3. **`summary.txt`**: 高レベルの概要
   - LLDP収集に失敗したデバイスをリストします
   - 不一致と欠落している接続のカウント

**結果の解釈**:

- `diff_links.csv`の`EXACT_MATCH`以外の`status`値を確認してください
- 各不一致の説明については、`reason`列を確認してください
- 収集失敗のあるデバイスについては、`summary.txt`を確認してください

## 高度な機能

### ドライランモード

ドライランモードでは、ネットワークデバイスに再クエリすることなく、To-Be配線の変更をテストできます。これは以下の場合に役立ちます:
- 配線定義の変更をテストする
- CI/CDパイプラインで実行する
- オフラインで作業する

**ワークフロー**:

1. 最初に、観測を収集して保存します:
   ```bash
   nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --save-observations obs.json
   ```

2. 後で、保存したデータでテストします:
   ```bash
   nw-check --devices devices.csv --tobe tobe-updated.csv --out-dir output/ --dry-run --load-observations obs.json
   ```

### 出力のフィルタリング

大規模なネットワークの場合、特定のデバイスまたは問題に焦点を当てるために出力をフィルタリングします:

**デバイス名でフィルタリング**:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --filter-devices leaf01,leaf02
```

**デバイスパターンでフィルタリング**:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --filter-devices-regex "^leaf"
```

**ステータスでフィルタリング**（不一致のみ表示）:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --filter-status PORT_MISMATCH,MISSING_ASIS
```

**フィルターの組み合わせ**:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ \
  --filter-devices-regex "^spine" \
  --filter-status PORT_MISMATCH
```

### 出力形式

デフォルトでは、nw-checkはCSVレポートを生成します。JSONまたは両方を出力することもできます:

```bash
# JSONのみ
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --output-format json

# CSVとJSONの両方
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --output-format both
```

JSON出力は以下の場合に役立ちます:
- 他のツールやAPIとの統合
- カスタムレポートスクリプト
- プログラマティック処理

### ネットワーク図の生成

Mermaid形式でネットワークトポロジーの視覚的な図を生成します:

```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --generate-mermaid
```

これにより、次のことができる`topology.mmd`が作成されます:
- GitHubマークダウンでレンダリング
- Mermaid互換ツールで表示
- ドキュメントに埋め込み

**注意**: 図はデフォルトで50デバイスに制限されています。`--mermaid-max-nodes`で調整します:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --generate-mermaid --mermaid-max-nodes 100
```

### Webコントロール付きスーパーバイザーモード

一時停止/再開/終了のためのWebベースのコントロールインターフェースでnw-checkを実行します:

```bash
nw-check-supervisor --devices devices.csv --tobe tobe.csv --out-dir output/ --control-port 8080
```

その後、ブラウザで http://127.0.0.1:8080 を開いてプロセスを制御します。

**セキュリティ注意**: `0.0.0.0`にバインドする場合（例: Dockerで）、`--control-token`を使用して認証を要求します:
```bash
nw-check-supervisor --devices devices.csv --tobe tobe.csv --out-dir output/ \
  --control-host 0.0.0.0 --control-port 8080 --control-token mysecrettoken
```

## よくある問題とトラブルシューティング

### 問題: `snmpwalk: command not found`

**解決策**: [SNMPツールのインストール](#snmpツールのインストール)で説明されているようにSNMPツールをインストールしてください

### 問題: `SNMP_TARGET_UNREACHABLE`エラー

**考えられる原因**:
- ネットワークデバイスのIPが正しくないか、到達できない
- SNMPトラフィック（UDPポート161）をブロックしているファイアウォール
- デバイスがオフラインまたは応答していない

**解決策**:
1. IPアドレスが正しいことを確認: `ping <device_ip>`
2. デバイスでSNMPが有効になっていることを確認
3. SNMPを手動でテスト:
   ```bash
   # SNMPv2cの場合:
   snmpwalk -v2c -c public <device_ip> system
   
   # SNMPv3の場合:
   snmpwalk -v3 -u snmpuser -l authPriv -a SHA -A authpass -x AES -X privpass <device_ip> system
   ```

### 問題: `SNMP_AUTH_FAILED`エラー

**考えられる原因**:
- 誤ったSNMPコミュニティ文字列（v1/v2c）
- 誤ったSNMPv3認証情報
- SNMPv3プロトコルの不一致

**解決策**:
1. `devices.csv`のSNMP認証情報を確認
2. デバイスのSNMP設定が認証情報と一致していることを確認
3. SNMPv3の場合、認証とプライバシープロトコルがデバイス設定と一致していることを確認

### 問題: すべてのリンクが`MISSING_ASIS`を表示

**考えられる原因**:
- デバイスでLLDPが有効になっていない
- `tobe.csv`のデバイス名が`devices.csv`の名前と一致しない
- インターフェースでLLDPが実行されていない

**解決策**:
1. ネットワークデバイスでLLDPを有効にする（デバイスのドキュメントを確認）
2. デバイス名が正確に一致することを確認（大文字小文字を区別）
3. インターフェースが稼働していてLLDPが送信されていることを確認: `asis_links.csv`を確認

### 問題: ポート名が同じように見えても一致しない

**原因**: ポートの正規化はほとんどのバリエーションを処理しますが、一部の形式は認識されない場合があります

**解決策**: 
- 詳細については、`diff_links.csv`の`reason`フィールドを確認
- ポート名は正規化されます（例: `Eth1/1`、`Ethernet1/1`、`eth1/1`はすべて同等として扱われます）
- 正規化が機能していない場合は、ポート名の形式で問題を報告してください

### 問題: Python `ModuleNotFoundError`

**原因**: 仮想環境が有効になっていないか、パッケージがインストールされていない

**解決策**:
```bash
# 仮想環境を有効化
source .venv/bin/activate  # Linux/macOS
# または
.venv\Scripts\activate  # Windows

# 必要に応じて再インストール
pip install -e .
```

### 問題: 部分的な観測または不明なデバイス

**原因**: LLDP情報が不完全（システム名またはシャーシIDが欠落）

**解決策**:
- デバイスのLLDP設定を確認
- 一部のデバイスはすべてのLLDPフィールドを送信しない場合があります
- シャーシIDの一致を支援するために、`devices.csv`にデバイス`aliases`を追加

### さらなるヘルプを得る

1. **詳細なログを有効にする**:
   ```bash
   nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --log-level DEBUG
   ```

2. **SNMPコマンドのログを有効にする**（シークレットは編集されます）:
   ```bash
   nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --snmp-verbose
   ```

3. **GitHubのIssuesを確認**: [icecake0141/nw-check/issues](https://github.com/icecake0141/nw-check/issues)

## 完全なリファレンス

### デバイスインベントリCSV形式

デバイスインベントリCSVは、チェックするすべてのネットワークデバイスとそのSNMP認証情報を定義します。

**必須カラム**:
- `name`: 一意のデバイス名（識別子として使用）
- `mgmt_ip`: 管理IPアドレス
- `snmp_version`: SNMPバージョン（`1`、`2c`、または`3`）

**SNMPv1/v2cカラム**:
- `snmp_community`: コミュニティ文字列（v1/v2cに必須）

**SNMPv3カラム**:
- `snmp_user`: ユーザー名（v3に必須）
- `snmp_auth`: 認証プロトコルとパスフレーズ（オプション、形式: `protocol:secret`）
- `snmp_priv`: プライバシープロトコルとパスフレーズ（オプション、形式: `protocol:secret`）

**オプションカラム**:
- `aliases`: デバイスの代替名のカンマ区切りリスト（LLDPシステム名の一致に役立ちます）

#### SNMPv3認証とプライバシープロトコル

SNMPv3の場合、`snmp_auth`および`snmp_priv`フィールドは`protocol:secret`の形式を使用します。

**サポートされている認証プロトコル**（大文字小文字を区別しません）:
- `MD5` - Message Digest 5
- `SHA`または`SHA1` - SHA-1
- `SHA-224`または`SHA224` - SHA-224（ハイフンの有無）
- `SHA-256`または`SHA256` - SHA-256（ハイフンの有無）
- `SHA-384`または`SHA384` - SHA-384（ハイフンの有無）
- `SHA-512`または`SHA512` - SHA-512（ハイフンの有無）

**サポートされているプライバシープロトコル**（大文字小文字を区別しません）:
- `DES` - Data Encryption Standard
- `AES`、`AES128`、または`AES-128` - AES 128ビット（複数のバリアント）
- `AES-192`または`AES192` - AES 192ビット（ハイフンの有無）
- `AES-256`または`AES256` - AES 256ビット（ハイフンの有無）

**CSVの例**:
```csv
name,mgmt_ip,snmp_version,snmp_community,snmp_user,snmp_auth,snmp_priv,aliases
leaf01,10.0.0.1,2c,public,,,,"leaf-1,leaf-one"
spine01,10.0.0.2,3,,snmpuser,sha:authpass,aes:privpass,spine-1
spine02,10.0.0.3,3,,snmpuser,SHA-256:authpass,AES-256:privpass,spine-2
leaf02,10.0.0.4,3,,snmpuser,md5:authpass,des:privpass,"leaf-2,leaf-two"
```

**エラーハンドリング**:
サポートされていないプロトコルが指定されている場合、nw-checkは無効な設定を持つデバイスを示し、サポートされているプロトコルをリストアップする明確なエラーメッセージをログに記録します。デバイスはLLDP収集中にスキップされます。

### To-Be配線CSV形式

To-Be配線CSVは、検証のための意図されたネットワークリンクトポロジーを定義します。

**必須カラム**:
- `device_a`: 最初のデバイスの名前（インベントリのデバイスと一致する必要があります）
- `port_a`: device_aのポート識別子（例: `Eth1/1`、`GigabitEthernet0/1`）
- `device_b`: 2番目のデバイスの名前（インベントリのデバイスと一致する必要があります）
- `port_b`: device_bのポート識別子（例: `Eth1/1`、`GigabitEthernet0/1`）

**CSVの例** (`tobe.csv`):
```csv
device_a,port_a,device_b,port_b
leaf01,Eth1/1,spine01,Eth1/1
leaf01,Eth1/2,spine02,Eth1/1
leaf02,Eth1/1,spine01,Eth1/2
leaf02,Eth1/2,spine02,Eth1/2
```

**重要な注意事項**:
- ポート名は比較中に正規化されます（ベンダー固有の略語を処理）
- device_a/device_bの順序は重要ではありません。リンクは双方向です
- 各行は2つのデバイス間の1つの物理リンクを表します

### すべてのCLI引数

**必須引数**:
- `--devices PATH`: デバイスインベントリCSVファイルへのパス
- `--tobe PATH`: To-Be配線CSVファイルへのパス
- `--out-dir PATH`: レポートの出力ディレクトリ

**SNMPオプション**:
- `--snmp-timeout SECONDS`: SNMP タイムアウト秒数（デフォルトは異なります）
- `--snmp-retries N`: SNMP 再試行回数（デフォルトは異なります）
- `--snmp-verbose`: 詳細なSNMPコマンドログを有効にする（シークレットは編集されます）

**出力オプション**:
- `--output-format FORMAT`: 出力形式: `csv`、`json`、または`both`（デフォルト: `csv`）
- `--show-progress`: LLDP収集中に進捗を表示
- `--log-level LEVEL`: ログレベル: `INFO`、`DEBUG`、または`WARN`（デフォルト: `INFO`）

**ドライランと観測管理**:
- `--dry-run`: SNMP収集をスキップして保存された観測を使用（`--load-observations`が必要）
- `--load-observations PATH`: SNMPを介して収集する代わりにJSONファイルから観測をロード
- `--save-observations PATH`: 後でドライラン使用のために収集した観測をJSONファイルに保存

**フィルタリングオプション**:
- `--filter-devices NAMES`: 出力に含めるデバイス名のカンマ区切りリスト
- `--filter-devices-regex PATTERN`: デバイスをフィルタリングする正規表現パターン（例: `"^leaf"`）
- `--filter-status STATUSES`: 含める差分ステータスのカンマ区切りリスト（例: `PORT_MISMATCH,MISSING_ASIS`）
  - 利用可能なステータス: `EXACT_MATCH`、`PORT_MISMATCH`、`DEVICE_MISMATCH`、`MISSING_ASIS`、`PARTIAL_OBSERVED`、`UNKNOWN`

**図のオプション**:
- `--generate-mermaid`: ネットワークトポロジーのMermaid図を生成
- `--mermaid-max-nodes N`: Mermaid図の最大ノード数（デフォルト: 50）

**スーパーバイザー固有の引数**（`nw-check-supervisor`コマンド用）:
- `--control-host HOST`: コントロールサーバーのバインドアドレス（デフォルト: `127.0.0.1`）
- `--control-port PORT`: コントロールサーバーのポート（デフォルト: `8080`）
- `--control-token TOKEN`: UI/APIリクエストのオプション共有シークレット（`0.0.0.0`バインドに推奨）
- `--shutdown-on-exit` / `--no-shutdown-on-exit`: nw-check終了時にコントロールサーバーを停止するかどうか
- `--terminate-timeout SECONDS`: プロセスグループを強制終了する前に待機する秒数

### 終了コード

- `0`: 成功、重大なエラーなし
- `2`: 収集失敗を伴う部分的な成功（一部のデバイスでLLDP収集が失敗）
- `3`: 無効な入力または回復不可能なエラー（例: 不正なCSV、必要なファイルの欠落）

### 出力ファイル形式

#### As-Isリンク（CSV）

**ファイル名**: `asis_links.csv`

**カラム**:
- `local_device`: ローカルデバイスの名前
- `local_port`: ローカルデバイスのポート
- `remote_device`: リモートデバイスの名前（または "unknown"）
- `remote_port`: リモートデバイスのポート（または "unknown"）
- `confidence`: 信頼度レベル（`observed`、`partial`、`unknown`）
- `evidence`: 情報のソース（例: `lldp`、`lldp:missing_remote`）

**例**:
```csv
local_device,local_port,remote_device,remote_port,confidence,evidence
leaf01,Eth1/1,spine01,Eth1/1,observed,lldp
leaf02,Eth1/1,unknown,unknown,partial,lldp:missing_remote
```

#### To-Be vs As-Is差分（CSV）

**ファイル名**: `diff_links.csv`

**カラム**:
- `device_a`: 意図したリンクの最初のデバイス
- `port_a`: device_aのポート
- `device_b`: 意図したリンクの2番目のデバイス
- `port_b`: device_bのポート
- `status`: 一致ステータス（下記参照）
- `reason`: ステータスの説明

**ステータス値**:
- `EXACT_MATCH`: 正規化後にデバイスとポートが一致 ✓
- `PORT_MISMATCH`: デバイスは一致しますが、ポートが異なります
- `DEVICE_MISMATCH`: ポートは一致しますが、デバイスが異なります
- `MISSING_ASIS`: このTo-Beリンクに対するAs-Is観測が見つかりません
- `PARTIAL_OBSERVED`: As-Is観測は存在しますが、不完全です（不明なデバイスまたはポート）
- `UNKNOWN`: 曖昧または競合する一致

**例**:
```csv
device_a,port_a,device_b,port_b,status,reason
leaf01,Eth1/1,spine01,Eth1/1,EXACT_MATCH,normalized ports matched
leaf02,Eth1/1,spine01,Eth1/2,PORT_MISMATCH,remote port differs: Eth1/3
leaf01,Eth1/2,leaf02,Eth1/2,MISSING_ASIS,no lldp observation
```

#### サマリー（テキスト）

**ファイル名**: `summary.txt`

含まれる内容:
- `lldp_failed_devices`: LLDP収集に失敗したデバイス名のリスト
- `missing_ports`: 不明なリモートポートを持つ接続のカウント
- `mismatch_links`: `EXACT_MATCH`以外のステータスを持つリンクのカウント

#### JSON出力形式

`--output-format json`または`--output-format both`を使用する場合、ツールはCSVファイルと同じ構造のJSONファイルを生成しますが、JSON形式です。これはAPI統合とプログラマティック処理に役立ちます。

**As-IsリンクJSONの例** (`asis_links.json`):
```json
[
  {
    "local_device": "leaf01",
    "local_port": "Eth1/1",
    "remote_device": "spine01",
    "remote_port": "Eth1/1",
    "confidence": "observed",
    "evidence": ["lldp"]
  }
]
```

#### Mermaid図の出力

**ファイル名**: `topology.mmd`

`--generate-mermaid`を使用する場合、ネットワークトポロジーを視覚化するMermaid図を生成します。

**機能**:
- デバイスをノードとして、リンクをエッジとして表示
- 接続にポートラベルを表示
- 差分ステータスに基づいてデバイスを色分け:
  - 緑（`#ccffcc`）: すべてのリンクがTo-Beと一致
  - 赤（`#ffcccc`）: 1つ以上の不一致
- "unknown"デバイスを除外
- `--mermaid-max-nodes`デバイスに制限

**注意**: 図は補助的なものであり、権威あるものとは見なされるべきではありません。

## 技術詳細

このセクションには、開発者と上級ユーザー向けの詳細な技術情報が含まれています。

### 要件

#### 機能要件

- SNMPを介してターゲットデバイスからLLDPネイバー情報を収集し、リンクのAs-Isビューを構築する。
- As-Isリンクを配線定義のTo-Beと比較し、不一致や欠落を分類する。
- 人が確認できる表形式のレポートを出力する:
  - As-Isで観測されたリンク
  - To-Be vs As-Isの差分結果（明示的な理由付き）
  - 失敗、欠落データ、不一致のサマリー
- デバイスインベントリとTo-Be配線のCSV入力をサポートする。
- 欠落または不確実なデータを明示的にする（例: 不明なデバイス、部分的な観測）。

#### 非機能要件

- Linux/WSL/WindowsのPythonランタイム上で動作する。
- マルチベンダーデバイスとLLDPスキーマの違いに対応し、実行全体が失敗しないようにする。
- 安定したソートにより、出力を決定論的に保つ。
- 同じ物理リンクの二重カウントを避ける。

#### 前提条件 / 非目標

- グラフィカルな図は任意。実装する場合はMermaidテキスト出力のみで、補助的なものとして扱う。
- 継続的な検出は行わない。初期構築と配線変更時の手動実行のみ。
- インターフェースの状態（up/down）とのリアルタイム相関は、LLDP可用性を超えては行わない。
- 初期スコープでは標準LLDP-MIBを超えるベンダー固有の独自検出は行わない。
- LLDP収集にはSNMPv1、v2c、v3がサポートされる。

### データモデル

#### 正規化された共通スキーマ

- **Device（デバイス）**
  - `name`: インベントリからの正規デバイス名
  - `mgmt_ip`: 管理IPアドレス
  - `snmp`: バージョンと認証情報（v1/v2cの場合はcommunity、v3の場合はuser/auth/priv）
- **Interface（インターフェース）**
  - `device`: 正規デバイス名
  - `name_raw`: 生のインターフェース名
  - `name_norm`: 正規化されたインターフェース名
- **LinkObservation（As-Is）**
  - `local_device`
  - `local_port_raw`
  - `local_port_norm`
  - `remote_device_id`: 生のシャーシIDまたはシステム名
  - `remote_device_name`: マッピングされた場合の解決された正規デバイス名
  - `remote_port_raw`
  - `remote_port_norm`
  - `source`: `lldp`
  - `confidence`: `observed` | `partial` | `unknown`
  - `errors`: 部分的な場合のエラーコードのリスト
- **LinkIntent（To-Be）**
  - `device_a`, `port_a_raw`, `port_a_norm`
  - `device_b`, `port_b_raw`, `port_b_norm`
- **LinkDiff（リンク差分）**
  - `tobe_link`: LinkIntent参照
  - `asis_link`: LinkObservation参照または`null`
  - `status`: マッチカテゴリ
  - `reason`: テキストによる理由

### 収集設計（SNMP LLDP）

#### 標準LLDP-MIB

- `lldpRemTable`（LLDP-MIB::lldpRemTable）
  - リモートシャーシID
  - リモートポートID
  - リモートシステム名（利用可能な場合）
- `lldpLocPortTable`（LLDP-MIB::lldpLocPortTable）
  - ローカルポートIDと説明

#### 収集するフィールド

- ローカルポート識別子と説明
- リモートシャーシID（タイプ + 値）
- リモートポートID（タイプ + 値）
- リモートシステム名

#### 欠落データの処理

- リモートシステム名が欠落している場合: `remote_device_id`を保持し、`remote_device_name`を`unknown`とマークする。
- リモートポートIDが欠落している場合: `remote_port_*`を`unknown`とマークし、`confidence`を`partial`に設定する。
- LLDPテーブルが返されない場合: デバイスレベルの収集失敗を記録する。

#### エラー分類

- `SNMP_TARGET_UNREACHABLE`
- `SNMP_AUTH_FAILED`
- `SNMP_MIB_MISSING`
- `SNMP_COMMAND_MISSING`
- `SNMP_COMMAND_FAILED`
- `SNMP_UNKNOWN_ERROR`
- `LLDP_TABLE_EMPTY`
- `LLDP_PARTIAL_ROW`

### 正規化ルール

- インターフェース名の正規化:
  - 大文字小文字を区別しない。
  - ベンダー固有の略語をマッピング（例: `Eth`、`Ethernet`、`Gi`、`GigabitEthernet`）。
  - 空白を削除し、区切り文字を標準化（`Eth1/1`スタイル）。
- デバイスアイデンティティの正規化:
  - インベントリのデバイス名を正規名として優先する。
  - LLDPの`sysName`を完全一致または設定されたエイリアスマップを使用してインベントリに解決する。
    - デバイスインベントリには、カンマ区切りの名前を含む`aliases`カラムを含めることができる。
  - シャーシIDのみが利用可能な場合、`remote_device_id`として保持し、不確実性をマークする。

### リンク推論と重複排除

- 各LLDP行を方向性のある観測として扱う。
- 正規化されたキーによる重複排除:
  - デバイス/ポートペアの辞書順で`(device_a, port_a_norm, device_b, port_b_norm)`。
- 両方向が観測された場合:
  - `confidence=observed`で1つのリンクにマージし、証拠リストを保存する。
- 一方向のみが観測された場合:
  - `confidence=partial`で単一リンクを保持する。

### To-Be vs As-Is差分ロジック

#### マッチカテゴリ

- `EXACT_MATCH`: 正規化後にデバイスとポートが一致。
- `PORT_MISMATCH`: デバイスは一致するが、ポートが異なる。
- `DEVICE_MISMATCH`: ポートは一致するが、デバイスが異なる。
- `MISSING_ASIS`: To-BeリンクにAs-Is観測がない。
- `PARTIAL_OBSERVED`: As-Isが部分的。デバイスまたはポートが不明。
- `UNKNOWN`: 曖昧または競合する一致。

#### マッチング優先順位

1. 正規化されたデバイス + ポートペアの完全一致。
2. ポート不一致の証拠を持つデバイス一致。
3. デバイス不一致の証拠を持つポート一致。
4. 曖昧な場合、シャーシIDまたはリモートシステム名を使用した部分一致。

#### 不確実性の表現

- リモートデバイス名が解決されない場合、生のシャーシIDを含む`reason`で`PARTIAL_OBSERVED`を報告する。
- 複数のAs-Is候補がTo-Beリンクに一致する場合、候補をリストアップして`UNKNOWN`を報告する。

## 開発

このセクションは、nw-checkに貢献する開発者向けです。

### 開発コマンド

**テストの実行**:
```bash
python -m pytest
```

**コードのリント**:
```bash
python -m pylint nw_check
```

**コードのフォーマット**:
```bash
python -m ruff format
```

**型チェック**:
```bash
python -m mypy nw_check
```

### 継続的インテグレーション

GitHub Actionsは、プッシュとプルリクエストでフォーマットチェック、リント、型チェック、テスト、およびpre-commitフックを実行します。

### テスト計画

#### ユニットテスト

- インターフェース名の正規化（略語マッピングと大文字小文字の処理）。
- 双方向観測の重複排除ロジック。
- 各カテゴリの差分分類。

#### サンプル入力期待値

- `samples/`で提供されるサンプルCSVを使用して検証:
  - 完全一致検出
  - ポート不一致検出
  - As-Isリンク欠落検出
  - sysNameが存在しない場合の部分観測処理

### 実装計画

#### モジュール

- `nw_check.cli`: CLI解析とエントリーポイント
- `nw_check.inventory`: デバイスCSV解析
- `nw_check.lldp_snmp`: SNMP収集とLLDP解析
- `nw_check.normalize`: 正規化ユーティリティ
- `nw_check.link_infer`: 推論と重複排除
- `nw_check.diff`: To-Be vs As-Is比較
- `nw_check.output`: CSV/テキストレポートレンダリング
- `nw_check.mermaid`: Mermaid図生成
- `nw_check.filters`: 出力フィルタリングユーティリティ
- `nw_check.supervisor`: Webコントロールインターフェース

#### 依存関係

- Python 3.10以降
- `snmpwalk` CLIコマンド（net-snmpパッケージから）SNMP/LLDP収集用
  - システムのPATH上で利用可能である必要があります
  - ネットワークデバイスからLLDP-MIBテーブルをクエリするために使用されます

#### ログ

- デバイスコンテキストとエラーコードを含む構造化ログ。
- 生のLLDP行のデバッグログ。

---

**質問や問題がありますか？** [GitHub Issuesページ](https://github.com/icecake0141/nw-check/issues)をご覧ください。
