import json
import os
import secrets
import uuid

from flask import Flask, Response, jsonify, render_template, request, session, stream_with_context
from werkzeug.exceptions import RequestEntityTooLarge

import config
from rag import RAGEngine

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024

os.makedirs(config.UPLOAD_DIR, exist_ok=True)

print("모델을 불러오는 중입니다… (LLM: EXAONE-3.5-2.4B, 임베딩: bge-m3)")
engine = RAGEngine()
print("모델 로딩 완료")


def _session_id() -> str:
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def _display_name(filename: str) -> str:
    name = os.path.basename(filename.replace("\\", "/")).strip()
    return name or "document.pdf"


def _is_pdf(file_storage) -> bool:
    if not file_storage.filename.lower().endswith(".pdf"):
        return False
    head = file_storage.stream.read(5)
    file_storage.stream.seek(0)
    return head == b"%PDF-"


@app.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return jsonify(error=f"파일 용량은 최대 {config.MAX_UPLOAD_MB}MB까지 업로드할 수 있습니다."), 413


@app.get("/")
def index():
    _session_id()
    return render_template("index.html", no_info=config.NO_INFO_MESSAGE)


@app.get("/api/documents")
def documents():
    return jsonify(documents=engine.list_documents())


@app.delete("/api/documents/<doc_id>")
def delete_document(doc_id):
    removed = engine.delete_document(doc_id)
    if not removed:
        return jsonify(error="해당 문서를 찾을 수 없습니다."), 404
    return jsonify(removed_chunks=removed)


@app.post("/api/upload")
def upload():
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify(error="업로드할 PDF 파일을 선택해 주세요."), 400

    results = []
    for f in files:
        name = _display_name(f.filename)
        if not _is_pdf(f):
            results.append({"name": name, "ok": False, "error": "PDF 파일만 업로드할 수 있습니다."})
            continue

        tmp_path = os.path.join(config.UPLOAD_DIR, f"{uuid.uuid4().hex}.pdf")
        f.save(tmp_path)
        doc_id = engine.file_hash(tmp_path)
        final_path = os.path.join(config.UPLOAD_DIR, f"{doc_id}.pdf")

        if engine.has_document(doc_id):
            os.remove(tmp_path)
            results.append({"name": name, "ok": True, "duplicate": True, "doc_id": doc_id})
            continue

        try:
            os.replace(tmp_path, final_path)
            stats = engine.ingest_pdf(final_path, name, doc_id)
            results.append({"name": name, "ok": True, "doc_id": doc_id, **stats})
        except Exception as e:
            if os.path.exists(final_path):
                os.remove(final_path)
            results.append({"name": name, "ok": False, "error": f"처리 중 오류가 발생했습니다: {e}"})

    status = 200 if any(r["ok"] for r in results) else 400
    return jsonify(results=results, documents=engine.list_documents()), status


@app.post("/api/chat")
def chat():
    question = (request.get_json(silent=True) or {}).get("question", "").strip()
    if not question:
        return jsonify(error="질문을 입력해 주세요."), 400
    sid = _session_id()

    def generate():
        try:
            for event in engine.stream_answer(sid, question):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"답변 생성 중 오류가 발생했습니다: {e}"}, ensure_ascii=False) + "\n"

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/summarize")
def summarize():
    chunk_id = (request.get_json(silent=True) or {}).get("id", "")
    try:
        return jsonify(id=chunk_id, summary=engine.summarize_chunk(chunk_id))
    except KeyError:
        return jsonify(error="chunk를 찾을 수 없습니다."), 404


@app.get("/api/history")
def history():
    return jsonify(history=engine.get_display_log(_session_id()))


@app.post("/api/reset")
def reset():
    engine.clear_session(_session_id())
    session["sid"] = uuid.uuid4().hex
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), threaded=True, debug=False)
