import threading

import cv2
import gradio as gr
import numpy as np
from ultralytics import YOLO

MODEL_PATH = "yolo11n.pt"
CONF_THRESHOLD = 0.25
BOX_COLOR = (0, 200, 0)

model = YOLO(MODEL_PATH)
model_lock = threading.Lock()


def detect(image: np.ndarray | None) -> np.ndarray | None:
    """RGB 이미지를 받아 바운딩 박스, 범주이름, 신뢰도를 그린 RGB 이미지를 반환한다."""
    if image is None:
        return None

    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    with model_lock:
        result = model.predict(bgr, conf=CONF_THRESHOLD, verbose=False)[0]

    thickness = max(2, round(max(bgr.shape[:2]) / 400))
    font_scale = max(0.5, max(bgr.shape[:2]) / 1200)

    for box in result.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        label = f"{result.names[int(box.cls[0])]} {float(box.conf[0]):.2f}"

        cv2.rectangle(bgr, (x1, y1), (x2, y2), BOX_COLOR, thickness)

        (tw, th), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        left = max(min(x1, bgr.shape[1] - tw - 6), 0)
        top = max(y1 - th - baseline - 4, 0)
        cv2.rectangle(bgr, (left, top), (left + tw + 6, top + th + baseline + 4), BOX_COLOR, -1)
        cv2.putText(
            bgr,
            label,
            (left + 3, top + th + 1),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            max(1, thickness - 1),
            cv2.LINE_AA,
        )

    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


with gr.Blocks(title="YOLO11 사물인식") as demo:
    with gr.Row(equal_height=False):
        with gr.Column(scale=1):
            gr.Markdown("### 이미지 업로드")
            upload_in = gr.Image(
                label="입력 이미지", sources=["upload", "clipboard"], type="numpy"
            )
            upload_out = gr.Image(label="탐지 결과", interactive=False)

        with gr.Column(scale=1):
            gr.Markdown("### 웹캠")
            webcam_in = gr.Image(
                label="웹캠 입력", sources=["webcam"], type="numpy", streaming=True
            )
            webcam_out = gr.Image(label="실시간 탐지 결과", interactive=False)

    upload_in.change(detect, inputs=upload_in, outputs=upload_out)
    webcam_in.stream(
        detect,
        inputs=webcam_in,
        outputs=webcam_out,
        stream_every=0.1,
        time_limit=None,
        show_progress="hidden",
    )


if __name__ == "__main__":
    demo.launch()
