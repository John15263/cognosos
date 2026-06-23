from backend.app.services.embedding_service import embed_text


def local_embedder(text: str):
    return embed_text(text)

