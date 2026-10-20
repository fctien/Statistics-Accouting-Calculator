"""印出引擎對所有 golden 案例的結果 JSON（CLI 放在 tools/，讓 golden/ 保持可攜）。

用法：python tools/golden_dump.py（透過 engine/bridge.call 跑全部 golden 案例）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from golden import runner  # noqa: E402


def main():
    """載入 excel.json，呼叫 engine.bridge.call，印出 {id: 值}。"""
    from engine.bridge import call
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "tests", "golden", "excel.json")

    def call_fn(request):
        """runner 要 dict 進 dict 出；bridge 是 JSON 字串進出。"""
        return json.loads(call(json.dumps(request)))

    print(json.dumps(runner.dump(runner.load(path), call_fn),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
