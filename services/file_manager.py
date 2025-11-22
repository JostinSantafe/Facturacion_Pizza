import os
from config.settings import PENDIENTES_BASE, PENDIENTES_DIAN, ERROR_DIR

def save_xml(content, filename, folder="base"):
    if folder == "base":
        path = os.path.join(PENDIENTES_BASE, filename)
    elif folder == "xmldian":
        path = os.path.join(PENDIENTES_DIAN, filename)
    else:
        path = os.path.join(ERROR_DIR, filename)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
    return path
