import requests
import pandas as pd
import time
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import streamlit as st
import pydeck as pdk
from urllib.request import urlopen #jsonファイル形式で取得するアニメーションファイルをアプリに表示する
from streamlit_option_menu import option_menu

# //////////////////  関数

# 指定されたスプレッドシートとシート名からDataFrameを作成する関数
def get_dataframe_from_sheet(spreadsheet, sheet_name):
    worksheet = spreadsheet.worksheet(sheet_name)
    data = worksheet.get_all_values()
    return pd.DataFrame(data[1:], columns=data[0])


# 新規登録フォームの内容をSpに送る
def form_upload(email, password, first_name, last_name, tel, spreadsheet):
    keys = email + password
    new_data = {
        "メールアドレス": email,
        "パスワード": password,
        "氏": first_name,
        "名": last_name,
        "TEL": tel,
        "keys": keys,
    }
    try:
        worksheet = spreadsheet.worksheet('login')
        last_row = len(worksheet.get_all_values()) # スプレッドシートの最後の行を取得
        worksheet.append_row(list(new_data.values())) # 新しいデータを追加
        st.success("フォームが送信されました")
        initialize_session_state(variables) #正常に送信された場合に入力されたフォームの内容を削除する
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")

# 新規登録フォームの内容を初期化する関数
def initialize_session_state(variables):
    for var in variables:
        st.session_state[var] = st.session_state.get(var, '')

# //////////////////  データベース系

# StreamlitのSecretsから情報を取得
gcp_service_account_info = st.secrets["gcp_service_account"]

# GCPサービスアカウントで認証
credentials = Credentials.from_service_account_info(gcp_service_account_info, 
                                                    scopes=['https://www.googleapis.com/auth/spreadsheets',
                                                            'https://www.googleapis.com/auth/drive'])
gc = gspread.authorize(credentials)

# スプレッドシートのIDを指定して開く
spreadsheet = gc.open_by_key("1R191trRqSI7ukjSUv_ZtWCmt57ve-EntXsLS6161SUM")

# シートのデータをDataFrameに変換
df_login = get_dataframe_from_sheet(spreadsheet, 'login')


# //////////////////  streamlitの設定選択された項目に基づいて表示を切り替え

# セッション状態の初期化 このコードはログインアウトによって分岐を行うコード群の一番上にしないと正しく初期化されない
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# サイドバーにオプションメニューを追加
with st.sidebar:
    if st.session_state['logged_in']:
        # ログイン中のメニュー
        menu_options = ["物件検索", "ログイン・マイページ"]
        menu_icons = ["house", "person"]
    else:
        # ログインしていない時のメニュー
        menu_options = ["物件検索", "ログイン・マイページ", "新規登録"]
        menu_icons = ["house", "person", "info-circle"]

    selected = option_menu(
        menu_title="Main Menu",
        options=menu_options,
        icons=menu_icons,
        default_index=0,
    )

    # ユーザー情報の表示
    if st.session_state['logged_in']:
        user_row = df_login[df_login['keys'] == st.session_state['email'] + st.session_state['password']]
        user_info = user_row.iloc[0]
        st.write(f"メールアドレス: {user_info['メールアドレス']}")
        st.write(f"氏: {user_info['氏']}")
        st.write(f"名: {user_info['名']}")
        st.write(f"TEL: {user_info['TEL']}")
        if st.button('ログアウト', key='sidebar_logout'):
            st.session_state['logged_in'] = False
            st.session_state['email'] = ''
            st.session_state['password'] = ''
            st.experimental_rerun()


# //////////////////  物件検索のメニュー

if selected == "物件検索":
    st.write("物件検索用のページ")

    # ダミーの物件データ
    data_line = {
        "物件名": ["物件A", "物件B", "物件C"],
        "URL": ["https://suumo.jp/chintai/jnc_000079607104/", "https://suumo.jp/chintai/jnc_000080672100/", "https://suumo.jp/chintai/jnc_000087709468/"]
    }
    df_line = pd.DataFrame(data_line)

    # チェックボックスの列を追加
    if 'select' not in st.session_state:
        st.session_state['select'] = [False] * len(df_line)

    # Streamlitのテーブルで表示
    for index, row in df_line.iterrows():
        st.session_state['select'][index] = st.checkbox(row["物件名"], key=f"checkbox_{index}")

    # 選択されたURLを取得
    df_line['Select'] = st.session_state['select']
    selected_urls = df_line[df_line['Select']]['URL'].tolist()

    # HTMLでLINE共有ボタンを作成する関数
    def create_line_button(line_url):
        return f'''
            <div class="line-it-button" data-lang="ja" data-type="share-a" data-env="REAL" data-url="{line_url}" data-color="default" data-size="large" data-count="false" data-ver="3"></div>
            <script src="https://www.line-website.com/social-plugins/js/thirdparty/loader.min.js" async="async" defer="defer"></script>
        '''

    # リセットボタン
    if st.button('リセット'):
        st.session_state['select'] = [False] * len(df_line)
        selected_urls = []

    # 選択されたURLがあれば、LINE共有ボタンを表示
    if selected_urls:
        # 最初の選択されたURLに対してLINE共有ボタンを生成
        line_button_html = create_line_button(selected_urls[0])
        st.markdown(line_button_html, unsafe_allow_html=True)



# //////////////////  ログイン・マイページの項目

if selected == "ログイン・マイページ":
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if st.session_state['logged_in']:
        st.title('My Page・ログイン中')
        if st.button('ログアウト'):
            st.session_state['logged_in'] = False
            st.session_state['email'] = ''
            st.session_state['password'] = ''
            st.experimental_rerun()
    else:
        st.title('My Page')
        with st.form(key='login_form'):
            email = st.text_input("メールアドレス", value=st.session_state['email'])
            password = st.text_input("パスワード", type='password', value=st.session_state['password'])
            submit_button = st.form_submit_button("ログイン")

            if submit_button:
                my_key = email + password
                user_row = df_login[df_login['keys'] == my_key]

                if not user_row.empty:
                    st.session_state['logged_in'] = True
                    st.session_state['email'] = email
                    st.session_state['password'] = password
                    st.experimental_rerun()
                else:
                    st.write("メールアドレスかパスワードが間違っています")

    if st.session_state['logged_in']:
        user_row = df_login[df_login['keys'] == st.session_state['email'] + st.session_state['password']]
        user_info = user_row.iloc[0]
        st.write(f"メールアドレス: {user_info['メールアドレス']}")
        st.write(f"氏: {user_info['氏']}")
        st.write(f"名: {user_info['名']}")
        st.write(f"TEL: {user_info['TEL']}")


# ////////////////// 新規登録ページの項目

# 初期化する変数のリスト
variables = ['email', 'password', 'first_name', 'last_name', 'tel', 'keys']

# セッション状態の初期化を行う関数を呼び出し
initialize_session_state(variables)

# 入力フォーム
if selected == "新規登録":
    with st.form(key='new_user_form'):
        email = st.text_input("メールアドレス", value=st.session_state['email'])
        password = st.text_input("パスワード", type='password', value=st.session_state['password'])
        first_name = st.text_input("氏", value=st.session_state['first_name'])
        last_name = st.text_input("名", value=st.session_state['last_name'])
        tel = st.text_input("TEL", value=st.session_state['tel'])
        submit_button = st.form_submit_button("送信")

        if submit_button:
            if email not in df_login['メールアドレス'].values:
                form_upload(email, password, first_name, last_name, tel, spreadsheet)
            else:
                st.write("すでにそのメールアドレスは登録されています")

# ////////////////// EOE
