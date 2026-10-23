"""
Discord 天気お知らせボット（課題：Discord API）

Open-Meteo から東京の今日の天気予報を取り、
Discord の Webhook を使って、指定したチャンネルに通知する。
Mac の定期実行（launchd）で、毎朝 8:00 に自動で動かす。

使い方：
  python main.py            天気を取って Discord に送る
  python main.py --dry-run  送らずに、送る中身だけ表示する（お試し）
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# ============================================================
# 設定（ここをまとめて書いておく）
# ============================================================

# このプログラム（main.py）が置いてあるフォルダ
BASE_DIR = Path(__file__).resolve().parent

# Webhook URL を書いておくファイルと、その中の項目名
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE_FILE = BASE_DIR / ".env.example"
WEBHOOK_NAME = "DISCORD_WEBHOOK_URL"

# Webhook URL の始まり（古い形の discordapp.com も受け付ける）
WEBHOOK_URL_PREFIXES = (
    "https://discord.com/api/webhooks/",
    "https://discordapp.com/api/webhooks/",
)

# 天気を知りたい場所（東京都庁のあたり）
CITY_NAME = "東京"
LATITUDE = 35.6895
LONGITUDE = 139.6917
TIMEZONE = "Asia/Tokyo"

# 天気予報の API（Open-Meteo。登録・API キー不要）
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"

# Discord に表示する送り主の名前と、カードの左の帯の色（16進数の色番号）
SENDER_NAME = "天気お知らせ"
EMBED_COLOR = 0x3498DB

# 降水確率がこの値（%）以上なら、傘の一言を足す
UMBRELLA_THRESHOLD = 50

# 相手の返事を待つ秒数（これを過ぎたら「応答が無い」として終わる）
TIMEOUT_SECONDS = 10

# お試し表示にするときの指定
DRY_RUN_OPTION = "--dry-run"

# 曜日の表示（月曜日が 0）
WEEKDAYS = "月火水木金土日"

# 天気コード（WMO コード）→（日本語, 絵文字）
WEATHER_CODES = {
    0: ("快晴", "☀️"),
    1: ("晴れ", "🌤️"),
    2: ("晴れ時々くもり", "⛅"),
    3: ("くもり", "☁️"),
    45: ("霧", "🌫️"),
    48: ("霧（霧氷）", "🌫️"),
    51: ("弱い霧雨", "🌦️"),
    53: ("霧雨", "🌦️"),
    55: ("強い霧雨", "🌦️"),
    56: ("凍る霧雨", "🌧️"),
    57: ("強い凍る霧雨", "🌧️"),
    61: ("弱い雨", "🌧️"),
    63: ("雨", "🌧️"),
    65: ("強い雨", "🌧️"),
    66: ("凍る雨", "🌧️"),
    67: ("強い凍る雨", "🌧️"),
    71: ("弱い雪", "🌨️"),
    73: ("雪", "🌨️"),
    75: ("強い雪", "🌨️"),
    77: ("霧雪", "🌨️"),
    80: ("弱いにわか雨", "🌦️"),
    81: ("にわか雨", "🌦️"),
    82: ("激しいにわか雨", "🌧️"),
    85: ("にわか雪", "🌨️"),
    86: ("強いにわか雪", "🌨️"),
    95: ("雷雨", "⛈️"),
    96: ("ひょうを伴う雷雨", "⛈️"),
    99: ("強いひょうを伴う雷雨", "⛈️"),
}


# ============================================================
# F1 設定の読み込み
# ============================================================
def load_webhook_url():
    """
    .env から Webhook URL を読み込んで返す。
    .env が無い・空・Webhook の形でない場合は、理由を表示して終了する（F8）。
    """
    # .env の中身を「環境変数」（プログラムが読める設定値）として読み込む
    load_dotenv(ENV_FILE)
    url = os.getenv(WEBHOOK_NAME, "").strip()

    if not url:
        show_error_and_exit(
            f"{WEBHOOK_NAME} が設定されていません。\n"
            f"{ENV_EXAMPLE_FILE.name} をコピーして「{ENV_FILE.name}」という名前にし、\n"
            "Discord でコピーしたウェブフック URL を書いてください。\n"
            f"置き場所: {BASE_DIR}"
        )
    if not url.startswith(WEBHOOK_URL_PREFIXES):
        show_error_and_exit(
            f"{WEBHOOK_NAME} が Discord のウェブフック URL ではありません"
            f"（{WEBHOOK_URL_PREFIXES[0]} で始まるはずです）。\n"
            "Discord のチャンネルの編集 →「連携サービス」→「ウェブフック」で、\n"
            "「ウェブフックURLをコピー」を押してコピーし直してください。"
        )
    return url


# ============================================================
# F2 天気の取得
# ============================================================
def fetch_weather():
    """
    Open-Meteo から今日の天気を取り、次の形の辞書で返す。
    {"date": 日付, "code": 天気コード, "max": 最高気温, "min": 最低気温, "rain": 降水確率}
    取れなかった場合は、例外（requests.RequestException / ValueError など）が起きる。
    """
    response = requests.get(
        WEATHER_API_URL,
        params={
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            # 1日分の「天気コード・最高気温・最低気温・降水確率」を頼む
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": TIMEZONE,
            "forecast_days": 1,
        },
        timeout=TIMEOUT_SECONDS,
    )
    # 200 番台以外（400 や 500 など）なら例外にする
    response.raise_for_status()

    # 返事は「項目ごとに日付の数だけ並んだリスト」なので、1日目（[0]）を取り出す
    daily = response.json()["daily"]
    return {
        "date": date.fromisoformat(daily["time"][0]),
        "code": daily["weather_code"][0],
        "max": daily["temperature_2m_max"][0],
        "min": daily["temperature_2m_min"][0],
        "rain": daily["precipitation_probability_max"][0],
    }


# ============================================================
# F3 メッセージを作る
# ============================================================
def describe_weather(code):
    """
    天気コードを（日本語, 絵文字）に直して返す。知らないコードなら「不明」と返す。
    """
    return WEATHER_CODES.get(code, (f"不明（コード {code}）", "❔"))


def build_weather_message(weather):
    """
    天気の辞書から、Discord に送るメッセージ（埋め込みのカード付き）を作って返す。
    """
    name, emoji = describe_weather(weather["code"])
    day = weather["date"]
    title = f"{emoji} 今日の{CITY_NAME}の天気（{day.month}/{day.day} {WEEKDAYS[day.weekday()]}）"

    # 降水確率が高い日だけ、傘の一言を足す（降水確率が取れない日は None になる）
    rain = weather["rain"]
    description = "☂️ 傘を持っていきましょう" if rain is not None and rain >= UMBRELLA_THRESHOLD else None

    embed = {
        "title": title,
        "color": EMBED_COLOR,
        # inline を True にすると、項目が横に並ぶ
        "fields": [
            {"name": "天気", "value": name, "inline": False},
            {"name": "最高気温", "value": format_value(weather["max"], "℃"), "inline": True},
            {"name": "最低気温", "value": format_value(weather["min"], "℃"), "inline": True},
            {"name": "降水確率", "value": format_value(rain, "%"), "inline": True},
        ],
        "footer": {"text": "Open-Meteo の予報より"},
    }
    if description:
        embed["description"] = description

    return {"username": SENDER_NAME, "embeds": [embed]}


def build_failure_message(reason):
    """
    天気が取れなかったときに Discord に送る、お知らせのメッセージを作って返す。
    """
    return {
        "username": SENDER_NAME,
        "content": f"⚠️ 今日の{CITY_NAME}の天気を取得できませんでした。\n理由: {reason}",
    }


def format_value(value, unit):
    """
    数値に単位を付けた文字列にする。値が無い（None）ときは「—」にする。
    """
    return "—" if value is None else f"{value}{unit}"


# ============================================================
# F4 Discord に送る
# ============================================================
def send_to_discord(url, message):
    """
    Webhook URL にメッセージを JSON で送り、Discord が返したメッセージの中身を返す。
    失敗したら、理由を表示して終了する（F8）。

    - URL の後ろに ?wait=true を付けると、投稿したメッセージ（ID など）を返してくれる
    - Discord は、失敗すると HTTP のステータスコード（401・404 など）で知らせる
    """
    response = requests.post(
        url,
        params={"wait": "true"},
        json=message,
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        show_error_and_exit(explain_discord_error(response))
    return response.json()


# ============================================================
# F5 結果の表示
# ============================================================
def now_text():
    """
    今の日時を「2026-10-23 08:00:01」の形の文字列で返す（ログに残すため）。
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# F6 お試し表示
# ============================================================
def show_preview(message):
    """
    Discord に送るはずの中身を、画面に表示する（送らない）。
    """
    print("--- 送る中身（お試し表示。Discord には送りません）---")
    print(f"送り主: {message['username']}")
    if "content" in message:
        print(message["content"])
    for embed in message.get("embeds", []):
        print(embed["title"])
        if "description" in embed:
            print(embed["description"])
        for field in embed["fields"]:
            print(f"  {field['name']}: {field['value']}")
        print(f"  （{embed['footer']['text']}）")


# ============================================================
# F8 エラー表示
# ============================================================
def show_error_and_exit(message):
    """
    原因が分かる日本語のエラーメッセージを、日時付きで表示して、プログラムを終了する。
    """
    print(f"[{now_text()}] エラー: {message}", file=sys.stderr)
    sys.exit(1)


def explain_discord_error(response):
    """
    Discord が返した失敗の返事を、日本語の説明に直して返す。
    """
    status = response.status_code
    # 返事の中身（JSON）に、Discord のエラーの理由が入っている
    try:
        detail = response.json()
    except ValueError:
        detail = response.text[:200]

    # Webhook が見つからない（消された・ID が違う）／鍵の部分（URL の後ろ半分）が違う
    if status in (401, 404):
        return (
            "Discord のウェブフックが見つかりません。次の2つを確認してください。\n"
            "  ・Discord でそのウェブフックを消していないか\n"
            f"  ・{ENV_FILE.name} の {WEBHOOK_NAME} に、URL を最後まで全部コピーしたか\n"
            f"詳細: HTTP {status} {detail}"
        )
    # 送りすぎ
    if status == 429:
        return (
            "短い時間に送りすぎたため、Discord に止められました。少し待ってからやり直してください。\n"
            f"詳細: HTTP {status} {detail}"
        )
    # 送った中身がおかしい
    if status == 400:
        return f"Discord が送った中身を受け付けませんでした。\n詳細: HTTP {status} {detail}"
    return f"Discord への送信に失敗しました。\n詳細: HTTP {status} {detail}"


# ============================================================
# メインの処理（上の関数を順番に呼ぶ）
# ============================================================
def main():
    """
    プログラム全体の流れ：
    設定の読み込み → 天気の取得 → メッセージを作る → Discord に送る → 結果の表示
    （お試し表示のときは、送る代わりに中身を表示する）
    """
    dry_run = DRY_RUN_OPTION in sys.argv[1:]

    try:
        # F1 設定の読み込み（お試し表示では送らないので、URL は要らない）
        url = None if dry_run else load_webhook_url()

        # F2 天気の取得
        print(f"{CITY_NAME}の天気を取得しています...")
        weather_error = None
        try:
            weather = fetch_weather()
        except requests.HTTPError as error:
            # つながったが、エラー（404 や 500 など）が返ってきた
            weather_error = f"天気予報のサーバーがエラーを返しました（HTTP {error.response.status_code}）"
        except requests.RequestException as error:
            # 詳細は種類の名前だけにする（中身には長い URL が入っていて読みにくいため）
            weather_error = f"天気予報のサーバーにつながりませんでした（{type(error).__name__}）"
        except (ValueError, KeyError, IndexError, TypeError) as error:
            weather_error = f"天気予報の返事の形が想定と違いました（{error!r}）"

        # F3 メッセージを作る（天気が取れなかったときは、そのお知らせを作る）
        if weather_error:
            print(f"[{now_text()}] エラー: {weather_error}", file=sys.stderr)
            message = build_failure_message(weather_error)
        else:
            message = build_weather_message(weather)

        # F6 お試し表示
        if dry_run:
            show_preview(message)
            return

        # F4 Discord に送る
        send_to_discord(url, message)

        # F5 結果の表示
        if weather_error:
            print(f"天気を取得できなかったことを、Discord に送信しました（{now_text()}）")
            sys.exit(1)
        print(f"Discord に送信しました（{now_text()}）")

    except requests.Timeout:
        # 決めた秒数のうちに Discord から返事が無かった（F8）
        show_error_and_exit(
            f"Discord から {TIMEOUT_SECONDS} 秒たっても応答がありませんでした。時間をおいてやり直してください。\n"
            "（送信されている場合もあるので、Discord のチャンネルを確認してください）"
        )
    except requests.RequestException as error:
        # インターネットにつながらない など（F8）
        # 詳細は種類の名前だけにする。error の中身には Webhook URL（秘密）がそのまま入っていて、
        # 表示するとログファイルにも残ってしまうため
        show_error_and_exit(
            "Discord につながりませんでした。インターネット接続を確認してください。\n"
            f"詳細: {type(error).__name__}"
        )
    except KeyboardInterrupt:
        # Ctrl + C で途中でやめた場合
        print("\n中断しました。")
        sys.exit(1)


# このファイルを直接実行したときだけ main() を動かす
if __name__ == "__main__":
    main()
