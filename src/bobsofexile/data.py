from collections import deque
from collections.abc import Sequence


class RecentBytesBuffer:
    __slots__ = ("buffer",)

    buffer: deque[int]

    def __init__(self, max_bytes: int) -> None:
        self.buffer = deque(maxlen=max_bytes)

    def extend(self, b: bytes) -> None:
        self.buffer.extend(b)

    def as_text(
        self,
        start: int | None = None,
        stop: int | None = None,
        step: int | None = None,
        errors_decoding_mode: str = "replace",
    ) -> str:
        slice_as_bytes: bytes = bytes(self.buffer)[start:stop:step]
        return slice_as_bytes.decode(errors=errors_decoding_mode)

    def as_lines(
        self,
        max_lines: int,
        errors_decoding_mode: str = "replace",
    ) -> Sequence[str]:
        as_text: str = self.as_text(
            None, None, None, errors_decoding_mode=errors_decoding_mode
        )
        # This split is an extremely lazy way of doing this and will waste resources
        lines: Sequence[str] = as_text.split("\n")
        lines_l: int = len(lines)
        start_index: int = max(0, lines_l - max_lines)
        return lines[start_index:]

    def as_lines_length_limited(
        self,
        max_lines: int,
        max_line_length: int,
        ellipsis: str = "...",
        errors_decoding_mode: str = "replace",
    ) -> Sequence[str]:
        ellipsis = ellipsis[:max_line_length]
        as_lines: Sequence[str] = self.as_lines(
            max_lines, errors_decoding_mode=errors_decoding_mode
        )
        lines: Sequence[str] = list()
        ellipsis_l: int = len(ellipsis)
        max_length_with_ellipsis: int = max(0, max_line_length - ellipsis_l)
        for line in as_lines:
            line_l: int = len(line)
            if line_l > max_line_length:
                new_line: str = line[:max_length_with_ellipsis] + ellipsis
                lines.append(new_line)
                continue
            lines.append(line)
        return lines
