from flask import Flask

app = Flask(__name__)  # 내 프로그램을 Flask 앱으로 등록


@app.route("/")  # 사용자가 홈페이지 주소로 들어오면
def hello():
    return "안녕하세요! 여러분의 첫 번째 웹 서버입니다."


if __name__ == "__main__":
    app.run()  # 서버 실행!
