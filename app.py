import streamlit as st
import pandas as pd
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import time
from io import BytesIO

# 페이지 설정
st.set_page_config(page_title="Uphone Translator V5", page_icon="⚡", layout="wide")

st.title("⚡ Uphone AI Translator V5")
st.markdown("""
**Google Sheets + 파일 업로드 + 실시간 번역 모두 지원**
""")

# Google Sheets 인증 함수
def get_google_sheets_client():
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        if 'gcp_service_account' in st.secrets:
            credentials = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=scope
            )
        else:
            credentials = Credentials.from_service_account_file(
                'service-account-key.json',
                scopes=scope
            )
        
        return gspread.authorize(credentials)
    except Exception as e:
        return None

# ⭐ 사이드바에서 API Key 입력받기
with st.sidebar:
    st.header("🔑 API Key 설정")
    api_key = st.text_input(
        "Gemini API Key:",
        type="password",
        placeholder="AIzaSy...",
        help="https://aistudio.google.com/apikey"
    )
    
    if not api_key:
        st.warning("⚠️ API Key를 입력해주세요!")
        st.info("👉 [API Key 발급받기](https://aistudio.google.com/apikey)")
        st.stop()
    
    st.divider()
    st.header("📂 Translation Settings")
    
    category = st.selectbox(
        "Category",
        ["Daily Life", "Business", "Travel", "News", "Academic", "Entertainment", "Health", "Technology"]
    )
    difficulty = st.selectbox(
        "Difficulty",
        ["0-Level", "Beginner", "Intermediate", "Advanced"]
    )
    
    st.divider()
    st.header("📊 Excel Columns")
    col_source = st.text_input("Source Column (English)", value="D")
    col_target = st.text_input("Target Column (Korean)", value="E")

# 프롬프트 로직
ground_rules = """
# 🛡️ Absolute Ground Rules (Non-negotiable)
1. **Zero 'You' Policy:** NEVER translate 'You' as '당신'. Omit subject or use context-appropriate titles.
2. **Anti-Passive Voice:** Use Active Voice. (X) "~에 의해 ~되다" -> (O) "강사가 취소했다"
3. **Subject-Drop Freedom:** Omit unnecessary subjects (I/We) if context is clear.
4. **Word Order Liberation:** Don't mimic English order. Rearrange for natural Korean flow.
5. **Sentence Fusion:** Combine/split sentences for better rhythm.
6. **Natural Predicate Choice:** Don't translate verbs 1:1. Use natural Korean predicates.
7. **Connector Naturalization:** Avoid mechanical "And, But". Use natural endings (~하는데).
8. **Tense Flexibility:** Don't force 'Have p.p'. Use context-based tense.
9. **Pronoun Minimization:** Avoid repetitive He/She/It.
10. **Formality Calibration:** Follow the Tone defined in Category settings.
11. **No Hallucination:** Fact must match 100%. No adding/omitting info.
12. **Bold/Tag Preservation:** Preserve markdown bold (`**`) and variables (`{name}`) exactly.
"""

common_errors = """
# ⚠️ Common Translation Errors to AVOID
1. **Spacing:** 문장 끝 다음 띄어쓰기, 쉼표 뒤 띄어쓰기, 조사 앞 붙여쓰기
2. **Quotation:** 인용문 정확히 처리, 원문 없으면 따옴표 추가 금지
3. **Parentheses:** 괄호 최소화 (유명 인명에 영어 표기 불필요)
4. **Symbols:** 대시(—), 슬래시(/) 남용 금지
5. **Entity Names:** 동일 회사/기관 표기 통일
6. **Balance:** 자연스러운 의역 우선, 핵심 의미 누락 금지
7. **Tone:** 한 문서 내 "-요"/"-습니다" 혼용 금지
8. **Numbers:** 만/억 단위 사용, 쉼표 위치 확인
9. **Connectors:** 원문 없는 "하지만", "특히" 추가 금지
10. **Terms:** 전문 용어는 업계 표준 번역 사용
"""

category_guidelines = {
    "Daily Life": "기본 말투: polite (~요), 자연스러운 구어체 우선",
    "Business": "기본 말투: polite~formal, 정중하고 전문적인 톤",
    "Travel": "기본 말투: polite, 실용적이고 명확하게",
    "News": "기본 말투: formal (-다/-습니다), 객관적이고 간결한 서술",
    "Academic": "기본 말투: polite~formal, 논리적이고 명확한 표현",
    "Entertainment": "기본 말투: casual~polite, 생동감 있고 재미있게",
    "Health": "기본 말투: polite~formal, 정확하고 신중하게",
    "Technology": "기본 말투: polite~formal, 전문적이되 이해하기 쉽게"
}

difficulty_guidelines = {
    "0-Level": "가장 기본적이고 쉬운 단어만, 매우 짧고 단순한 문장",
    "Beginner": "일상적이고 기본적인 어휘, 짧고 단순한 문장 구조",
    "Intermediate": "자연스러운 관용 표현 활용, 뉘앙스 살리기",
    "Advanced": "원어민 수준의 자연스러움, 문화적 뉘앙스까지 반영"
}

master_prompt = f"""
You are Uphone's Localization Specialist.
Translate the text from **English** to **Korean**.

{ground_rules}

{common_errors}

[Category: {category}] {category_guidelines[category]}
[Difficulty: {difficulty}] {difficulty_guidelines[difficulty]}

[Technical Instruction]
- Only output the translated Korean text.
- Do not add explanations.
"""

# 번역 함수
def translate_text(text):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            f"{master_prompt}\n\n[Source Text]: {text}\n[Translation]:"
        )
        return response.text.strip()
    except Exception as e:
        return f"Error: {e}"

# 컬럼 인덱스 변환
def col_letter_to_index(letter):
    return ord(letter.upper()) - 65

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs([
    "💬 실시간 문장 번역",
    "🔗 Google Sheets 번역",
    "⚡ 파일 업로드 번역",
    "📝 프롬프트 생성"
])

# [Tab 1] 실시간 문장 번역
with tab1:
    st.subheader("💬 실시간 문장 번역")
    st.info(f"현재 설정: {category} / {difficulty}")
    
    input_text = st.text_area(
        "영어 문장을 입력하세요:",
        height=150,
        placeholder="예: Hello, how are you today?"
    )
    
    if st.button("🚀 번역하기", type="primary", key="translate_text"):
        if not input_text.strip():
            st.warning("번역할 문장을 입력해주세요!")
        else:
            with st.spinner("번역 중..."):
                translated_text = translate_text(input_text)
            
            if "Error:" not in translated_text:
                st.success("✅ 번역 완료!")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**원문:**")
                    st.info(input_text)
                with col2:
                    st.markdown("**번역:**")
                    st.success(translated_text)
                st.code(translated_text, language="text")
            else:
                st.error(translated_text)

# [Tab 2] Google Sheets 번역
with tab2:
    st.subheader("🔗 Google Sheets 링크 번역")
    st.info(f"현재 설정: {category} / {difficulty}")
    
    st.markdown("""
    **사용 방법:**
    1. Google Sheets 링크를 붙여넣으세요
    2. 시트를 **'누구나 링크가 있는 사용자'에게 공개**로 설정하세요
    3. 번역 시작 버튼을 누르세요
    """)
    
    sheets_url = st.text_input(
        "📎 Google Sheets URL:",
        placeholder="https://docs.google.com/spreadsheets/d/1ABC..."
    )
    
    sheet_name = st.text_input(
        "📄 시트 이름 (선택사항):",
        placeholder="Sheet1",
        help="비워두면 첫 번째 시트를 사용합니다"
    )
    
    if st.button("🚀 번역 시작", type="primary", key="translate_sheets"):
        if not sheets_url:
            st.warning("Google Sheets URL을 입력해주세요!")
        else:
            try:
                with st.spinner("Google Sheets 연결 중..."):
                    if '/d/' in sheets_url:
                        sheet_id = sheets_url.split('/d/')[1].split('/')[0]
                    else:
                        st.error("올바른 Google Sheets URL이 아닙니다")
                        st.stop()
                    
                    gc = get_google_sheets_client()
                    if not gc:
                        st.warning("⚠️ Google Sheets API 인증이 설정되지 않았습니다. 공개 시트만 읽을 수 있습니다.")
                        try:
                            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                            df = pd.read_csv(csv_url)
                            can_write = False
                        except Exception as e:
                            st.error(f"시트를 읽을 수 없습니다: {e}")
                            st.info("시트가 '누구나 링크가 있는 사용자'에게 공개되어 있는지 확인하세요")
                            st.stop()
                    else:
                        spreadsheet = gc.open_by_key(sheet_id)
                        if sheet_name:
                            worksheet = spreadsheet.worksheet(sheet_name)
                        else:
                            worksheet = spreadsheet.sheet1
                        
                        data = worksheet.get_all_values()
                        df = pd.DataFrame(data[1:], columns=data[0])
                        can_write = True
                    
                    st.success(f"✅ 시트 로드 완료! (총 {len(df)}행)")
                    st.dataframe(df.head(), use_container_width=True)
                
                with st.spinner("번역 중..."):
                    idx_src = col_letter_to_index(col_source)
                    idx_tgt = col_letter_to_index(col_target)
                    
                    if len(df.columns) <= idx_tgt:
                        df[f'Column_{col_target}'] = ""
                    
                    progress_bar = st.progress(0)
                    total_rows = len(df)
                    preview_container = st.empty()
                    
                    translations = []
                    
                    for index, row in df.iterrows():
                        if idx_src < len(row):
                            source_text = str(row.iloc[idx_src]) if pd.notna(row.iloc[idx_src]) else ""
                        else:
                            source_text = ""
                        
                        if source_text.strip():
                            translated_text = translate_text(source_text)
                            translations.append(translated_text)
                        else:
                            translations.append("")
                        
                        if idx_tgt < len(df.columns):
                            df.iat[index, idx_tgt] = translated_text
                        
                        progress = (index + 1) / total_rows
                        progress_bar.progress(progress)
                        preview_container.text(f"Processing row {index+1}/{total_rows}")
                        
                        time.sleep(0.5)
                    
                    st.success("🎉 번역 완료!")
                    
                    if can_write and gc:
                        try:
                            with st.spinner("Google Sheets에 저장 중..."):
                                target_col_num = idx_tgt + 1
                                start_row = 2
                                
                                cell_list = []
                                for i, translation in enumerate(translations):
                                    cell_list.append(gspread.Cell(
                                        row=start_row + i,
                                        col=target_col_num,
                                        value=translation
                                    ))
                                
                                worksheet.update_cells(cell_list)
                            
                            st.success("✅ Google Sheets 업데이트 완료!")
                            st.markdown(f"[📊 결과 확인하기]({sheets_url})")
                        except Exception as e:
                            st.warning(f"Google Sheets 저장 실패: {e}")
                            st.info("엑셀 파일로 다운로드하세요")
                    
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='Sheet1')
                    
                    st.download_button(
                        label="📥 번역 결과 다운로드 (Excel)",
                        data=output.getvalue(),
                        file_name="translated_sheets_result.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
                st.info("""
                **문제 해결:**
                1. Google Sheets가 '누구나 링크가 있는 사용자'에게 공개되어 있는지 확인
                2. URL이 정확한지 확인
                3. 시트 이름이 정확한지 확인
                """)

# [Tab 3] 파일 업로드 번역
with tab3:
    st.subheader("⚡ 엑셀/CSV 파일 자동 번역")
    st.info(f"현재 설정: {category} / {difficulty}")
    
    uploaded_file = st.file_uploader("엑셀 또는 CSV 파일을 업로드하세요", type=['xlsx', 'csv'])
    
    if uploaded_file:
        st.success("✅ 파일이 업로드되었습니다!")
        
        if st.button("🚀 번역 시작", type="primary", key="translate_file"):
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                idx_src = col_letter_to_index(col_source)
                idx_tgt = col_letter_to_index(col_target)
                
                if len(df.columns) <= idx_tgt:
                    df[f'Column {col_target}'] = ""
                    idx_tgt = len(df.columns) - 1
                
                progress_bar = st.progress(0)
                total_rows = len(df)
                preview_container = st.empty()
                
                for index, row in df.iterrows():
                    source_text = str(row.iloc[idx_src]) if pd.notna(row.iloc[idx_src]) else ""
                    
                    if source_text.strip():
                        translated_text = translate_text(source_text)
                    else:
                        translated_text = ""
                    
                    df.iat[index, idx_tgt] = translated_text
                    
                    progress = (index + 1) / total_rows
                    progress_bar.progress(progress)
                    preview_container.text(f"Processing row {index+1}/{total_rows}: {source_text[:30]}... → {translated_text[:30]}...")
                    
                    time.sleep(0.5)
                
                st.success("🎉 번역 완료! 아래 버튼을 눌러 다운로드하세요.")
                
                output = BytesIO()
                if uploaded_file.name.endswith('.csv'):
                    df.to_csv(output, index=False, encoding='utf-8-sig')
                    file_name = "translated_result.csv"
                else:
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='Sheet1')
                    file_name = "translated_result.xlsx"
                
                st.download_button(
                    label="📥 번역된 파일 다운로드",
                    data=output.getvalue(),
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
                st.warning("팁: D열, E열이 실제로 존재하는지 확인해주세요.")

# [Tab 4] 프롬프트 생성
with tab4:
    st.subheader("📝 마닐라 팀 전달용 프롬프트")
    st.info("아래 내용을 복사해서 AI에게 엑셀 파일과 함께 전달하세요.")
    
    display_prompt = f"""
# Role Definition
{master_prompt}

# [INPUT DATA]
1. Read the Excel file.
2. Translate the content in **Column {col_source}** (English).
3. Put the result in **Column {col_target}** (Korean).
"""
    st.code(display_prompt, language='text')
