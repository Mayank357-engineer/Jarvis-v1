"""Local face identification and password fallback for Jarvis."""

import hashlib
import hmac
import json
import math
import os
import tempfile
import urllib.request
import uuid
from pathlib import Path


PASSWORD_ITERATIONS = 310_000
FACE_MATCH_THRESHOLD = 0.363
MIN_PASSWORD_LENGTH = 8
MODEL_REVISION = "47534e27c9851bb1128ccc0102f1145e27f23f98"
MODEL_URLS = {
    "yunet.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/"
        f"{MODEL_REVISION}/models/face_detection_yunet/"
        "face_detection_yunet_2023mar.onnx"
    ),
    "sface_int8.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/"
        f"{MODEL_REVISION}/models/face_recognition_sface/"
        "face_recognition_sface_2021dec_int8bq.onnx"
    ),
}


class FaceAuthError(Exception):
    """Raised for face-auth setup, storage, and model errors."""


def _app_data_dir():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Jarvis" / "face_auth"
    return Path.home() / ".local" / "share" / "Jarvis" / "face_auth"


def _password_digest(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    ).hex()


def _validate_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise FaceAuthError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )


class FaceAuthStore:
    """Stores face embeddings and password verification data locally."""

    def __init__(self, data_path=None):
        self.data_path = Path(data_path or (_app_data_dir() / "users.json"))
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = None

        if self.data_path.exists():
            try:
                self.data = json.loads(
                    self.data_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise FaceAuthError(
                    f"Could not read face-auth data: {exc}"
                ) from exc

            if (
                not isinstance(self.data, dict)
                or self.data.get("version") != 1
                or not isinstance(self.data.get("users"), list)
                or not self.data.get("owner_id")
            ):
                raise FaceAuthError(
                    "The local face-auth data is invalid or unsupported."
                )

    @property
    def is_configured(self):
        return self.data is not None

    @property
    def users(self):
        return list(self.data["users"]) if self.data else []

    def _save(self):
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.data_path.parent,
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(self.data, temporary_file, indent=2)
            os.replace(temporary_path, self.data_path)
        except OSError as exc:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
            raise FaceAuthError(
                f"Could not save face-auth data: {exc}"
            ) from exc

    @staticmethod
    def _validate_embedding(embedding):
        if not isinstance(embedding, (list, tuple)) or len(embedding) != 128:
            raise FaceAuthError("The face model returned an invalid embedding.")
        values = [float(value) for value in embedding]
        if not all(math.isfinite(value) for value in values):
            raise FaceAuthError("The face embedding contains invalid values.")
        return values

    def setup_owner(self, name, profile, password, embedding):
        if self.is_configured:
            raise FaceAuthError("Face authentication has already been set up.")
        name = name.strip()
        if not name:
            raise FaceAuthError("Enter the owner's name.")
        _validate_password(password)

        salt = os.urandom(16)
        owner_id = str(uuid.uuid4())
        self.data = {
            "version": 1,
            "owner_id": owner_id,
            "password_salt": salt.hex(),
            "password_hash": _password_digest(password, salt),
            "users": [{
                "id": owner_id,
                "name": name,
                "profile": profile.strip(),
                "embeddings": [self._validate_embedding(embedding)],
            }],
        }
        try:
            self._save()
        except FaceAuthError:
            self.data = None
            raise
        return self.owner

    @property
    def owner(self):
        if not self.data:
            return None
        return next(
            (
                user for user in self.data["users"]
                if user["id"] == self.data["owner_id"]
            ),
            None,
        )

    def verify_password(self, password):
        if not self.data:
            return False
        try:
            salt = bytes.fromhex(self.data["password_salt"])
            stored_hash = self.data["password_hash"]
        except (KeyError, ValueError, TypeError) as exc:
            raise FaceAuthError(
                "The local password data is invalid."
            ) from exc
        candidate = _password_digest(password, salt)
        return hmac.compare_digest(candidate, stored_hash)

    def change_password(self, current_password, new_password):
        if not self.verify_password(current_password):
            raise FaceAuthError("The current password is incorrect.")
        _validate_password(new_password)
        salt = os.urandom(16)
        self.data["password_salt"] = salt.hex()
        self.data["password_hash"] = _password_digest(new_password, salt)
        self._save()

    def add_or_update_person(self, name, profile, embedding, person_id=None):
        if not self.data:
            raise FaceAuthError("Face authentication is not set up.")
        name = name.strip()
        if not name:
            raise FaceAuthError("Enter the person's name.")
        embedding = self._validate_embedding(embedding)

        if person_id:
            person = next(
                (user for user in self.data["users"] if user["id"] == person_id),
                None,
            )
            if person is None:
                raise FaceAuthError("The selected person no longer exists.")
            person["name"] = name
            person["profile"] = profile.strip()
            person["embeddings"].append(embedding)
        else:
            duplicate = next(
                (
                    user for user in self.data["users"]
                    if user["name"].casefold() == name.casefold()
                ),
                None,
            )
            if duplicate:
                raise FaceAuthError(
                    "That name already exists. Select it to add another face sample."
                )
            self.data["users"].append({
                "id": str(uuid.uuid4()),
                "name": name,
                "profile": profile.strip(),
                "embeddings": [embedding],
            })
        self._save()

    def remove_person(self, person_id):
        if not self.data:
            raise FaceAuthError("Face authentication is not set up.")
        if person_id == self.data["owner_id"]:
            raise FaceAuthError(
                "The owner cannot be removed. Change the owner profile instead."
            )
        remaining = [
            user for user in self.data["users"]
            if user["id"] != person_id
        ]
        if len(remaining) == len(self.data["users"]):
            raise FaceAuthError("The selected person no longer exists.")
        self.data["users"] = remaining
        self._save()

    def identify(self, embedding):
        if not self.data:
            return None
        candidate = self._validate_embedding(embedding)
        candidate_norm = math.sqrt(sum(value * value for value in candidate))
        if candidate_norm == 0:
            return None

        best_user = None
        best_score = -1.0
        for user in self.data["users"]:
            for known_embedding in user.get("embeddings", []):
                known = self._validate_embedding(known_embedding)
                known_norm = math.sqrt(sum(value * value for value in known))
                if known_norm == 0:
                    continue
                score = sum(
                    left * right for left, right in zip(candidate, known)
                ) / (candidate_norm * known_norm)
                if score > best_score:
                    best_user = user
                    best_score = score

        if best_user and best_score >= FACE_MATCH_THRESHOLD:
            return {
                "id": best_user["id"],
                "name": best_user["name"],
                "profile": best_user.get("profile", ""),
                "score": best_score,
            }
        return None


class FaceEngine:
    """CPU-only YuNet/SFace face detector and embedding extractor."""

    def __init__(self, model_dir=None):
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise FaceAuthError(
                "Face authentication needs OpenCV. Install it with "
                "'pip install -r requirements-face-auth.txt'."
            ) from exc

        self.cv2 = cv2
        self.np = np
        self.model_dir = Path(model_dir or (_app_data_dir() / "models"))
        self.model_dir.mkdir(parents=True, exist_ok=True)
        model_paths = {
            name: self._ensure_model(name, url)
            for name, url in MODEL_URLS.items()
        }

        try:
            self.detector = cv2.FaceDetectorYN.create(
                str(model_paths["yunet.onnx"]),
                "",
                (320, 320),
                0.85,
                0.3,
                5000,
            )
            self.recognizer = cv2.FaceRecognizerSF.create(
                str(model_paths["sface_int8.onnx"]),
                "",
            )
        except cv2.error as exc:
            raise FaceAuthError(
                f"Could not initialize local face models: {exc}"
            ) from exc

    def _ensure_model(self, filename, url):
        model_path = self.model_dir / filename
        if model_path.exists() and model_path.stat().st_size > 10_000:
            return model_path

        temporary_path = model_path.with_suffix(model_path.suffix + ".tmp")
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Jarvis-Face-Auth"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                with temporary_path.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
            if temporary_path.stat().st_size <= 10_000:
                raise FaceAuthError(
                    f"Downloaded face model '{filename}' is incomplete."
                )
            os.replace(temporary_path, model_path)
        except FaceAuthError:
            if temporary_path.exists():
                temporary_path.unlink()
            raise
        except (OSError, urllib.error.URLError) as exc:
            if temporary_path.exists():
                temporary_path.unlink()
            raise FaceAuthError(
                f"Could not download the local face model '{filename}': {exc}"
            ) from exc
        return model_path

    def extract_embedding(self, frame):
        height, width = frame.shape[:2]
        try:
            self.detector.setInputSize((width, height))
            _, faces = self.detector.detect(frame)
        except self.cv2.error as exc:
            raise FaceAuthError(
                f"Could not detect a face: {exc}"
            ) from exc
        if faces is None or len(faces) != 1:
            return None

        try:
            aligned_face = self.recognizer.alignCrop(frame, faces[0])
            feature = self.recognizer.feature(aligned_face)
        except self.cv2.error as exc:
            raise FaceAuthError(
                f"Could not extract a face embedding: {exc}"
            ) from exc
        return feature.reshape(-1).astype(self.np.float32).tolist()


def open_camera(cv2):
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not camera.isOpened():
        camera.release()
        camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        camera.release()
        return None
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return camera
