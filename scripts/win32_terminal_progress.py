"""用于隔离 WinRAR ConPTY 尖峰试验的精简 VT 行状态模型。"""

import re

PERCENT_TEXT = re.compile(r"(?<!\d)(\d{1,3})%")


def visible_percentages(output: bytes) -> tuple[tuple[int, ...], dict[str, int]]:
    text = output.decode("utf-8", errors="replace")
    line: list[str] = []
    column = 0
    samples: list[int] = []
    controls = {
        "backspace": 0, "carriageReturn": 0, "lineFeed": 0, "csi": 0, "osc": 0,
    }
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\x1b" and index + 1 < len(text) and text[index + 1] == "]":
            end = text.find("\x07", index + 2)
            if end == -1:
                break
            controls["osc"] += 1
            index = end + 1
            continue
        if char == "\x1b" and index + 1 < len(text) and text[index + 1] == "[":
            match = re.match(r"\x1b\[([0-9;?]*)([@-~])", text[index:])
            if match:
                controls["csi"] += 1
                params, final = match.groups()
                amount = int((params.lstrip("?").split(";")[0] or "1"))
                if final == "D":
                    column = max(0, column - amount)
                elif final == "C":
                    column += amount
                elif final == "G":
                    column = max(0, amount - 1)
                elif final == "K" and params in ("", "0"):
                    del line[column:]
                index += len(match.group(0))
                continue
        if char == "\b":
            controls["backspace"] += 1
            column = max(0, column - 1)
        elif char == "\r":
            controls["carriageReturn"] += 1
            column = 0
        elif char == "\n":
            controls["lineFeed"] += 1
            line, column = [], 0
        elif char >= " ":
            while len(line) <= column:
                line.append(" ")
            line[column] = char
            column += 1
            if char == "%":
                matches = tuple(PERCENT_TEXT.finditer("".join(line)))
                if matches:
                    samples.append(int(matches[-1].group(1)))
        index += 1
    return tuple(samples), controls
