"""Mentor photos: sent by the mentor, checked by Focs before any student sees one (with the application, or on its
own later), cropped square with the phone's metadata gone, and served only while current."""
import io

from PIL import Image

from app.services import storage
from tests.test_mentors import _admin, _apply, _user


def _photo(size=(1200, 1600), exif=True) -> bytes:
    img = Image.new("RGB", size, (200, 120, 90))
    buf = io.BytesIO()
    info = Image.Exif()
    info[0x010F] = "PhoneMaker"  # Make; a real phone also writes where the photo was taken
    img.save(buf, format="JPEG", exif=info.tobytes() if exif else b"")
    return buf.getvalue()


def _upload(client, h, data=None, kind="image/jpeg"):
    return client.post("/api/mentors/me/photo", headers=h, files={"photo": ("me.jpg", data or _photo(), kind)})


def _card(client, student, name):
    return next((m for m in client.get("/api/mentors", headers=student).json()["mentors"] if m["name"] == name), None)


def test_a_photo_is_seen_only_once_checked(client, monkeypatch):
    mentor = _user(client, "photo.mentor@example.com", name="Kavya Rao", role="mentor")
    student = _user(client, "photo.student@example.com")
    admin = _admin(client, monkeypatch)

    assert _upload(client, mentor).status_code == 404  # no application yet: no card to put it on
    assert _apply(client, mentor).status_code == 201
    assert _upload(client, mentor, b"not a picture").status_code == 400
    assert _upload(client, mentor, kind="image/gif").status_code == 415
    sent = _upload(client, mentor)
    assert sent.status_code == 200 and sent.json()["photo"] is None and sent.json()["photo_pending"]

    # the stored picture: square, small, nothing of the original file's metadata
    picture = client.get(sent.json()["photo_pending"])
    assert picture.status_code == 200 and picture.headers["content-type"] == "image/jpeg"
    img = Image.open(io.BytesIO(picture.content))
    assert img.size == (480, 480) and not img.getexif()

    # approving the application approves the photo that came with it
    row = next(a for a in client.get("/api/admin/mentors", headers=admin).json() if a["name"] == "Kavya Rao")
    assert row["photo_pending"] == sent.json()["photo_pending"]
    assert client.post(f"/api/admin/mentors/{row['id']}/review", headers=admin, json={"approve": True}).status_code == 200
    first = _card(client, student, "Kavya Rao")["photo"]
    assert first == sent.json()["photo_pending"] and "photo_pending" not in _card(client, student, "Kavya Rao")

    # a new photo from a listed mentor waits for its own check; students keep seeing the old one
    newer = _upload(client, mentor).json()["photo_pending"]
    assert _card(client, student, "Kavya Rao")["photo"] == first
    waiting = client.get("/api/admin/mentors?status=photo", headers=admin).json()
    assert [a["photo_pending"] for a in waiting if a["name"] == "Kavya Rao"] == [newer]
    rejected = client.post(f"/api/admin/mentors/{row['id']}/photo", headers=admin, json={"approve": False, "note": "Logo, not a face"})
    assert rejected.status_code == 200 and client.get(newer).status_code == 404  # deleted
    note = client.get("/api/notifications", headers=mentor).json()
    assert any("Logo, not a face" in n["text"] for n in (note["items"] if isinstance(note, dict) else note))
    assert _card(client, student, "Kavya Rao")["photo"] == first

    newest = _upload(client, mentor).json()["photo_pending"]
    assert client.post(f"/api/admin/mentors/{row['id']}/photo", headers=admin, json={"approve": True}).status_code == 200
    assert _card(client, student, "Kavya Rao")["photo"] == newest and client.get(first).status_code == 404  # old one gone

    # taking it down needs no check
    assert client.delete("/api/mentors/me/photo", headers=mentor).json()["photo"] is None
    assert _card(client, student, "Kavya Rao")["photo"] is None and client.get(newest).status_code == 404


def test_photo_names_cant_be_used_to_read_other_files(client):
    storage._put("mentor-proof/1-123.jpg", b"an ID card")
    for name in ("..%2Fmentor-proof%2F1-123.jpg", "1-123.jpg", "1-abcdefghijklmnopqrstuv.png", "x" * 30 + ".jpg"):
        assert client.get(f"/api/mentors/photos/{name}").status_code == 404
