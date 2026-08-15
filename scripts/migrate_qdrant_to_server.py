"""One-shot migration: copy collections from the embedded on-disk Qdrant store
into the running native Qdrant server, vectors included (no re-embedding).

    SRC embedded : data/qdrant   (path mode)
    DST server   : http://localhost:6355

Idempotent per point id. Safe to re-run; recreates the DST collection.
"""
from __future__ import annotations

import sys

from qdrant_client import QdrantClient, models

SRC_PATH = "data/qdrant"
DST_URL = "http://localhost:6355"
BATCH = 1000


def main() -> int:
    src = QdrantClient(path=SRC_PATH)
    dst = QdrantClient(url=DST_URL)

    for col in src.get_collections().collections:
        name = col.name
        info = src.get_collection(name)
        vparams = info.config.params.vectors
        total = info.points_count
        print(f"→ {name}: {total} points à copier", flush=True)

        dst.recreate_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=vparams.size, distance=vparams.distance),
        )

        copied, offset = 0, None
        while True:
            points, offset = src.scroll(
                name, limit=BATCH, offset=offset,
                with_payload=True, with_vectors=True,
            )
            if not points:
                break
            dst.upsert(
                collection_name=name,
                points=[
                    models.PointStruct(id=p.id, vector=p.vector, payload=p.payload)
                    for p in points
                ],
                wait=False,
            )
            copied += len(points)
            print(f"   … {copied}/{total}", flush=True)
            if offset is None:
                break

        dst_count = dst.get_collection(name).points_count
        print(f"✅ {name} migré : {dst_count} points côté serveur\n", flush=True)

    src.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
