"""
Training service — enrolls students by generating InsightFace embeddings
and persisting them to the Student_Embeddings table.

Called from:
  - admin.py  POST /admin/enroll-student   (bulk enrollment, N images)
  - user.py   POST /user/resolve-faces     (single face, incremental)
"""

import base64
from typing import List, Union

import cv2
import numpy as np

from database import execute_query, get_db_connection
from model.insightface_engine import InsightFaceEngine


# Module-level engine instance (initialised once, reused)
_engine: InsightFaceEngine | None = None


def _get_engine() -> InsightFaceEngine:
    global _engine
    if _engine is None:
        _engine = InsightFaceEngine()
    return _engine


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enroll_student(prn: str, images: List[Union[str, np.ndarray]]) -> int:
    """
    Generate InsightFace embeddings for a student and store them in
    Student_Embeddings.  Existing embeddings for this PRN are replaced.

    Args:
        prn:    Student PRN (must already exist in Student_Master).
        images: List of base64 strings OR BGR numpy arrays.
                At least 1 image required; more images → better centroid.

    Returns:
        Number of embeddings successfully stored.

    Raises:
        ValueError: If no usable face is detected in any image.
        RuntimeError: On DB write failure.
    """
    if not images:
        raise ValueError("At least one image is required for enrollment")

    engine = _get_engine()
    embeddings: List[np.ndarray] = []

    for idx, img in enumerate(images):
        bgr = _to_bgr(img, idx)
        if bgr is None:
            continue
        try:
            face_data = engine.detect_and_embed(bgr)
            if not face_data:
                continue
            # Take the highest-confidence face from each image
            best = max(face_data, key=lambda f: f["score"])
            embeddings.append(best["embedding"])
        except Exception as exc:
            print(f"[training_service] Skipping image {idx}: {exc}")
            continue

    if not embeddings:
        raise ValueError(
            "No faces detected in any of the provided images. "
            "Please upload clear, well-lit face photos."
        )

    # Delete old embeddings for this PRN, then insert fresh ones
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "DELETE FROM Student_Embeddings WHERE prn = %s", (prn,)
        )
        for emb in embeddings:
            blob = InsightFaceEngine.embedding_to_bytes(emb)
            cursor.execute(
                "INSERT INTO Student_Embeddings (prn, embedding) VALUES (%s, %s)",
                (prn, blob),
            )
        connection.commit()
    except Exception as exc:
        connection.rollback()
        raise RuntimeError(f"Failed to save embeddings for PRN {prn}: {exc}") from exc
    finally:
        cursor.close()
        connection.close()

    print(f"[training_service] Stored {len(embeddings)} embeddings for PRN {prn}")
    return len(embeddings)


def incremental_enroll(prn: str, image: Union[str, np.ndarray]) -> bool:
    """
    Add a single face embedding for an existing student (used by resolve-faces).

    Does NOT delete existing embeddings — appends one new row.

    The image is expected to be an already-cropped face (from InsightFace's own
    detection output). We try two strategies:
    1. Direct embedding via detect_and_embed (works if there's enough context)
    2. If no face detected, resize the crop to 112x112 and embed directly using
       the ArcFace model's expected input size — this handles tight crops.

    Args:
        prn:   Student PRN.
        image: Single base64 string or BGR numpy array of the face crop.

    Returns:
        True if embedding was stored, False if embedding failed.
    """
    engine = _get_engine()
    bgr = _to_bgr(image, 0)
    if bgr is None:
        return False

    blob = None
    try:
        # Strategy 1: try normal detection (works when crop has some padding)
        face_data = engine.detect_and_embed(bgr)
        if face_data:
            best = max(face_data, key=lambda f: f["score"])
            blob = InsightFaceEngine.embedding_to_bytes(best["embedding"])
    except Exception as exc:
        print(f"[training_service] detect_and_embed failed for {prn}: {exc}")

    if blob is None:
        # Strategy 2: the crop is too tight for detection — embed directly.
        # Resize to 112x112 (ArcFace input size), run through the recognition
        # model directly by padding the image and re-running detection on a
        # padded version.
        try:
            h, w = bgr.shape[:2]
            pad = max(h, w) // 4  # add 25% padding on each side
            padded = cv2.copyMakeBorder(bgr, pad, pad, pad, pad,
                                        cv2.BORDER_CONSTANT, value=(0, 0, 0))
            face_data = engine.detect_and_embed(padded)
            if face_data:
                best = max(face_data, key=lambda f: f["score"])
                blob = InsightFaceEngine.embedding_to_bytes(best["embedding"])
        except Exception as exc:
            print(f"[training_service] padded embed failed for {prn}: {exc}")

    if blob is None:
        print(f"[training_service] incremental_enroll: no face detected for {prn}")
        return False

    execute_query(
        "INSERT INTO Student_Embeddings (prn, embedding) VALUES (%s, %s)",
        (prn, blob),
        fetch=False,
    )
    print(f"[training_service] Appended 1 embedding for PRN {prn}")
    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_bgr(image: Union[str, np.ndarray], idx: int) -> np.ndarray | None:
    """Convert a base64 string or numpy array to a BGR numpy array."""
    if isinstance(image, np.ndarray):
        return image

    if isinstance(image, str):
        try:
            b64 = image.split(",", 1)[1] if "," in image else image
            img_bytes = base64.b64decode(b64)
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is None:
                raise ValueError("cv2.imdecode returned None")
            return bgr
        except Exception as exc:
            print(f"[training_service] Cannot decode image at index {idx}: {exc}")
            return None

    print(f"[training_service] Unsupported image type at index {idx}: {type(image)}")
    return None
