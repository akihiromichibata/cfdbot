
# app.py（全文コピペ用）
import json, logging, requests
from datetime import datetime
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import yfinance as yf
import pandas as pd

# ★ ここがポイント：CORS を有効化
from flask_cors import CORS

# ===== Flask 初期化 =====
app = Flask(__name__)

# Netlify の公開 URL を許可（あなたの URL に置き換えてください）
# 例: "https://fabulous-florentine-7a9f86.netlify.app"
ALLOWED_ORIGIN = "https://fabulous-florentine-7a9f86.netlify.app"
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGIN}})

# ===== 設定読み込み =====
CFG_PATH = 'config.json'
logging.basicConfig(filename='logs/app.log', level=logging.INFO)

def load_cfg():
    with open(CFG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_cfg(cfg):
    with open(CFG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ===== 指標計算 =====
from indicators import bollinger_bands, rsi, volume_spike

def fetch_hist(sym, period='3mo', interval='1h'):
    tk = yf.Ticker(sym)
    return tk.history(period=period, interval=interval)

def should_alert(sym_name, df: pd.DataFrame, cfg):
    close = df['Close']
    vol = df['Volume'] if 'Volume' in df.columns else pd.Series([0]*len(df))
    ma, upper, lower = bollinger_bands(close, cfg['rules']['bb_period'], cfg['rules']['bb_sigma'])
    rsi_vals = rsi(close, cfg['rules']['rsi_period'])

    last = len(close) - 1
    last_close = close.iloc[last]
    last_upper = upper.iloc[last]
    last_lower = lower.iloc[last]
    last_rsi = rsi_vals.iloc[last] if not pd.isna(rsi_vals.iloc[last]) else None
    vol_spike_flag = volume_spike(vol, cfg['rules']['volume_ma_period'], cfg['rules']['volume_spike_mult'])

    msg = None
    # 指数：-2σでロング、+2σでショート候補
    if sym_name in ('nikkei225','nasdaq100'):
        if cfg['entry_conditions']['index_buy_on_minus2sigma'] and last_close <= last_lower and vol_spike_flag:
            msg = f"[{sym_name}] -2σタッチ＋出来高増→短期ロング候補"
        elif cfg['entry_conditions']['index_sell_on_plus2sigma'] and last_close >= last_upper and vol_spike_flag:
            msg = f"[{sym_name}] +2σタッチ＋出来高増→短期ショート候補"
    else:
        # コモディティ：20MA反発＋RSI>=閾値＋出来高増
        last_ma = ma.iloc[last]
        if cfg['entry_conditions']['commodity_buy_on_ma_bounce']:
            if last_ma and last_close >= last_ma and last_rsi and last_rsi >= cfg['rules']['rsi_buy_threshold'] and vol_spike_flag:
                msg = f"[{sym_name}] 20MA反発＋RSI{int(last_rsi)}→短期ロング候補"

    detail = {
        "last_close": float(last_close),
        "upper": float(last_upper) if last_upper else None,
        "lower": float(last_lower) if last_lower else None,
        "rsi": float(last_rsi) if last_rsi else None,
        "vol_spike": bool(vol_spike_flag)
    }
    return msg, detail

def push_onesignal(app_id, api_key, title, body, segment="all"):
    url = "https://onesignal.com/api/v1/notifications"
    payload = {
        "app_id": app_id,
        "included_segments": [segment],
        "headings": {"en": title, "ja": title},
        "contents": {"en": body, "ja": body}
    }
    headers = {"Authorization": f"Basic {api_key}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    logging.info(f"push status {r.status_code}: {r.text[:200]}")

def job():
    cfg = load_cfg()
    syms = cfg['symbols']
    for name, ticker in syms.items():
        try:
            df = fetch_hist(ticker)
            if df is None or df.empty:
                continue
            msg, detail = should_alert(name, df, cfg)
            if msg:
                title = "エントリー候補（CFD）"
                body = f"{msg}\nprice={detail['last_close']}, rsi={detail['rsi']}, volSpike={detail['vol_spike']}"
                push_onesignal(cfg['notifications']['onesignal_app_id'],
                               cfg['notifications']['onesignal_api_key'],
                               title, body, cfg['notifications']['segment'])
                logging.info(f"ALERT: {msg} {detail}")
        except Exception as e:
            logging.exception(f"error {name}: {e}")

# ===== API エンドポイント =====
@app.route("/config", methods=["GET","POST"])
def config_endpoint():
    if request.method == "GET":
        return jsonify(load_cfg())
    data = request.get_json(force=True)
    save_cfg(data)
    return jsonify({"ok": True})

# 任意：ヘルスチェック（Render側で設定するなら）
@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "ts": datetime.utcnow().isoformat()})

# ===== 起動 =====
if __name__ == "__main__":
    sched = BackgroundScheduler()
    sched.add_job(job, 'interval', minutes=load_cfg()['scheduler']['interval_minutes'])
    sched.start()
    # 0.0.0.0 で起動（Render から外部アクセス可能）
    app.run(host="0.0.0.0", port=5000)

