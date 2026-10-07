# PDF 문서 기반 RAG 챗봇 (로컬 실행)

PDF를 업로드하면 문서 내용을 근거로 질의응답하는 ChatGPT 스타일 웹 챗봇입니다.
LLM과 임베딩 모델 모두 `llama-cpp-python`으로 로컬에서 실행됩니다.

## 실행

```powershell
python app.py
```

브라우저에서 http://127.0.0.1:5000 접속 → 왼쪽 **PDF 업로드**(다중 선택/드래그 가능) → 질문 입력.

## 구성

| 파일 | 역할 |
| --- | --- |
| `app.py` | Flask 서버 (업로드, 문서 목록/삭제, 스트리밍 채팅, chunk 요약, 대화 초기화 API) |
| `rag.py` | RAG 파이프라인 (PyPDFLoader → RecursiveCharacterTextSplitter → bge-m3 → ChromaDB → EXAONE) |
| `config.py` | 모델 경로, chunk/검색/메모리 파라미터 |
| `templates/`, `static/` | 사이드바 + 채팅 UI |

## RAG 동작 방식

- **청킹**: 500자 / overlap 100자, 분할 기준 `["\n\n", "\n", ". ", "? ", "! ", " ", ""]` (문단 → 문장 순)
- **검색**: 코사인 유사도 상위 4개 chunk. 후속 질문은 "최근 질문 2개 + 현재 질문"으로도 검색해 결과를 병합
- **관련 정보 없음 판정**: 최고 유사도 < 0.55 이거나, 현재 질문 단독 유사도 < 0.40 이면 LLM 호출 없이
  `정보가 없어서 답변할 수 없습니다`만 응답. LLM이 같은 문구를 출력한 경우에도 그 문구만 남기고 출처는 숨김
- **대화 메모리**: 세션별 `InMemoryChatMessageHistory`, 최근 3턴을 프롬프트에 포함 (**새 대화** 버튼으로 초기화)
- **출처 표시**: 답변 아래에 파일명, 페이지, 유사도, chunk 요약(LLM이 답변 후 순차 생성) + 원문 보기

임계값은 환경변수 `RAG_RELEVANCE_THRESHOLD`, `RAG_MIN_QUESTION_RELEVANCE` 로 조정할 수 있습니다.

## 환경 관련 참고 (최초 1회 작업, 이미 완료됨)

1. **llama-cpp-python CPU 빌드**: 기존 설치본은 CUDA 빌드여서 NVIDIA GPU가 없는 PC에서 `llama.dll` 로딩이
   실패했습니다. 같은 버전(0.3.33)의 CPU 휠로 재설치했습니다.
   ```powershell
   pip install --force-reinstall --no-deps llama-cpp-python==0.3.33 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
   ```
2. **bge-m3 GGUF 변환**: `models/bge-m3`는 HuggingFace(PyTorch) 형식이라 llama.cpp가 읽을 수 없어,
   llama.cpp의 `convert_hf_to_gguf.py`로 `models/bge-m3/bge-m3-f16.gguf`를 생성했습니다.
   (원본 대비 임베딩 코사인 유사도 0.99999)

CPU(i5-1135G7) 기준 답변 1건에 약 40초가 걸립니다.
