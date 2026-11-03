"""다국어 번역기 - Streamlit 앱"""

import os

import openai
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# --- 페이지 설정 (반드시 첫 Streamlit 호출) ---
st.set_page_config(page_title="다국어 번역기", page_icon="🌐", layout="centered")

# --- 환경 변수 로드 (.env) ---
load_dotenv()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-astra")
REQUEST_TIMEOUT = 30  # 초. 응답이 이보다 늦으면 시간 초과로 처리

# --- 지원 언어 목록 (버튼 라벨: (언어 코드, 프롬프트에 넣을 언어 이름)) ---
# 국기 이모지는 Windows에서 글자로 표시되므로 언어 코드를 사용한다.
LANGUAGES = {
    "영어": ("EN", "English"),
    "일본어": ("JA", "Japanese"),
    "베트남어": ("VI", "Vietnamese"),
}

# --- 번역 시스템 프롬프트 (PRD 6장) ---
SYSTEM_PROMPT = (
    "You are a professional translator.\n"
    "Translate the user's text into {target_language}.\n"
    "Output only the translated text, without explanations or quotes.\n"
    "Preserve line breaks and formatting."
)


@st.cache_resource
def get_client(api_key: str) -> OpenAI:
    """OpenAI 클라이언트를 한 번만 만들어 재사용한다."""
    return OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT)


def translate(text: str, target_language: str) -> str:
    """OpenAI API로 텍스트를 target_language로 번역해 번역문만 반환한다."""
    response = get_client(OPENAI_API_KEY).chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(target_language=target_language)},
            {"role": "user", "content": text},
        ],
    )
    return (response.choices[0].message.content or "").strip()


# --- 세션 상태 초기화 (화면이 다시 그려져도 결과 유지) ---
st.session_state.setdefault("result", None)
st.session_state.setdefault("result_label", None)
st.session_state.setdefault("error", None)

# --- 간단한 스타일 (색은 Streamlit 테마를 따르므로 라이트/다크 모드 모두 대응) ---
st.markdown(
    """
    <style>
    .block-container { padding-top: 2.5rem; max-width: 760px; }
    h1 { font-size: 2.1rem !important; }
    .stTextArea textarea { font-size: 1.05rem; line-height: 1.6; }
    .stButton button p { font-size: 1.05rem; font-weight: 600; }
    [data-testid="stCode"] pre, [data-testid="stCode"] code { font-size: 1.05rem; line-height: 1.7; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 헤더 ---
st.title("🌐 다국어 번역기")
st.caption("번역할 글을 입력하고 언어 버튼을 누르면 해당 언어로 번역합니다.")

# API 키가 없으면 상단에 오류를 한 번만 표시하고 버튼을 비활성화한다
if not OPENAI_API_KEY:
    st.error(".env 파일에 OPENAI_API_KEY를 설정해 주세요.")

# --- 입력 영역 ---
text = st.text_area(
    "번역할 글",
    height=180,
    placeholder="번역할 글을 입력하세요...",
    label_visibility="collapsed",
)
st.caption(f"{len(text):,}자")

# --- 언어 버튼 (마지막으로 번역한 언어는 강조) ---
selected_label = None
columns = st.columns(len(LANGUAGES))
for column, (label, (code, _)) in zip(columns, LANGUAGES.items()):
    with column:
        is_last = label == st.session_state.result_label
        if st.button(
            f"{label} ({code})",
            key=f"btn_{label}",
            type="primary" if is_last else "secondary",
            width="stretch",
            disabled=not OPENAI_API_KEY,
        ):
            selected_label = label

# --- 버튼 클릭 처리 ---
if selected_label:
    st.session_state.error = None
    if not text.strip():
        st.warning("번역할 내용을 입력해 주세요.")
    else:
        try:
            with st.spinner("번역 중..."):
                result = translate(text, LANGUAGES[selected_label][1])
        except openai.AuthenticationError:
            st.session_state.error = "API 키가 올바르지 않습니다."
        except openai.NotFoundError:
            st.session_state.error = "모델을 찾을 수 없습니다. .env의 OPENAI_MODEL 값을 확인해 주세요."
        except openai.APITimeoutError:  # APIConnectionError의 하위 클래스이므로 먼저 처리
            st.session_state.error = "응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
        except (openai.RateLimitError, openai.APIConnectionError):
            st.session_state.error = "잠시 후 다시 시도해 주세요."
        except Exception:
            st.session_state.error = "번역 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        else:
            previous_label = st.session_state.result_label
            st.session_state.result = result
            st.session_state.result_label = selected_label
            # 버튼 강조 상태를 즉시 반영하기 위해 다시 그림
            if previous_label != selected_label:
                st.rerun()

        # 번역이 실패하면 이전 결과와 버튼 강조를 지워 오류와 섞이지 않게 한다
        # (오류는 session_state에 있으므로 다시 그려도 유지된다)
        if st.session_state.error and st.session_state.result_label is not None:
            st.session_state.result = None
            st.session_state.result_label = None
            st.rerun()

# 오류 표시
if st.session_state.error:
    st.error(st.session_state.error)

# --- 결과 영역 ---
with st.container(border=True):
    if st.session_state.result is not None:
        st.markdown(f"**번역 결과 ({st.session_state.result_label})**")
        # st.code는 오른쪽 위에 복사 버튼을 제공한다 (PRD F-9)
        st.code(st.session_state.result, language=None, wrap_lines=True)
    else:
        st.caption("언어 버튼을 누르면 여기에 번역 결과가 표시됩니다.")

# --- 하단 정보 ---
st.caption(f"모델: {OPENAI_MODEL}")
