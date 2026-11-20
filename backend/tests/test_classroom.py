"""Classroom mode: a phone camera sees the board at an angle; its four marked corners straighten every frame."""
import io
import json

import cv2
import numpy as np
from PIL import Image

from tests.conftest import board_png

# a board seen from a desk to the side: wider at the bottom, leaning right
QUAD = [[0.30, 0.18], [0.82, 0.24], [0.88, 0.80], [0.20, 0.86]]


def _scene(w=1280, h=720) -> np.ndarray:
    """A grey classroom with a red board in perspective."""
    img = np.full((h, w, 3), 128, np.uint8)
    pts = (np.array(QUAD) * [w, h]).astype(np.int32)
    cv2.fillConvexPoly(img, pts, (200, 30, 30))
    return img


def test_corners_are_ordered_and_bad_input_is_ignored():
    from app.services import perspective

    shuffled = json.dumps([QUAD[2], QUAD[0], QUAD[3], QUAD[1]])
    ordered = perspective.parse_corners(shuffled)
    assert np.allclose(ordered, np.array(QUAD, np.float32))
    for bad in ["", "nope", json.dumps(QUAD[:3]), json.dumps([[0, 0], [2, 0], [1, 1], [0, 1]]),
                json.dumps([[0.5, 0.5], [0.51, 0.5], [0.51, 0.51], [0.5, 0.51]])]:  # missing, garbled, 3 points, off-frame, a sliver
        assert perspective.parse_corners(bad) is None


def test_warp_gives_a_front_on_board():
    from app.services import perspective

    out = perspective.warp(_scene(), perspective.parse_corners(json.dumps(QUAD)))
    h, w = out.shape[:2]
    assert 850 < w < 890 and 490 < h < 520  # its longest sides (871 x 506 here): the board, not the 1280 x 720 frame
    red = (out[:, :, 0] > 150) & (out[:, :, 1] < 80)
    assert red.mean() > 0.97  # nothing of the room around it is left


def test_frame_endpoint_straightens_camera_frames(client, auth):
    session = client.post("/api/sessions", headers=auth, json={"title": "Classroom", "source": "camera"}).json()
    assert session["source"] == "camera"
    # a readable board, then shown at an angle inside a bigger frame, as a phone would see it
    board = np.asarray(Image.open(io.BytesIO(board_png(["Newton's second law", "F = m a", "Unit: newton (N)"]))).convert("RGB"))
    h, w = 900, 1600
    src = np.array([[0, 0], [board.shape[1], 0], [board.shape[1], board.shape[0]], [0, board.shape[0]]], np.float32)
    dst = (np.array(QUAD) * [w, h]).astype(np.float32)
    scene = cv2.warpPerspective(board, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(90, 90, 90))
    buf = io.BytesIO()
    Image.fromarray(scene).save(buf, format="JPEG", quality=92)
    r = client.post(f"/api/capture/{session['id']}/frame", headers=auth,
                    files={"frame": ("frame.jpg", buf.getvalue(), "image/jpeg")},
                    data={"force": "true", "camera": "true", "corners": json.dumps(QUAD)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("created", "growing", "updated"), body
    text = json.dumps(body).lower()
    assert "newton" in text or "f = m" in text or "f=ma" in text
