import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 모델 경로 ────────────────────────────────────────────────
LLM_MODEL_PATH = os.path.join(
    BASE_DIR, "models", "exaone_2.4b", "EXAONE-3.5-2.4B-Instruct-Q5_K_M.gguf"
)
EMBEDDING_MODEL_DIR = os.path.join(BASE_DIR, "models", "bge-m3")
# llama-cpp-python 은 GGUF 만 읽을 수 있으므로 bge-m3 원본(HF 형식)을 변환한 파일을 사용한다.
EMBEDDING_MODEL_PATH = os.path.join(EMBEDDING_MODEL_DIR, "bge-m3-f16.gguf")

# ── 저장소 경로 ──────────────────────────────────────────────
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "pdf_documents"

# ── llama.cpp 실행 설정 ──────────────────────────────────────
N_THREADS = int(os.environ.get("RAG_N_THREADS", os.cpu_count() or 4))
N_GPU_LAYERS = int(os.environ.get("RAG_N_GPU_LAYERS", 0))
LLM_N_CTX = 8192
LLM_MAX_TOKENS = 512
LLM_TEMPERATURE = 0.1
EMBEDDING_N_CTX = 2048

# ── RAG 파라미터 ─────────────────────────────────────────────
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
# 문단(빈 줄, 줄바꿈) → 문장(마침표/물음표/느낌표 뒤) → 단어 → 글자 순으로 분할
SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]
TOP_K = 4
# 코사인 유사도(0~1). 가장 유사한 chunk 가 이 값보다 낮으면 "관련 chunk 없음"으로 판단한다.
RELEVANCE_THRESHOLD = float(os.environ.get("RAG_RELEVANCE_THRESHOLD", 0.55))
# 후속 질문은 이전 질문과 합쳐 검색하지만, 현재 질문 단독 점수가 이 값보다 낮으면
# 이전 대화 주제에 끌려간 무관한 질문(예: 문서 대화 중 "프랑스 혁명은?")으로 보고 차단한다.
MIN_QUESTION_RELEVANCE = float(os.environ.get("RAG_MIN_QUESTION_RELEVANCE", 0.4))
HISTORY_QUERY_TURNS = 2

# ── 대화 메모리 ──────────────────────────────────────────────
MEMORY_MAX_TURNS = 3
MEMORY_MAX_ANSWER_CHARS = 400

NO_INFO_MESSAGE = "정보가 없어서 답변할 수 없습니다"

MAX_UPLOAD_MB = 100
