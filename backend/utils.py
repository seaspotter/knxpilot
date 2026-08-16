"""Small shared helpers with no dependencies on the rest of the app."""


def join_parts(*parts):
    """Join name fragments with a single space, skipping empty ones (avoids double spaces)."""
    return " ".join(p for p in parts if p)


def channel_letters(n):
    """Spreadsheet-style channel labels: A, B, ..., Z, AA, AB, ... for n channels."""
    result = []
    for i in range(1, n + 1):
        label = ""
        x = i
        while x > 0:
            x, rem = divmod(x - 1, 26)
            label = chr(65 + rem) + label
        result.append(label)
    return result
