from flask import Flask

app = Flask(__name__)                   # 내 프로그램을 Flask 앱으로 등록 → app: 전체 프로그램을 관리할 객체

@app.route('/')                         # 사용자가 홈페이지 주소(/)로 들어오면
def hello():
    return "안녕하세요! 여러분의 첫 번째 웹 서버입니다."

if __name__ == '__main__':              # 이 파일을 직접 실행했을 때만 Flask 서버를 실행하라는 표준 조건문
    app.run()                           # 서버 실행!

