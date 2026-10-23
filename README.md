# discord-weather-notify

Discord の Webhook を使って、毎朝 8:00 に東京の今日の天気予報を、決めておいたチャンネルへ自動で通知する Python プログラムです。

## 何をするものか

1. `.env` に書いた Discord の Webhook URL を読み込む
2. 無料の天気予報 API [Open-Meteo](https://open-meteo.com/) から、東京の今日の天気・最高/最低気温・降水確率を取る
3. 天気をカード（埋め込み）の形にして、Webhook で Discord のチャンネルに送る
4. Mac の定期実行（launchd）で、これを毎朝 8:00 に自動で動かす

```
% python main.py
東京の天気を取得しています...
Discord に送信しました（2026-10-23 08:00:01）
```

天気が取れなかった日は、Discord に「今日の天気を取得できませんでした」と送ります（自動実行では誰も画面を見ていないため）。

## 事前準備

### 1. ライブラリのインストール

```bash
pip install requests python-dotenv
```

天気予報の API（Open-Meteo）は登録も API キーも要りません。

### 2. Discord のウェブフックの作成

1. Discord で自分のサーバーを開く（無ければ左の「＋」→「オリジナルの作成」で作る）
2. 通知を送りたいチャンネルの ⚙（チャンネルの編集）→「連携サービス」→「ウェブフックを作成」
3. できたウェブフックをクリックし、名前（例：`天気お知らせ`）を付けて「ウェブフックURLをコピー」

ウェブフックは、そのチャンネルに投稿することしかできません。ボットのようにサーバー全体の権限を持たないので、範囲を最小にできます。

## 秘密ファイルの用意の仕方

Webhook URL は、知っていれば誰でもそのチャンネルに投稿できてしまうので、GitHub に載せていません（`.gitignore` で除外）。自分で用意してください。

| ファイル | 中身 | 用意の仕方 |
|---|---|---|
| `.env` | Discord の Webhook URL | `.env.example` をコピーして `.env` という名前にし、上でコピーした URL を書く |

`.env` の例：

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1234567890/xxxxxxxx
```

## 使い方

```bash
python main.py            # 天気を取って Discord に送る
python main.py --dry-run  # 送らずに、送る中身だけ表示する（お試し）
```

都市や送り主の名前を変えたいときは、`main.py` の先頭の設定（`CITY_NAME`、`LATITUDE`、`LONGITUDE`、`SENDER_NAME`）を書き換えます。

## 毎朝の自動実行（launchd）

launchd は Mac に最初から入っている「目覚まし時計係」です。`launchd/discord-weather.plist.example` に「毎朝 8:00 に main.py を動かす」と書いてあるので、自分の環境に合わせてコピーし、登録します。このフォルダで次を実行してください。

```bash
# 1. ログを入れるフォルダを作る
mkdir -p logs

# 2. 見本の __PYTHON__ と __PROJECT_DIR__ を自分の環境に置き換えて、launchd の置き場所にコピーする
sed -e "s#__PYTHON__#$(which python)#" -e "s#__PROJECT_DIR__#$(pwd)#g" \
  launchd/discord-weather.plist.example > ~/Library/LaunchAgents/local.discord-weather.plist

# 3. 登録する（これで毎朝 8:00 に動く）
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.discord-weather.plist
```

| やりたいこと | コマンド |
|---|---|
| 朝を待たずに今すぐ動かして試す | `launchctl kickstart gui/$(id -u)/local.discord-weather` |
| 登録されているか見る | `launchctl print gui/$(id -u)/local.discord-weather` |
| 結果を見る | `cat logs/notify.log logs/error.log` |
| 自動実行をやめる | `launchctl bootout gui/$(id -u)/local.discord-weather` |

- 8:00 に Mac がスリープしていた場合は、起きたときに動きます
- 電源が切れていた日は動きません
- 時刻を変えたいときは、plist の `Hour`・`Minute` を書き換え、一度やめてから登録し直します

## うまくいかないとき

| 表示 | 対処 |
|---|---|
| DISCORD_WEBHOOK_URL が設定されていません | `.env` を作り、`DISCORD_WEBHOOK_URL=` の後ろに URL を書く |
| ウェブフック URL ではありません | Discord の「ウェブフックURLをコピー」でコピーし直す |
| ウェブフックが見つかりません | Discord でウェブフックを消していないか、URL を最後まで全部コピーしたか確かめる |
| 送りすぎたため、Discord に止められました | 少し待ってからやり直す |
| Discord につながりませんでした | インターネット接続を確かめる |
| 天気を取得できませんでした | 天気予報のサーバーの不調か、接続の問題。時間をおいてやり直す |
| 朝に通知が来ない | `logs/error.log` を見る。`launchctl print ...` で登録されているか確かめる |

詳しい仕様は [要件定義書.md](要件定義書.md) を見てください。
