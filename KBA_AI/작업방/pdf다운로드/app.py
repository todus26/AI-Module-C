import io
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file, stream_with_context
from openai import OpenAI
from pypdf import PdfReader

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 업로드 최대 30MB

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MAX_CHUNK_CHARS = 3000
MAX_RETRIES = 3
JOB_TTL_SECONDS = 60 * 60

DIRECTIONS = {
    "en-ko": ("English", "Korean"),
    "ko-en": ("Korean", "English"),
}

JOBS = {}
JOBS_LOCK = threading.Lock()


def get_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "환경 변수 OPENAI_API_KEY 가 설정되어 있지 않습니다. 설정 후 서버를 다시 실행해 주세요."
        )
    return OpenAI(api_key=api_key)


def cleanup_jobs():
    now = time.time()
    with JOBS_LOCK:
        expired = [k for k, v in JOBS.items() if now - v["created"] > JOB_TTL_SECONDS]
        for key in expired:
            del JOBS[key]


def extract_pages(file_stream):
    reader = PdfReader(file_stream)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ValueError("암호가 걸린 PDF는 처리할 수 없습니다.")
    pages = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        pages.append(text)
    return pages


def split_text(text, limit=MAX_CHUNK_CHARS):
    """문단(줄) 단위로 묶어 limit 이하의 청크로 나눈다."""
    chunks, buf = [], ""
    for line in text.splitlines():
        while len(line) > limit:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(buf) + len(line) + 1 > limit and buf:
            chunks.append(buf)
            buf = line
        else:
            buf = f"{buf}\n{line}" if buf else line
    if buf.strip():
        chunks.append(buf)
    return chunks


def build_chunks(pages):
    result = []
    for page_no, text in enumerate(pages, start=1):
        if not text:
            continue
        for part in split_text(text):
            result.append((page_no, part))
    return result


def translate_chunk(client, text, src, dst):
    system_prompt = (
        f"You are a professional translator. Translate the user's {src} text into natural {dst}. "
        "Preserve line breaks and paragraph structure. "
        "Output only the translated text without any explanation or extra comments."
    )
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
    raise last_error


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def safe_stem(filename):
    stem = Path(filename or "translated").stem
    stem = re.sub(r'[\\/:*?"<>|\r\n]+', "_", stem).strip(" .")
    return stem or "translated"


@app.route("/")
def index():
    return render_template("index.html", model=OPENAI_MODEL)


@app.route("/upload", methods=["POST"])
def upload():
    cleanup_jobs()
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="PDF 파일을 선택해 주세요."), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify(error="PDF 파일만 업로드할 수 있습니다."), 400

    try:
        pages = extract_pages(io.BytesIO(file.read()))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        return jsonify(error="PDF를 읽는 중 오류가 발생했습니다. 손상된 파일이 아닌지 확인해 주세요."), 400

    chunks = build_chunks(pages)
    if not chunks:
        return jsonify(error="추출할 수 있는 텍스트가 없습니다. (스캔 이미지 PDF일 수 있습니다.)"), 400

    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {
            "created": time.time(),
            "filename": file.filename,
            "chunks": chunks,
            "status": "ready",
            "translated": "",
        }

    return jsonify(
        job_id=job_id,
        filename=file.filename,
        page_count=len(pages),
        chunk_count=len(chunks),
        text="\n\n".join(p for p in pages if p),
    )


@app.route("/translate/<job_id>")
def translate(job_id):
    direction = request.args.get("direction", "en-ko")
    if direction not in DIRECTIONS:
        return jsonify(error="지원하지 않는 번역 방향입니다."), 400
    src, dst = DIRECTIONS[direction]

    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return jsonify(error="작업을 찾을 수 없습니다. PDF를 다시 업로드해 주세요."), 404
        if job["status"] == "running":
            return jsonify(error="이미 번역이 진행 중입니다."), 409
        job["status"] = "running"
        job["translated"] = ""

    @stream_with_context
    def generate():
        total = len(job["chunks"])
        try:
            client = get_client()
            yield sse("start", {"total": total})
            parts = []
            for index, (page_no, text) in enumerate(job["chunks"], start=1):
                translated = translate_chunk(client, text, src, dst)
                parts.append(translated)
                job["translated"] = "\n\n".join(parts)
                yield sse(
                    "chunk",
                    {
                        "index": index,
                        "total": total,
                        "page": page_no,
                        "percent": round(index / total * 100),
                        "text": translated + "\n\n",
                    },
                )
            job["status"] = "done"
            yield sse("done", {"percent": 100})
        except GeneratorExit:
            job["status"] = "ready"
            raise
        except Exception as exc:
            job["status"] = "ready"
            yield sse("error", {"message": f"번역 중 오류가 발생했습니다: {exc}"})

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@app.route("/download/<job_id>")
def download(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if job is None or job["status"] != "done":
        return jsonify(error="번역이 완료된 작업이 없습니다."), 404

    data = io.BytesIO(job["translated"].encode("utf-8"))
    return send_file(
        data,
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name=f"{safe_stem(job['filename'])}.txt",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
