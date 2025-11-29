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

# ⭐ 사이드바 설정
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
    
    level = st.selectbox(
        "Level",
        ["Beginner", "Elementary", "Intermediate", "Advanced"]
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

# 카테고리별 상세 지침
category_guidelines = {
    "Daily Life": """
**특징:**
- 자연스러운 구어체 우선
- 외래어보다 한국어 대체어 선호
- 실생활 표현 그대로

**기본 말투:** polite (~요)

**말투 자동 조정:**
- 원문에 casual 신호 (Wanna, Gonna, Dude, bro) → casual 전환
- 원문에 formal 신호 (Would you, Could you, Sir/Ma'am) → formal 전환
- 대화 맥락이 있으면 관계 파악하여 조정

**예시:**
- "Wanna grab lunch?" → casual → "점심 먹을래?"
- "Would you like to have lunch?" → polite → "점심 드실래요?"
- "Let's have lunch" → 기본 polite → "점심 먹어요"
""",
    
    "Business": """
**특징:**
- 정중하고 전문적인 톤
- 업무 용어는 외래어 허용 (미팅, 이메일, 리포트 등)
- 격식 있는 표현

**기본 말투:** polite~formal

**예시:**
- "Let's schedule a meeting" → "회의 일정을 잡겠습니다"
- "I'll follow up on this" → "이 건은 제가 후속 조치하겠습니다"
- "Could you review the proposal?" → "제안서 검토 부탁드립니다"
""",
    
    "Travel": """
**특징:**
- 실용적이고 명확하게
- 여행 상황별 맥락 반영
- 지명/고유명사는 외래어 유지

**기본 말투:** polite

**예시:**
- "Where's the nearest subway station?" → "가장 가까운 지하철역이 어디예요?"
- "I'd like to check in" → "체크인하려고요"
- "How much is this?" → "이거 얼마예요?"
""",
    
    "News": """
**특징:**
- 객관적이고 간결한 서술
- 감정 표현 배제
- 사실 전달 중심
- 전문 용어 정확히

**기본 말투:** formal (-다/-습니다)

**예시:**
- "The company announced a major restructuring" → "회사는 대규모 구조조정을 발표했다"
- "Experts predict economic growth will slow" → "전문가들은 경제 성장이 둔화될 것으로 예측한다"
- "The government introduced new regulations" → "정부는 새로운 규제를 도입했다"
""",
    
    "Academic": """
**특징:**
- 논리적이고 명확한 표현
- 학술 용어 정확히
- 논거가 분명하게

**기본 말투:** polite~formal

**예시:**
- "In my opinion, this approach is more effective" → "제 생각에는 이 접근 방식이 더 효과적입니다"
- "Research shows that students benefit from" → "연구에 따르면 학생들은 ~로부터 도움을 받는다"
- "Let's discuss the pros and cons" → "장단점을 논의해 봅시다"
""",
    
    "Entertainment": """
**특징:**
- 생동감 있고 재미있게
- 감정/분위기 살리기
- 유행어/신조어 적절히 활용

**기본 말투:** casual~polite

**예시:**
- "That's hilarious!" → "완전 웃겨!" / "진짜 재밌네!"
- "I'm a huge fan of this show" → "이 프로 완전 팬이야"
- "The plot twist was amazing" → "반전이 대박이었어"
""",
    
    "Health": """
**특징:**
- 정확하고 신중하게
- 의학 용어는 한글 또는 설명 추가
- 오해 없도록 명확히

**기본 말투:** polite~formal

**예시:**
- "Take this medication twice a day" → "이 약은 하루 두 번 복용하세요"
- "You should get enough rest" → "충분한 휴식이 필요합니다"
- "Consult your doctor if symptoms persist" → "증상이 지속되면 의사와 상담하세요"
""",
    
    "Technology": """
**특징:**
- 전문적이되 이해하기 쉽게
- 기술 용어는 외래어 유지
- 약어는 그대로 (API, AI, UI 등)

**기본 말투:** polite~formal

**예시:**
- "Update the software to the latest version" → "소프트웨어를 최신 버전으로 업데이트하세요"
- "The AI system processes data in real-time" → "AI 시스템은 데이터를 실시간으로 처리한다"
- "Click on the settings icon" → "설정 아이콘을 클릭하세요"
"""
}

# 레벨별 상세 지침
level_guidelines = {
    "Beginner": """
**특징:**
- 가장 기본적이고 쉬운 단어
- 짧고 단순한 문장 구조
- 한 문장에 하나의 의미만
- 어려운 표현은 쉽게 풀어서

**예시:**
- "I'm feeling under the weather" → "몸이 안 좋아" / "아파"
- "Let's call it a day" → "오늘은 여기까지 하자"
- "I'm swamped with work" → "일이 너무 많아"
""",
    
    "Elementary": """
**특징:**
- 일상적인 표현 사용
- 기본적인 관용구 포함 가능
- 자연스럽되 복잡하지 않게

**예시:**
- "I'm feeling under the weather" → "컨디션이 별로야"
- "Let's call it a day" → "오늘은 이만 마무리하자"
- "I'm swamped with work" → "일이 엄청 많아"
""",
    
    "Intermediate": """
**특징:**
- 자연스러운 관용 표현 활용
- 뉘앙스 살리기
- 다양한 어휘 사용

**예시:**
- "I'm feeling under the weather" → "몸 상태가 좋지 않아"
- "Let's call it a day" → "오늘은 여기서 마치자"
- "I'm swamped with work" → "일에 치여 있어" / "일이 산더미야"
""",
    
    "Advanced": """
**특징:**
- 원어민 수준의 자연스러움
- 문화적 뉘앙스까지 반영
- 상황에 따른 미묘한 차이 표현

**예시:**
- "I'm feeling under the weather" → "몸이 영 개운치 않네"
- "Let's call it a day" → "오늘은 이쯤에서 접자"
- "I'm swamped with work" → "일에 파묻혀 있어" / "일 때문에 정신이 하나도 없어"
"""
}

# 마스터 프롬프트 생성
master_prompt = f"""
You are Uphone's Localization Specialist.
Translate the text from **English** to **Korean**.

{ground_rules}

{common_errors}

# Category-Specific Guidelines
[Category: {category}]
{category_guidelines[category]}

# Level-Specific Guidelines
[Level: {level}]
{level_guidelines[level]}

[Technical Instruction]
- AI will automatically detect content type (Dialogue/Script/Article) and adjust tone accordingly
- Only output the translated Korean text
- Do not add explanations
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
    st.info(f"현재 설정: {category} / {level}")
    
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
    st.info(f"현재 설정: {category} / {level}")
    
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
    st.info(f"현재 설정: {category} / {level}")
    
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
