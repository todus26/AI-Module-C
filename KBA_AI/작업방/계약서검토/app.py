"""LLM 기반 계약서 검토 웹 - Flask 서버.

실행:  python app.py   ->  브라우저에서 http://127.0.0.1:5050 접속

모든 오래 걸리는 작업(업로드 처리, 계약서 검토, 질문 답변)은 결과를 한꺼번에 돌려주지 않고
'한 줄에 JSON 하나(NDJSON)' 형태로 조금씩 흘려보낸다(스트리밍).
그래서 브라우저가 진행률과 검토 결과를 실시간으로 화면에 그릴 수 있다.
"""
import json
import os
import uuid
import warnings

# langchain-community 의 "곧 지원 중단" 안내 경고는 동작과 무관하므로 숨긴다.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community")

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

import chat
import config
import contract
import rag
import reviewer

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
config.UPLOAD_DIR.mkdir(exist_ok=True)


# ------------------------------------------------------------------ 공통 도우미
def ndjson_response(events, cleanup=None) -> Response:
    """제너레이터가 내보내는 이벤트(dict)를 NDJSON 스트림으로 바꿔 응답한다.

    cleanup : 스트림이 끝나면(오류 포함) 호출할 정리 함수. (임시 파일 삭제용)
    """

    def generate():
        try:
            for event in events:
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:  # 어떤 오류든 화면에 알려 준다
            yield json.dumps({"type": "error", "text": f"오류가 발생했습니다: {exc}"}, ensure_ascii=False) + "\n"
        finally:
            if cleanup:
                cleanup()

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def error_stream(text: str) -> Response:
    """오류 한 건만 담은 스트림 응답."""
    return ndjson_response(iter([{"type": "error", "text": text}]))


def save_pdfs(file_storages) -> list[tuple[str, str]]:
    """업로드된 PDF 를 임시 폴더에 저장하고 [(저장 경로, 원래 파일명)] 을 돌려준다.

    한글 파일명이 깨지지 않도록 저장 이름은 무작위 id 로 만들고, 원래 이름은 따로 들고 다닌다.
    """
    config.UPLOAD_DIR.mkdir(exist_ok=True)  # 폴더가 지워졌어도 업로드가 실패하지 않게 매번 확인
    saved = []
    for f in file_storages:
        name = f.filename or ""
        if not name.lower().endswith(".pdf"):
            continue
        path = config.UPLOAD_DIR / f"{uuid.uuid4().hex}.pdf"
        f.save(path)
        saved.append((str(path), name))
    return saved


def remove_files(paths) -> None:
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass


# ------------------------------------------------------------------ 화면 / 상태
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    """현재 RAG / 계약서 준비 상태. (화면을 새로 열었을 때 버튼 표시를 복원하는 데 사용)"""
    return jsonify({"rag": rag.list_sources(), "contract": contract.get_state()})


# ------------------------------------------------------------------ RAG 파일 업로드
@app.post("/api/rag/upload")
def rag_upload():
    saved = save_pdfs(request.files.getlist("files"))
    if not saved:
        return error_stream("PDF 파일을 선택해 주세요.")
    return ndjson_response(
        rag.ingest_pdfs(saved), cleanup=lambda: remove_files(p for p, _ in saved)
    )


# ------------------------------------------------------------------ 계약서 업로드
@app.post("/api/contract/upload")
def contract_upload():
    saved = save_pdfs(request.files.getlist("file")[:1])
    if not saved:
        return error_stream("PDF 파일을 선택해 주세요.")
    path, name = saved[0]
    return ndjson_response(
        contract.ingest_contract(path, name), cleanup=lambda: remove_files([path])
    )


# ------------------------------------------------------------------ 계약서 검토
@app.post("/api/review")
def review():
    sentences = contract.STATE["sentences"]
    if not sentences:
        return error_stream("먼저 계약서를 업로드해 주세요.")
    if rag.list_sources()["total_chunks"] == 0:
        return error_stream("검토 기준이 될 RAG 파일이 없습니다. 먼저 'RAG 파일 업로드'를 해 주세요.")
    return ndjson_response(reviewer.stream_review(sentences))


# ------------------------------------------------------------------ 일반 질문 (RAG 미사용)
@app.post("/api/chat")
def chat_route():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return error_stream("질문을 입력해 주세요.")
    return ndjson_response(chat.stream_answer(message, data.get("history") or []))


if __name__ == "__main__":
    # threaded=True : 검토 스트림이 진행되는 중에도 다른 요청을 받을 수 있다.
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)
