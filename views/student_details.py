import streamlit as st
import pandas as pd# 必須！データフレーム（表）を扱うため
import altair as alt# 必須！グラフを描画するため
import datetime# 必須！日付を扱うため

# 📊 スプレッドシート関連は g_sheets から
from utils.g_sheets import (
    get_all_student_names,
    get_student_info,
    update_student_info,
    save_test_score,
    load_test_scores
)

# 🧮 計算ロジックは calc_logic から（これを追加！）
from utils.calc_logic import (
    calculate_ability_rank,
    calculate_motivation_rank
)

def render_student_details_page():
    st.header("👤 生徒詳細 ＆ テスト成績・模試記録")
    student_names = get_all_student_names()
    if not student_names: 
        st.warning("まだ生徒が登録されていません。")
        return

    selected_student = st.selectbox("👤 対象の生徒を選択してください", ["-- 選択 --"] + student_names)

    if selected_student == "-- 選択 --":
        st.info("👆 生徒を選択すると、詳細情報（カルテ）やテスト記録が表示されます。")
        return

    tab_info, tab_input, tab_view = st.tabs(["👤 基本情報・カルテ", "✍️ テスト成績を入力", "📈 テスト成績推移を見る"])

    with tab_info:
        info = get_student_info(selected_student)
        
        df_test = load_test_scores()
        df_student_tests = pd.DataFrame()
        if not df_test.empty:
            df_student_tests = df_test[df_test['生徒名'] == selected_student]

        col_prof, col_graph = st.columns([1, 1])
        
        with col_prof:
            st.markdown(f"### 📝 {selected_student} さんのプロフィール")
            
            st.markdown(f"**🎓 学年**: {info.get('学年', '未設定')}")
            st.markdown(f"**🏫 学校名**: {info.get('学校名', '未設定')}")
            st.markdown(f"**🎯 志望校・目的**: {info.get('志望校・目的', '未設定')}")
            st.markdown(f"**📚 受講科目**: {info.get('受講科目', '未設定')}")
            
            if st.session_state['role'] == 'admin':
                with st.expander("✏️ 基本情報を編集する (教室長のみ)"):
                    with st.form("edit_student_info_form"):
                        new_grade = st.text_input("学年 (例: 中2)", value=info.get('学年', ''))
                        new_school = st.text_input("学校名", value=info.get('学校名', ''))
                        new_target = st.text_input("志望校・通塾目的", value=info.get('志望校・目的', ''))
                        new_subjects = st.text_input("受講科目 (例: 英語, 数学)", value=info.get('受講科目', ''))
                        
                        if st.form_submit_button("💾 基本情報を保存", type="primary"):
                            update_student_info(selected_student, new_grade, new_school, new_target, new_subjects, info.get('能力', 3), info.get('やる気', 3), info.get('内申点', 3), info.get('最新偏差値', 50), info.get('宿題履行率', 100))
                            st.success(f"基本情報を保存しました！")
                            st.rerun()
            else:
                st.info("※プロフィールの編集は教室長のみ可能です。")

        with col_graph:
            st.markdown("### 🧭 科目別：能力 × やる気 マトリクス")
            selected_subject = st.selectbox("📊 分析する科目を選択", ["英語", "数学", "国語", "理科", "社会"])
            
            latest_dev = 50.0
            latest_naishin = 3
            
            if not df_student_tests.empty:
                df_moshi = df_student_tests[df_student_tests['テスト種別'] == "外部模試"]
                if not df_moshi.empty and f"{selected_subject} 偏差値" in df_moshi.columns:
                    latest_dev_val = df_moshi.iloc[-1][f"{selected_subject} 偏差値"]
                    if pd.notna(latest_dev_val) and str(latest_dev_val).replace('.','',1).isdigit():
                        latest_dev = float(latest_dev_val)
                
                df_naishin = df_student_tests[df_student_tests['テスト種別'] == "通知表（内申点）"]
                if not df_naishin.empty and f"{selected_subject} 内申" in df_naishin.columns:
                    latest_naishin_val = df_naishin.iloc[-1][f"{selected_subject} 内申"]
                    if pd.notna(latest_naishin_val) and str(latest_naishin_val).isdigit():
                        latest_naishin = int(latest_naishin_val)

            st.caption(f"💡 【自動参照】最新偏差値: **{latest_dev}** / 最新内申点: **{latest_naishin}**")
            
            hw_rate = st.slider(f"✍️ {selected_subject}の宿題履行率 (直近 %)", 0, 100, 100, key=f"hw_{selected_subject}")
            
            ability = calculate_ability_rank(latest_naishin, latest_dev)
            motivation = calculate_motivation_rank(hw_rate, 100) 
            
            df_coord = pd.DataFrame({
                "生徒": [selected_student],
                "能力 (X)": [ability],
                "やる気 (Y)": [motivation]
            })
            
            chart = alt.Chart(df_coord).mark_circle(size=800, color="#FF4B4B").encode(
                x=alt.X('能力 (X)', scale=alt.Scale(domain=[1, 5]), title="🧠 能力 (1〜5)"),
                y=alt.Y('やる気 (Y)', scale=alt.Scale(domain=[1, 5]), title="🔥 やる気 (1〜5)"),
                tooltip=['生徒', '能力 (X)', 'やる気 (Y)']
            ).properties(height=300)
            
            rule_x = alt.Chart(pd.DataFrame({'x': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(x='x')
            rule_y = alt.Chart(pd.DataFrame({'y': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(y='y')
            
            st.altair_chart(chart + rule_x + rule_y, use_container_width=True)

    with tab_input:
        with st.container(border=True):
            st.write(f"**{selected_student}** さんのテスト結果・内申点を入力します。")
            c1, c2 = st.columns(2)
            date = c1.date_input("実施日", datetime.date.today())
            test_type = c2.selectbox("📝 テスト種別", ["定期テスト(中間など)", "期末テスト", "外部模試", "通知表（内申点）", "その他"])

            if test_type == "通知表（内申点）":
                st.info("各科目の内申点（1〜5）を入力してください。※ここで入力した値がカルテのマトリクスに自動反映されます。")
                n1, n2, n3, n4, n5 = st.columns(5)
                n_eng = n1.number_input("英語 内申", 1, 5, value=None)
                n_math = n2.number_input("数学 内申", 1, 5, value=None)
                n_jpn = n3.number_input("国語 内申", 1, 5, value=None)
                n_sci = n4.number_input("理科 内申", 1, 5, value=None)
                n_soc = n5.number_input("社会 内申", 1, 5, value=None)
                
                st.divider()
                n6, n7, n8, n9 = st.columns(4)
                n_pe = n6.number_input("保体 内申", 1, 5, value=None)
                n_tech = n7.number_input("技術 内申", 1, 5, value=None)
                n_home = n8.number_input("家庭 内申", 1, 5, value=None)
                n_mus = n9.number_input("音楽 内申", 1, 5, value=None)
                
                if st.button("💾 内申点を登録する", type="primary"):
                    save_test_score(date, selected_student, test_type, n_eng, n_math, n_jpn, n_sci, n_soc, None, None, None, None, None, None, None, n_pe, n_tech, n_home, n_mus, is_naishin=True)
                    st.success("内申点を登録しました！カルテ画面のマトリクスに反映されます。")

            else:
                with st.expander("⚙️ 各教科の満点設定（基本100点/副教科50点）"):
                    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                    m_eng = mc1.number_input("英 満点", 0, 100, 100)
                    m_math = mc2.number_input("数 満点", 0, 100, 100)
                    m_jpn = mc3.number_input("国語 満点", 0, 100, 100)
                    m_sci = mc4.number_input("理科 満点", 0, 100, 100)
                    m_soc = mc5.number_input("社会 満点", 0, 100, 100)
                    
                    m_pe, m_tech, m_home, m_mus = 50, 50, 50, 50
                    if test_type == "期末テスト":
                        mc6, mc7, mc8, mc9 = st.columns(4)
                        m_pe = mc6.number_input("保体 満点", 0, 100, 50)
                        m_tech = mc7.number_input("技 満点", 0, 100, 50)
                        m_home = mc8.number_input("家 満点", 0, 100, 50)
                        m_mus = mc9.number_input("音 満点", 0, 100, 50)

                sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                eng = sc1.number_input(f"英語 (/{m_eng})", 0, m_eng, value=None)
                math_score = sc2.number_input(f"数学 (/{m_math})", 0, m_math, value=None)
                jpn = sc3.number_input(f"国語 (/{m_jpn})", 0, m_jpn, value=None)
                sci = sc4.number_input(f"理科 (/{m_sci})", 0, m_sci, value=None)
                soc = sc5.number_input(f"社会 (/{m_soc})", 0, m_soc, value=None)

                dev_eng, dev_math, dev_jpn, dev_sci, dev_soc, dev_3, dev_5 = None, None, None, None, None, None, None
                if test_type == "外部模試":
                    st.divider()
                    st.markdown("##### 📊 偏差値の入力")
                    d1, d2, d3, d4, d5 = st.columns(5)
                    dev_eng = d1.number_input("英語 偏差値", 0.0, 90.0, value=None, step=0.1)
                    dev_math = d2.number_input("数学 偏差値", 0.0, 90.0, value=None, step=0.1)
                    dev_jpn = d3.number_input("国語 偏差値", 0.0, 90.0, value=None, step=0.1)
                    dev_sci = d4.number_input("理科 偏差値", 0.0, 90.0, value=None, step=0.1)
                    dev_soc = d5.number_input("社会 偏差値", 0.0, 90.0, value=None, step=0.1)

                pe, tech, home, mus = None, None, None, None
                if test_type == "期末テスト":
                    st.divider()
                    sc6, sc7, sc8, sc9 = st.columns(4)
                    pe = sc6.number_input(f"保健体育 (/{m_pe})", 0, m_pe, value=None)
                    tech = sc7.number_input(f"技術 (/{m_tech})", 0, m_tech, value=None)
                    home = sc8.number_input(f"家庭科 (/{m_home})", 0, m_home, value=None)
                    mus = sc9.number_input(f"音楽 (/{m_mus})", 0, m_mus, value=None)

                if st.button("💾 この成績を登録する", type="primary"):
                    save_test_score(date, selected_student, test_type, eng, math_score, jpn, sci, soc, dev_eng, dev_math, dev_jpn, dev_sci, dev_soc, dev_3, dev_5, pe, tech, home, mus, is_naishin=False)
                    st.success("成績を登録しました！")

    with tab_view:
        if not df_student_tests.empty:
            st.subheader(f"📈 {selected_student} さんの総合点 推移")
            if '総合' in df_student_tests.columns:
                st.line_chart(df_student_tests.set_index("テスト種別")["総合"])
            elif '5科総合' in df_student_tests.columns:
                st.line_chart(df_student_tests.set_index("テスト種別")["5科総合"])
            
            st.dataframe(df_student_tests, hide_index=True, use_container_width=True)
        else:
            st.info("まだ成績データがありません。")