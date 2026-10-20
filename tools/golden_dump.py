"""印出引擎對所有 golden 案例的結果 JSON（CLI 放在 tools/，讓 golden/ 保持可攜）。

用法：python tools/golden_dump.py（需 engine/bridge.py，Task 16 之後才有）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from golden import runner  # noqa: E402


def main():
    """載入 excel.json，呼叫 engine.bridge.call，印出 {id: 值}。"""
    from engine.bridge import call
    path = os.path.join("tests", "golden", "excel.json")
    print(json.dumps(runner.dump(runner.load(path), call),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
