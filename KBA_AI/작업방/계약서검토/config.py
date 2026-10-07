"""프로젝트 전체에서 쓰는 설정값 모음.

값을 바꾸고 싶을 때 이 파일만 고치면 되도록 한곳에 모아 두었다.
(OPENAI_API_KEY는 시스템 환경변수에 이미 설정되어 있으므로 여기서 다루지 않는다.)
"""
from pathlib import Path

# ---------------------------------------------------------------- 경로
BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = BASE_DIR / "chroma_db"   # 벡터 DB(Chroma)가 저장되는 폴더
UPLOAD_DIR = BASE_DIR / "uploads"     # 업로드된 PDF를 잠시 보관하는 폴더(처리 후 삭제)

# ---------------------------------------------------------------- 모델
LLM_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

# ---------------------------------------------------------------- RAG 문서 분할 (요구사항 4번)
RAG_CHUNK_SIZE = 30
RAG_CHUNK_OVERLAP = 5
# 요구사항에 적힌 순서 그대로 사용한다.
SEPARATORS = ["\n", "\n\n"]

# ---------------------------------------------------------------- 계약서 분할 (요구사항 5번)
CONTRACT_CHUNK_SIZE = 30
CONTRACT_CHUNK_OVERLAP = 0

# ---------------------------------------------------------------- Chroma / 검색
COLLECTION_NAME = "contract_guidelines"
EMBED_BATCH_SIZE = 100   # 임베딩 API를 한 번 호출할 때 보낼 조각 수(= 진행률 갱신 단위)
RETRIEVE_K = 8           # 계약서 문장 하나당 RAG에서 가져올 유사 문서 수

# ---------------------------------------------------------------- 계약서 검토
REVIEW_WORKERS = 4       # 문장을 동시에 몇 개까지 검토할지 (출력 순서는 항상 원문 순서)
MIN_REVIEW_CHARS = 4     # 이 글자 수보다 짧은 조각(쪽번호 등)은 LLM 호출 없이 원문만 출력
CONTEXT_CHARS = 200      # 앞·뒤 문장을 프롬프트에 참고용으로 넣을 때 최대 글자 수
# 수정문에 새로 들어갈 수 있는 글자 수의 한도 = max(MIN_INSERT_ALLOWED, 원문 길이 * MAX_INSERT_RATIO)
# 30글자 단위로 잘린 조각을 LLM 이 멋대로 완성해 버리는 것을 막기 위한 안전장치.
MAX_INSERT_RATIO = 0.5
MIN_INSERT_ALLOWED = 12

# ---------------------------------------------------------------- 일반 질문
CHAT_HISTORY_LIMIT = 10  # 일반 질문 시 LLM에 함께 보낼 이전 대화 개수

# ---------------------------------------------------------------- Flask
HOST = "127.0.0.1"
PORT = 5050              # 5000 번은 다른 Flask 예제와 겹치기 쉬워 5050 을 사용한다
MAX_UPLOAD_MB = 200
