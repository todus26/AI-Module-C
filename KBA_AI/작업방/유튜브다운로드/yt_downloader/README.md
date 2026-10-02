# 유튜브 다운로더

유튜브 링크를 분석하고, 원하는 화질이나 음질로 저장하는 개인용 데스크톱 앱입니다.

이 도구는 사용자가 **개인적으로 이용할 수 있는 콘텐츠**를 내려받기 위한 용도입니다. 저작권이 있는 영상을 권리자의 허락 없이 배포하거나, 저작권을 침해하는 용도로는 사용하지 마세요.

## 준비

- Python 3.10 이상
- FFmpeg (영상·음성 병합, MP3 변환). 없으면 병합이 필요 없는 포맷만 받을 수 있습니다.

```bash
pip install -r requirements.txt
```

Windows에서 FFmpeg는 [공식 빌드](https://www.gyan.dev/ffmpeg/builds/)를 받거나 `winget install Gyan.FFmpeg` 로 설치한 뒤, `ffmpeg` 가 PATH에 잡혀 있는지 확인하면 됩니다.

## 실행

```bash
python main.py
```

## 테스트

```bash
pytest
```
