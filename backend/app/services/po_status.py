def _normalize_po_status(value: str | None) -> str:
    if not value:
        return ''
    normalized = value.strip().lower().replace('-', ' ').replace('_', ' ')
    return ' '.join(normalized.split())


def is_po_received_raw(value: str | None) -> bool:
    normalized = _normalize_po_status(value)
    return normalized in {'po received', 'po recieve', 'po recieved', 'po recived'}
