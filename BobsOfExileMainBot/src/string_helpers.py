def pad_left_to_length(text: str, length: int, padding: str) -> str:
    text_l: int = len(text)
    to_pad: int = max(0, length - text_l)
    pads: str = padding * to_pad
    padded: str = f'{pads}{text}'
    return padded