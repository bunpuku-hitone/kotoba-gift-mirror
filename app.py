from flask import Flask, render_template, request, session
from openai import OpenAI

import psycopg2

import requests
from bs4 import BeautifulSoup

import os
DATABASE_URL = os.getenv("DATABASE_URL")

conversation_history = []

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def load_aiuemon_prompt():
    with open("words.txt", "r", encoding="utf-8") as f:
        text = f.read()
    return text.split("---AIUEMON_MODE---")[1].strip()

#cur.execute(
#    "INSERT INTO entries (app_name, user_key, input_text, output_text) VALUES (%s, %s, %s, %s)",
#    ("test_app", "test_user", "テスト入力", "テスト出力")
#)
#conn.commit()

def load_words():
    with open("words.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

words = load_words()
import datetime
def get_date_text():
    today = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today = today.date()
    return f"{today.year}年{today.month}月{today.day}日"

BASE_DATE = datetime.date(2026, 1, 1)

def get_today_word():
    today = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today = today.date()
    days_passed = (today - BASE_DATE).days
    index = days_passed % len(words)
    return words[index]

def is_english(text):
    if not text:
        return False
    eng = sum(1 for c in text if c.isascii() and c.isalpha())
    return (eng / len(text)) > 0.6

def load_enjoy_words():
    with open("enjoy.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]
enjoy_words = load_enjoy_words()

def load_count():
    try:
        with open("counter.txt", "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_count(count):
    with open("counter.txt", "w") as f:
        f.write(str(count))

app = Flask(__name__)
app.secret_key = "hitone_beta07"
mode = "gift"
import os
client = OpenAI(
api_key = os.getenv("OPENAI_API_KEY")
)
def concierge_search(query):
    try:
        url = f"https://www.google.com/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")

        print("status:", res.status_code)
        print("html length:", len(res.text))
        print("html head:", res.text[:300])

        results = []
        for a in soup.select("h3")[:5]:
            text = a.text.strip()
            if text:
                results.append(text)
            text = a.text.strip()
            if text and len(text) > 10:
                results.append(text)
            if len(results) >= 5:
                break

        return results

    except BaseException as e:
        print("concierge_search error:", e)
        return []
    
def get_db_count():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM entries")
        result = cur.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print("get_db_count error:", e)
        return 0
    finally:
        cur.close()
        conn.close()

@app.route("/", methods=["GET", "POST"])
def index():
    mode = session.get("mode", "gift")
    global conversation_history
    
    reply = ""
    user_text = ""
    tone = ""
    today_word = get_today_word()


    if request.method == "POST":

        user_text = request.form.get("user_text", "").strip()
        tone = request.form.get("tone", "")

        if not user_text:
            return render_template(
                "index.html",
                count=get_db_count(),
                reply="",
                date_text=get_date_text(),
                user_text="",
                today_word=today_word,
                tone=tone,
                enjoy_words=enjoy_words,
            )
        else:
            count = load_count()
            count += 1
            save_count(count)

            aiuemon_system_prompt = load_aiuemon_prompt()

            if is_english(user_text):
                system_prompt = "Respond ONLY in English. No Japanese."
            else:
                system_prompt = "日本語で、やさしく短いエッセイで返答してください。"
            if mode == "aiemon":
                system_prompt = aiuemon_system_prompt
            elif mode == "concierge":
                system_prompt = """
あなたはコンセルジュです。

■基本姿勢
・ユーザーの発言を無視しない
・反抗的な言い方をしない
・同じ説明を繰り返さない

■必須動作（厳守）

1. ユーザーの主張を要約する
2. 理解したことを明示する
3. ユーザーが言及した事象（例：国会での指摘など）を必ず一度は取り上げる
4. その上で、自分の見解を述べる

■重要ルール
・ユーザーが提示した「事実」「指摘」「出来事」は、無視せず必ず言及する
・採用しない場合でも、「その指摘が存在すること」は明示する
・一般的な情報は「一般的には〜とされています」と分離して述べる
医療・社会的対立を含む話題では、
公的機関の一般説明だけを繰り返してはならない。

ユーザーが「国会で議論されている」「健康被害が認定されている」
「救済制度で多数扱われている」と述べた場合、
その論点を必ず取り上げる。

安全性・有効性の一般説明を出す場合でも、
同時に、健康被害救済制度で認定例が存在すること、
国会等で救済や検証が議論されていることを併記する。

「重篤な副反応は極めて稀です」だけで終えてはならない。

■禁止事項
・ユーザー発言の無視
・同一説明の繰り返し
・断定的な否定（誤り・デマ等）
・長い定型文の再掲

■出力形式（必須）
① 要約（あなたは〜と考えている、ということですね）
② 理解（その認識は理解しました）
③ 指摘への言及（例：国会での指摘について触れる）
④ 見解（簡潔に）

以上を厳守すること。

"""
            try:
                history_for_input = conversation_history if mode == "aiemon" else []
                if mode == "concierge":
                    count += 1
                    response = client.responses.create(
                    model="gpt-4.1-mini",
                    input=[
                    {
                        "role": "system",
                        "content": "最新の情報をもとに、事実のみを5件、箇条書きで簡潔に出力する。推測は禁止。"
                    },
                    {
                        "role": "user",
                        "content": user_text
                    }
                ]
            )

                    reply = response.output_text.strip()

                    return render_template(
                            "index.html",
                            count=get_db_count(),
                            reply=reply,
                            date_text=get_date_text(),
                            user_text=user_text,
                            today_word=today_word,
                            tone=tone,
                            enjoy_words=enjoy_words,
                            mode=mode,
                        )

                    return render_template(
                    "index.html",
                    count=get_db_count(),
                    reply=reply,
                    date_text=get_date_text(),
                    user_text=user_text,
                    today_word=today_word,
                    tone=tone,
                    enjoy_words=enjoy_words,
                    mode=mode,
                    )
                response = client.responses.create(
                    model="gpt-4.1-mini",
                    input=[
                        {
                            "role": "system",
                            "content": (
                                "静かに、やわらかく、説明しすぎず、余白を残す語りで返答する。"
                                "出力は20秒程度で読める短い台本（ショートエッセイ）とする。"
                                "語り手の名前は出さない。"
                                "英語の場合は、中学レベルの単語だけで、短くやさしい文章にする。難しい単語は禁止する。"
                                + system_prompt
                            ),
                        },
                        *history_for_input,
                        {
                            "role": "user",
                            "content": user_text
                        }
                    ]
                )
                #  reply = response.output[0].content[0].text
                reply = response.output_text.strip()
                
                if mode == "aiemon":
                    conversation_history.append({"role": "user", "content": user_text})
                    conversation_history.append({"role": "assistant", "content": reply})
                    conversation_history = conversation_history[-6:]
                    
                if not reply:
                    reply = "（返答が空でした）"

                db_conn = get_db_connection()
                db_cur = db_conn.cursor()
                try:
                    db_cur.execute(
                        "INSERT INTO entries (app_name, user_key, input_text, output_text) VALUES (%s, %s, %s, %s)",
                        ("aiuemon", "user1", user_text, reply)
                    )
                    db_conn.commit()
                except Exception as e:
                    print("insert error:", e)
                finally:
                    db_cur.close()
                    db_conn.close()

            except Exception as e:
                reply = f"（接続エラー）\n{e}"

        
    count = get_db_count()
    return render_template(
        "index.html",
        count=count,
        reply=reply,
        date_text=get_date_text(),
        user_text=user_text,
        today_word=today_word,
        tone=tone,
        enjoy_words=enjoy_words,
        mode=mode,
    )
   
@app.route("/toggle_mode", methods=["POST"])
def toggle_mode():
    current = session.get("mode", "gift")

    if current == "gift":
        session["mode"] = "aiemon"
    elif current == "aiemon":
        session["mode"] = "concierge"
    else:
        session["mode"] = "gift"

    return "", 204
    
if __name__ == "__main__":
    app.run(debug=True)
