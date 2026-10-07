"""tqdm 진행률 막대를 웹 화면으로 보내기 위한 도우미.

tqdm은 원래 터미널에 막대를 그리지만, 여기서는 tqdm이 만든 막대 문자열
(예: ' 50%|█████     | 5/10 [00:01<00:01,  4.9page/s]')을 꺼내서
브라우저로 전달한다. 화면에 보여 주는 쪽은 static/app.js 이다.
"""
import io

from tqdm import tqdm


class WebProgress:
    """tqdm 막대 하나를 감싸고, 갱신될 때마다 화면 전송용 이벤트(dict)를 만든다."""

    def __init__(self, key: str, label: str, total: int, unit: str = "개"):
        self.key = key              # 화면에서 같은 막대를 계속 갱신하기 위한 식별자
        self.label = label          # 막대 위에 표시할 설명
        self.total = max(total, 1)  # 0으로 나누는 일을 막기 위해 최소 1
        # file=io.StringIO() : 터미널에는 출력하지 않고 문자열로만 사용한다.
        # ascii=False        : 유니코드 블록(█) 막대로 예쁘게 표시한다.
        self.bar = tqdm(
            total=self.total,
            unit=unit,
            ncols=64,
            ascii=False,
            file=io.StringIO(),
            leave=False,
        )

    def event(self) -> dict:
        """현재 상태를 화면으로 보낼 이벤트로 만든다."""
        text = self.bar.format_meter(**self.bar.format_dict).strip()
        return {
            "type": "progress",
            "key": self.key,
            "label": self.label,
            "bar": text,
            "percent": round(self.bar.n / self.total * 100),
        }

    def update(self, n: int = 1) -> dict:
        """n만큼 진행시키고 갱신된 이벤트를 돌려준다."""
        self.bar.update(n)
        return self.event()

    def close(self) -> None:
        self.bar.close()
