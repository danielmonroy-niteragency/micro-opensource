"""Procesamiento de texto independiente de macOS y del motor de voz."""

import re

FILLERS = re.compile(r"\b(?:e+h+m*|e+m+|h?m{2,}|u+h+m*|u+m+)\b[,.]?\s*", re.I)
COMMANDS = [
    (r"(?:punto y aparte|nuevo parrafo|nuevo párrafo|new paragraph)", ".\n\n"),
    (r"(?:nueva linea|nueva línea|new line)", "\n"),
    (r"(?:abrir interrogacion|abrir interrogación)", "¿"),
    (r"(?:cerrar interrogacion|cerrar interrogación)", "?"),
    (r"(?:abrir exclamacion|abrir exclamación)", "¡"),
    (r"(?:cerrar exclamacion|cerrar exclamación)", "!"),
    (r"(?:abrir comillas)", "«"),
    (r"(?:cerrar comillas)", "»"),
    (r"(?:punto y coma)", "; "),
    (r"(?:dos puntos)", ": "),
    (r"(?:punto y seguido|punto final)", ". "),
    (r"(?:coma)", ", "),
]
HALLUCINATIONS = {
    "gracias por ver el video",
    "gracias por ver el vídeo",
    "gracias",
    "thanks for watching",
    "thank you",
    "subtítulos realizados por la comunidad de amara.org",
    "you",
}


def _spoken_commands(text: str) -> str:
    for command, replacement in COMMANDS:
        text = re.sub(rf"[.,]?\s*\b{command}\b[.,]?\s*", replacement, text, flags=re.I)
    return text


def _capitalize_sentences(text: str) -> str:
    chars = list(text)
    should_capitalize = True
    for index, char in enumerate(chars):
        if should_capitalize and char.isalpha():
            chars[index] = char.upper()
            should_capitalize = False
        elif char in ".!?\n":
            should_capitalize = True
    return "".join(chars)


def clean(text: str) -> str:
    text = _spoken_commands(text.strip())
    text = FILLERS.sub("", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"[ \t]+([,.;:?!»])", r"\1", text)
    text = re.sub(r"([¿¡«])\s+", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text).strip()
    normalized = re.sub(r"[^\w\s]", "", text).lower().strip()
    hallucinations = {re.sub(r"[^\w\s]", "", item).lower().strip() for item in HALLUCINATIONS}
    if normalized in hallucinations:
        return ""
    return _capitalize_sentences(text)

