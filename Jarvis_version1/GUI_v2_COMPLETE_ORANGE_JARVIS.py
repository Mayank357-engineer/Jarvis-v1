"""
J.A.R.V.I.S v1 - Movie-Inspired Holographic GUI
PySide6 + PyOpenGL + psutil

Run:
    python GUI_v2_COMPLETE.py

Install:
    pip install PySide6 PyOpenGL psutil
    pip install -r requirements-face-auth.txt

Important:
- The GUI keeps your existing main.py as the Offline brain.
- main.py already provides processCommand(), speak(), and recognizeVoice().
- main.py starts the LFM2.5 server when imported in the current project,
  so the GUI imports it only when the user actually uses the Offline brain.
- Face models are downloaded once and cached locally on first startup.
- The 3D core is amber/orange and pulses while Jarvis is speaking.
"""

import sys
import time
import math
import threading
import traceback
from datetime import datetime
from collections import deque
from enum import Enum
from pathlib import Path

import jarvis_settings
from face_auth import (
    FaceAuthError,
    FaceAuthStore,
    FaceEngine,
    open_camera,
)
import psutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QComboBox, QFrame,
    QScrollArea, QDialog, QFormLayout, QPlainTextEdit, QListWidget,
    QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont, QImage, QPixmap, QTextCursor
from PySide6.QtOpenGLWidgets import QOpenGLWidget

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from OpenGL.GL import *
    from OpenGL.GLU import *
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False
    print("PyOpenGL not installed. Run: pip install PyOpenGL")


# ============================================================
# STATES
# ============================================================

class BrainMode(Enum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"


class STTMode(Enum):
    LOCAL = "LOCAL"
    CLOUD = "CLOUD"


class ProcessingState(Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


# ============================================================
# HARDWARE MONITOR
# ============================================================

class HardwareMonitor:
    def get_cpu_percent(self):
        return psutil.cpu_percent(interval=0.05)

    def get_memory_info(self):
        mem = psutil.virtual_memory()
        return mem.percent, f"{mem.used / 1024**3:.1f}GB / {mem.total / 1024**3:.1f}GB"

    def get_disk_info(self):
        disk = psutil.disk_usage('/')
        return disk.percent, f"{disk.used / 1024**3:.1f}GB / {disk.total / 1024**3:.1f}GB"

    def get_disk_speed(self):
        try:
            io = psutil.disk_io_counters()
            if not io:
                return "N/A"
            return f"{(io.read_bytes + io.write_bytes) / 1024**2:.0f} MB/s"
        except Exception:
            return "N/A"

    def get_temp(self):
        try:
            temps = psutil.sensors_temperatures()
            if "coretemp" in temps and temps["coretemp"]:
                return f"{temps['coretemp'][0].current:.0f}°C"
            if "acpitz" in temps and temps["acpitz"]:
                return f"{temps['acpitz'][0].current:.0f}°C"
        except Exception:
            pass
        return "N/A"


# ============================================================
# 3D JARVIS CORE
# ============================================================

class JarvisCore(QOpenGLWidget):
    """
    Movie-inspired 3D holographic AI core.

    IDLE:
        slow rotation + breathing

    LISTENING:
        brighter outer rings

    PROCESSING:
        faster rotating rings

    SPEAKING:
        central core expands/contracts rhythmically
        and the whole hologram gets brighter.
    """

    def __init__(self):
        super().__init__()

        self.rotation = 0.0
        self.rotation2 = 0.0
        self.pulse = 1.0
        self.target_pulse = 1.0
        self.mode = "IDLE"
        self.frame = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

        self.setMinimumSize(420, 480)

    def initializeGL(self):
        if not OPENGL_AVAILABLE:
            return

        glClearColor(0.005, 0.008, 0.012, 1.0)

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        glDisable(GL_CULL_FACE)

    def resizeGL(self, w, h):
        if not OPENGL_AVAILABLE:
            return

        glViewport(0, 0, max(w, 1), max(h, 1))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()

        aspect = w / max(h, 1)
        gluPerspective(38.0, aspect, 0.1, 100.0)

        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        if not OPENGL_AVAILABLE:
            return

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glTranslatef(0.0, 0.0, -5.2)

        # Main rotation.
        glRotatef(self.rotation, 0.0, 1.0, 0.0)
        glRotatef(math.sin(self.frame * 0.008) * 8.0, 1.0, 0.0, 0.0)

        pulse = self.pulse

        self.draw_holographic_core(pulse)

    def set_mode(self, mode):
        self.mode = mode.upper()

    def set_speaking(self, speaking):
        self.mode = "SPEAKING" if speaking else "IDLE"

    def animate(self):
        self.frame += 1

        if self.mode == "PROCESSING":
            self.rotation += 1.6
            self.rotation2 -= 1.0
        elif self.mode == "LISTENING":
            self.rotation += 0.9
            self.rotation2 -= 0.5
        else:
            self.rotation += 0.35
            self.rotation2 -= 0.25

        if self.mode == "SPEAKING":
            # Strong "voice vibration" without looking like a simple scale.
            wave = (
                math.sin(self.frame * 0.38) * 0.060
                + math.sin(self.frame * 0.73) * 0.025
            )
            self.target_pulse = 1.0 + wave
        elif self.mode == "LISTENING":
            self.target_pulse = 1.025 + math.sin(self.frame * 0.10) * 0.015
        elif self.mode == "PROCESSING":
            self.target_pulse = 1.02 + math.sin(self.frame * 0.16) * 0.012
        else:
            self.target_pulse = 1.0 + math.sin(self.frame * 0.035) * 0.008

        self.pulse += (self.target_pulse - self.pulse) * 0.22
        self.update()

    def _ring(self, radius, y=0.0, tilt_x=0.0, tilt_z=0.0,
              segments=160, alpha=0.45, width=1.0, color="amber"):

        glPushMatrix()

        glRotatef(tilt_x, 1, 0, 0)
        glRotatef(tilt_z, 0, 0, 1)

        if color == "cyan":
            glColor4f(0.05, 0.65, 1.0, alpha)
        else:
            glColor4f(1.0, 0.38, 0.035, alpha)

        glLineWidth(width)

        glBegin(GL_LINE_LOOP)

        for i in range(segments):
            a = (2.0 * math.pi * i) / segments
            x = radius * math.cos(a)
            z = radius * math.sin(a)
            glVertex3f(x, y, z)

        glEnd()
        glPopMatrix()

    def draw_holographic_core(self, pulse):
        # ----------------------------------------------------
        # Large soft amber shell
        # ----------------------------------------------------
        for radius, alpha in [
            (1.34, 0.035),
            (1.27, 0.055),
            (1.20, 0.080),
        ]:
            glColor4f(1.0, 0.25, 0.015, alpha)
            self.draw_wire_sphere(radius * pulse, 22, 36, 0.6)

        # ----------------------------------------------------
        # Main 3D cage
        # ----------------------------------------------------
        glColor4f(1.0, 0.42, 0.025, 0.42)
        glLineWidth(1.15)
        self.draw_wire_sphere(1.0 * pulse, 30, 44, 1.0)

        glColor4f(1.0, 0.70, 0.12, 0.22)
        self.draw_wire_sphere(0.86 * pulse, 18, 32, 0.7)

        # ----------------------------------------------------
        # Inner bright core
        # ----------------------------------------------------
        glColor4f(1.0, 0.80, 0.30, 0.28)
        self.draw_wire_sphere(0.48 * pulse, 16, 24, 0.55)

        glColor4f(1.0, 0.93, 0.62, 0.18)
        self.draw_wire_sphere(0.25 * pulse, 12, 20, 0.4)

        # ----------------------------------------------------
        # Central vertical energy structure
        # ----------------------------------------------------
        self.draw_energy_spine(pulse)

        # ----------------------------------------------------
        # Multiple holographic rings
        # ----------------------------------------------------
        self._ring(
            1.48 * pulse,
            tilt_x=68,
            tilt_z=self.rotation2 * 0.7,
            alpha=0.22,
            width=1.0
        )

        self._ring(
            1.31 * pulse,
            tilt_x=22,
            tilt_z=self.rotation * 0.4,
            alpha=0.34,
            width=1.2
        )

        self._ring(
            1.12 * pulse,
            tilt_x=90,
            tilt_z=self.rotation2,
            alpha=0.46,
            width=1.5
        )

        self._ring(
            0.72 * pulse,
            tilt_x=0,
            tilt_z=self.rotation * 0.7,
            alpha=0.48,
            width=1.3
        )

        # ----------------------------------------------------
        # Segmented "reactor" rings
        # ----------------------------------------------------
        self.draw_segmented_ring(
            1.58 * pulse,
            0.0,
            52,
            self.rotation * 1.2,
            0.55
        )

        self.draw_segmented_ring(
            1.38 * pulse,
            0.0,
            36,
            -self.rotation * 1.6,
            0.70
        )

        # ----------------------------------------------------
        # Orbital arcs
        # ----------------------------------------------------
        self.draw_orbit_arc(1.62 * pulse, 28, self.rotation * 0.8)
        self.draw_orbit_arc(1.50 * pulse, -35, -self.rotation * 0.9)

        # ----------------------------------------------------
        # Floating radial data marks
        # ----------------------------------------------------
        self.draw_radial_marks(1.75 * pulse)

        # ----------------------------------------------------
        # Tiny secondary cyan scan ring.
        # Keep cyan secondary; amber remains dominant.
        # ----------------------------------------------------
        self._ring(
            1.70 * pulse,
            tilt_x=90,
            tilt_z=-self.rotation * 0.25,
            alpha=0.12,
            width=1.0,
            color="cyan"
        )

    def draw_wire_sphere(self, radius, stacks, slices, alpha_scale=1.0):
        for lat in range(1, stacks):
            phi = math.pi * lat / stacks
            y = radius * math.cos(phi)
            ring_radius = radius * math.sin(phi)

            glBegin(GL_LINE_LOOP)

            for lon in range(slices):
                theta = 2.0 * math.pi * lon / slices
                x = ring_radius * math.cos(theta)
                z = ring_radius * math.sin(theta)
                glVertex3f(x, y, z)

            glEnd()

        # Longitude curves.
        for lon in range(0, slices, max(1, slices // 12)):
            theta = 2.0 * math.pi * lon / slices

            glBegin(GL_LINE_STRIP)

            for lat in range(stacks + 1):
                phi = math.pi * lat / stacks
                x = radius * math.sin(phi) * math.cos(theta)
                y = radius * math.cos(phi)
                z = radius * math.sin(phi) * math.sin(theta)
                glVertex3f(x, y, z)

            glEnd()

    def draw_segmented_ring(self, radius, y, count, rotation, alpha):
        glPushMatrix()
        glRotatef(rotation, 0, 1, 0)
        glRotatef(65, 1, 0, 0)

        glColor4f(1.0, 0.48, 0.05, alpha)
        glLineWidth(2.0)

        gap = 0.10

        for i in range(count):
            start = (2 * math.pi * i) / count
            end = (2 * math.pi * (i + 0.72)) / count

            glBegin(GL_LINE_STRIP)

            steps = 8

            for j in range(steps + 1):
                a = start + (end - start) * j / steps
                glVertex3f(
                    radius * math.cos(a),
                    y,
                    radius * math.sin(a)
                )

            glEnd()

        glPopMatrix()

    def draw_orbit_arc(self, radius, tilt, rotation):
        glPushMatrix()
        glRotatef(tilt, 1, 0, 0)
        glRotatef(rotation, 0, 1, 0)

        glColor4f(1.0, 0.58, 0.10, 0.40)
        glLineWidth(1.5)

        glBegin(GL_LINE_STRIP)

        # Three-quarter arc.
        for i in range(121):
            a = math.radians(-35 + i * 270 / 120)
            glVertex3f(
                radius * math.cos(a),
                0,
                radius * math.sin(a)
            )

        glEnd()
        glPopMatrix()

    def draw_energy_spine(self, pulse):
        glColor4f(1.0, 0.85, 0.45, 0.55)
        glLineWidth(2.0)

        glBegin(GL_LINES)

        glVertex3f(0, -0.82 * pulse, 0)
        glVertex3f(0, 0.82 * pulse, 0)

        glVertex3f(-0.45 * pulse, 0, 0)
        glVertex3f(0.45 * pulse, 0, 0)

        glVertex3f(0, 0, -0.45 * pulse)
        glVertex3f(0, 0, 0.45 * pulse)

        glEnd()

    def draw_radial_marks(self, radius):
        glColor4f(1.0, 0.45, 0.06, 0.30)
        glLineWidth(1.0)

        glBegin(GL_LINES)

        for i in range(24):
            a = 2 * math.pi * i / 24

            x1 = radius * math.cos(a)
            z1 = radius * math.sin(a)

            r2 = radius + (0.10 if i % 3 == 0 else 0.045)

            x2 = r2 * math.cos(a)
            z2 = r2 * math.sin(a)

            glVertex3f(x1, 0, z1)
            glVertex3f(x2, 0, z2)

        glEnd()


# ============================================================
# SIGNALS
# ============================================================

class Signals(QObject):
    command_done = Signal(str, object)
    command_error = Signal(str, object)
    voice_result = Signal(str)
    voice_error = Signal(str)
    speaking = Signal(bool)
    system_log = Signal(str)


class _FaceCameraDialog(QDialog):
    def __init__(self, engine, title, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.cv2 = engine.cv2
        self.camera = open_camera(self.cv2)
        self.latest_frame = None

        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        self.preview = QLabel("Camera unavailable")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(440, 300)
        self.preview.setStyleSheet(
            "background: #061018; border: 1px solid #25414a;"
        )
        layout.addWidget(self.preview)
        self.camera_status = QLabel()
        layout.addWidget(self.camera_status)

        self.camera_timer = QTimer(self)
        self.camera_timer.timeout.connect(self._update_camera)
        if self.camera is not None:
            self.camera_timer.start(100)
            self.camera_status.setText(
                "Face processing is local. Use good lighting and face the camera."
            )
        else:
            self.camera_status.setText(
                "Camera unavailable. Check the camera connection and permissions."
            )

    def _update_camera(self):
        if self.camera is None:
            return
        ok, frame = self.camera.read()
        if not ok:
            self.camera_status.setText(
                "Camera frame unavailable. Check the camera connection."
            )
            return
        self.latest_frame = frame
        rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        image = QImage(
            rgb.data,
            rgb.shape[1],
            rgb.shape[0],
            rgb.strides[0],
            QImage.Format_RGB888,
        ).copy()
        self.preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                self.preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def closeEvent(self, event):
        self._release_camera()
        super().closeEvent(event)

    def done(self, result):
        self._release_camera()
        super().done(result)

    def _release_camera(self):
        self.camera_timer.stop()
        if self.camera is not None:
            self.camera.release()
            self.camera = None


class FaceSetupDialog(_FaceCameraDialog):
    def __init__(self, store, engine, parent=None):
        super().__init__(engine, "Jarvis - First-time Face Setup", parent)
        self.store = store
        self.authenticated_person = None

        layout = self.layout()
        details = QFormLayout()
        self.name_input = QLineEdit()
        self.profile_input = QPlainTextEdit()
        self.profile_input.setPlaceholderText(
            "Optional facts Jarvis can use for this person in OFFLINE mode."
        )
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        details.addRow("Owner name:", self.name_input)
        details.addRow("Profile for local Jarvis:", self.profile_input)
        details.addRow("Fallback password:", self.password_input)
        details.addRow("Confirm password:", self.confirm_password_input)
        layout.addLayout(details)

        warning = QLabel(
            "First setup enrolls the owner. Face matching is a convenience "
            "lock and may be spoofed by a photo or video."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        buttons = QHBoxLayout()
        self.enroll_button = QPushButton("ENROLL OWNER")
        self.cancel_button = QPushButton("EXIT")
        buttons.addWidget(self.enroll_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.enroll_button.clicked.connect(self._enroll_owner)
        self.cancel_button.clicked.connect(self.reject)

    def _enroll_owner(self):
        if self.latest_frame is None:
            QMessageBox.warning(
                self, "Camera required", "A camera frame is required to enroll."
            )
            return
        if self.password_input.text() != self.confirm_password_input.text():
            QMessageBox.warning(
                self, "Password mismatch", "The passwords do not match."
            )
            return
        try:
            embedding = self.engine.extract_embedding(self.latest_frame)
            if embedding is None:
                QMessageBox.warning(
                    self,
                    "Face not found",
                    "Show exactly one clear face in the camera preview.",
                )
                return
            self.authenticated_person = self.store.setup_owner(
                self.name_input.text(),
                self.profile_input.toPlainText(),
                self.password_input.text(),
                embedding,
            )
        except FaceAuthError as exc:
            QMessageBox.warning(self, "Setup failed", str(exc))
            return
        self.accept()


class FaceUnlockDialog(_FaceCameraDialog):
    def __init__(self, store, engine, parent=None):
        super().__init__(engine, "Jarvis - Unlock", parent)
        self.store = store
        self.authenticated_person = None
        self._frames_since_check = 0
        self._stable_person_id = None
        self._stable_match_count = 0
        self._password_attempts = 0

        layout = self.layout()
        self.status = QLabel("Look at the camera or use your fallback password.")
        layout.addWidget(self.status)
        security_note = QLabel(
            "Face matching is a convenience lock and may be spoofed by a photo or video."
        )
        security_note.setWordWrap(True)
        layout.addWidget(security_note)
        form = QFormLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Fallback password")
        form.addRow("Password:", self.password_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.password_button = QPushButton("UNLOCK WITH PASSWORD")
        self.exit_button = QPushButton("EXIT JARVIS")
        buttons.addWidget(self.password_button)
        buttons.addWidget(self.exit_button)
        layout.addLayout(buttons)
        self.password_button.clicked.connect(self._unlock_with_password)
        self.exit_button.clicked.connect(self.reject)

    def _update_camera(self):
        super()._update_camera()
        if self.latest_frame is None:
            return
        self._frames_since_check += 1
        if self._frames_since_check < 3:
            return
        self._frames_since_check = 0
        try:
            embedding = self.engine.extract_embedding(self.latest_frame)
            match = self.store.identify(embedding) if embedding else None
        except FaceAuthError as exc:
            self.status.setText(f"Face check failed: {exc}")
            return

        if match is None:
            self._stable_person_id = None
            self._stable_match_count = 0
            if self.camera is not None:
                self.status.setText(
                    "No enrolled face recognized. Enter the fallback password."
                )
            return

        if match["id"] == self._stable_person_id:
            self._stable_match_count += 1
        else:
            self._stable_person_id = match["id"]
            self._stable_match_count = 1

        self.status.setText(f"Recognized {match['name']} - verifying...")
        if self._stable_match_count >= 4:
            self.authenticated_person = match
            self.status.setText(f"Welcome, {match['name']}.")
            self.accept()

    def _unlock_with_password(self):
        try:
            if self.store.verify_password(self.password_input.text()):
                self.authenticated_person = self.store.owner
                self.accept()
                return
        except FaceAuthError as exc:
            QMessageBox.critical(self, "Authentication error", str(exc))
            return

        self._password_attempts += 1
        self.password_input.clear()
        if self._password_attempts >= 5:
            self.password_button.setEnabled(False)
            self.status.setText("Too many attempts. Password unlock paused for 15 seconds.")
            QTimer.singleShot(
                15_000,
                lambda: self.password_button.setEnabled(True),
            )
            self._password_attempts = 0
        else:
            self.status.setText("Password not accepted. Try again.")


class FaceManagementDialog(_FaceCameraDialog):
    def __init__(self, store, engine, current_person_id, parent=None):
        super().__init__(engine, "Jarvis — Manage Faces", parent)
        self.setMinimumWidth(720)
        self.store = store
        self.current_person_id = current_person_id

        layout = self.layout()
        self.people_list = QListWidget()
        layout.addWidget(self.people_list)
        details = QFormLayout()
        self.name_input = QLineEdit()
        self.profile_input = QPlainTextEdit()
        self.profile_input.setPlaceholderText(
            "Optional facts sent only to the OFFLINE LFM brain."
        )
        details.addRow("Name:", self.name_input)
        details.addRow("Local Jarvis profile:", self.profile_input)
        layout.addLayout(details)

        buttons = QHBoxLayout()
        self.new_button = QPushButton("NEW PERSON")
        self.save_button = QPushButton("SAVE / ADD FACE SAMPLE")
        self.remove_button = QPushButton("REMOVE SELECTED")
        self.password_button = QPushButton("CHANGE FALLBACK PASSWORD")
        self.done_button = QPushButton("DONE")
        for button in (
            self.new_button,
            self.save_button,
            self.remove_button,
            self.password_button,
            self.done_button,
        ):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.people_list.currentRowChanged.connect(self._select_person)
        self.new_button.clicked.connect(self._new_person)
        self.save_button.clicked.connect(self._save_person)
        self.remove_button.clicked.connect(self._remove_person)
        self.password_button.clicked.connect(self._change_password)
        self.done_button.clicked.connect(self.accept)
        self._refresh_people()

    def _refresh_people(self, selected_id=None):
        self.people_list.clear()
        users = self.store.users
        selected_row = 0
        for row, person in enumerate(users):
            label = person["name"]
            if person["id"] == self.store.data["owner_id"]:
                label += " (owner)"
            self.people_list.addItem(label)
            self.people_list.item(row).setData(Qt.UserRole, person["id"])
            if person["id"] == selected_id:
                selected_row = row
        if users:
            self.people_list.setCurrentRow(selected_row)

    def _selected_person(self):
        item = self.people_list.currentItem()
        if item is None:
            return None
        return next(
            (
                person for person in self.store.users
                if person["id"] == item.data(Qt.UserRole)
            ),
            None,
        )

    def _select_person(self, row):
        if row < 0:
            return
        person = self._selected_person()
        if person is None:
            return
        self.name_input.setText(person["name"])
        self.profile_input.setPlainText(person.get("profile", ""))

    def _new_person(self):
        self.people_list.setCurrentRow(-1)
        self.name_input.clear()
        self.profile_input.clear()
        self.name_input.setFocus()

    def _save_person(self):
        if self.latest_frame is None:
            QMessageBox.warning(
                self, "Camera required", "A camera frame is required to enroll."
            )
            return
        try:
            embedding = self.engine.extract_embedding(self.latest_frame)
            if embedding is None:
                QMessageBox.warning(
                    self,
                    "Face not found",
                    "Show exactly one clear face in the camera preview.",
                )
                return
            selected = self._selected_person()
            self.store.add_or_update_person(
                self.name_input.text(),
                self.profile_input.toPlainText(),
                embedding,
                selected["id"] if selected else None,
            )
            updated = next(
                user for user in self.store.users
                if user["name"].casefold() == self.name_input.text().strip().casefold()
            )
            self._refresh_people(updated["id"])
            self.camera_status.setText(
                f"Saved local face sample for {updated['name']}."
            )
        except (FaceAuthError, StopIteration) as exc:
            QMessageBox.warning(self, "Enrollment failed", str(exc))

    def _remove_person(self):
        person = self._selected_person()
        if person is None:
            return
        if person["id"] == self.current_person_id:
            QMessageBox.warning(
                self,
                "Cannot remove current person",
                "The signed-in person cannot be removed during this session.",
            )
            return
        if QMessageBox.question(
            self,
            "Remove face",
            f"Remove {person['name']}'s face profile?",
        ) != QMessageBox.Yes:
            return
        try:
            self.store.remove_person(person["id"])
        except FaceAuthError as exc:
            QMessageBox.warning(self, "Could not remove face", str(exc))
            return
        self._refresh_people()

    def _change_password(self):
        current, accepted = QInputDialog.getText(
            self,
            "Change fallback password",
            "Current password:",
            QLineEdit.Password,
        )
        if not accepted:
            return
        new_password, accepted = QInputDialog.getText(
            self,
            "Change fallback password",
            "New password (at least 8 characters):",
            QLineEdit.Password,
        )
        if not accepted:
            return
        confirmation, accepted = QInputDialog.getText(
            self,
            "Change fallback password",
            "Confirm new password:",
            QLineEdit.Password,
        )
        if not accepted:
            return
        if new_password != confirmation:
            QMessageBox.warning(
                self, "Password mismatch", "The passwords do not match."
            )
            return
        try:
            self.store.change_password(current, new_password)
        except FaceAuthError as exc:
            QMessageBox.warning(self, "Password not changed", str(exc))
            return
        QMessageBox.information(
            self, "Password changed", "The fallback password was updated."
        )


# ============================================================
# JARVIS CORE WORKER
# ============================================================

class JarvisWorker:
    """
    Small adapter around your existing main.py.

    We intentionally call:
        main.processCommand(command)

    because that is the function present in your existing main.py.
    """

    def __init__(self, signals):
        self.signals = signals
        self.jarvis_main = None
        self._original_speak = None

    def load_main(self):
        if self.jarvis_main is not None:
            return self.jarvis_main

        sys.path.insert(0, str(Path(__file__).parent))

        import main as jarvis_main

        self.jarvis_main = jarvis_main

        # Wrap main.speak() so the GUI knows the exact time
        # when your real Jarvis TTS starts and stops.
        if hasattr(jarvis_main, "speak"):
            self._original_speak = jarvis_main.speak

            def gui_speak(text):
                self.signals.speaking.emit(True)
                try:
                    return self._original_speak(text)
                finally:
                    self.signals.speaking.emit(False)

            jarvis_main.speak = gui_speak

        return jarvis_main

    def process_offline(self, command):
        jarvis = self.load_main()

        if not hasattr(jarvis, "processCommand"):
            raise AttributeError(
                "main.py does not contain processCommand()."
            )

        result = jarvis.processCommand(command)

        if result is None:
            return "Command completed."

        return str(result)

    def speak_online(self, text):
        jarvis = self.load_main()

        if hasattr(jarvis, "speak"):
            jarvis.speak(text)


# ============================================================
# MAIN GUI
# ============================================================

class JarvisGUI(QMainWindow):

    def __init__(self, authenticated_person, face_store, face_engine):
        super().__init__()

        self.setWindowTitle(
            "J.A.R.V.I.S v1 - Offline-First Voice Assistant"
        )

        self.resize(1500, 900)
        self.setMinimumSize(1200, 760)

        self.state = ProcessingState.IDLE
        self.brain_mode = BrainMode(jarvis_settings.BRAIN_MODE)
        self.stt_mode = STTMode(jarvis_settings.STT_MODE)

        self.activity_log = deque(maxlen=50)
        self.command_history = deque(maxlen=50)

        self.signals = Signals()
        self.core = None

        self.command_running = False
        self.listening = False
        self.active_command_cancel = None
        self.authenticated_person = authenticated_person
        self.face_store = face_store
        self.face_engine = face_engine

        self.worker = JarvisWorker(self.signals)

        self._setup_theme()
        self._build_ui()
        self._connect_signals()

        self.hw_monitor = HardwareMonitor()

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(
            self._update_hardware_stats
        )
        self.update_timer.start(1000)

        self._log_activity("SYSTEM BOOT")
        self._log_activity("JARVIS CORE INITIALIZED")
        self._log_activity("READY FOR INPUT")

    # ========================================================
    # THEME
    # ========================================================

    def _setup_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #03070b;
            }

            QWidget {
                background: #03070b;
                color: #dcecf0;
                font-family: Consolas;
            }

            QFrame {
                background: rgba(3, 10, 15, 230);
                border: 1px solid #17313a;
                border-radius: 3px;
            }

            QLabel {
                background: transparent;
                border: none;
            }

            QLineEdit, QTextEdit {
                background: #061018;
                color: #e8f8fb;
                border: 1px solid #25414a;
                padding: 8px;
                border-radius: 2px;
                selection-background-color: #5a3210;
            }

            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #ff8a1c;
            }

            QPushButton {
                background: #08141b;
                color: #ff9a32;
                border: 1px solid #b45d13;
                padding: 9px 13px;
                border-radius: 2px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #1a160f;
                border: 1px solid #ff9a32;
                color: #ffc078;
            }

            QPushButton:pressed {
                background: #251608;
            }

            QPushButton:disabled {
                color: #53636a;
                border-color: #29343a;
            }

            QComboBox {
                background: #071118;
                color: #ff9a32;
                border: 1px solid #6e3d13;
                padding: 7px;
                border-radius: 2px;
            }

            QComboBox:hover {
                border-color: #ff9a32;
            }

            QScrollArea {
                border: 1px solid #17313a;
                background: #03070b;
            }

            QScrollBar:vertical {
                width: 8px;
                background: #061018;
            }

            QScrollBar::handle:vertical {
                background: #704016;
                border-radius: 4px;
            }

            QStatusBar {
                background: #020508;
                color: #8aa1a8;
                border-top: 1px solid #172a31;
            }
        """)

    # ========================================================
    # BUILD UI
    # ========================================================

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 4)
        root.setSpacing(6)

        # Top title bar.
        top = QFrame()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(14, 8, 14, 8)

        title = QLabel("J.A.R.V.I.S")
        title.setFont(QFont("Consolas", 20, QFont.Bold))
        title.setStyleSheet(
            "color: #ff9a32; letter-spacing: 2px;"
        )

        version = QLabel(
            "v1  //  JUST A RATHER VERY INTELLIGENT SYSTEM"
        )
        version.setStyleSheet(
            "color: #77919a; font-size: 9px;"
        )

        self.top_status = QLabel("● ALL SYSTEMS READY")
        self.top_status.setStyleSheet(
            "color: #ff9a32; font-size: 9px; font-weight: bold;"
        )

        top_layout.addWidget(title)
        top_layout.addSpacing(12)
        top_layout.addWidget(version)
        top_layout.addStretch()
        top_layout.addWidget(self.top_status)

        root.addWidget(top)

        # Main three-column area.
        columns = QHBoxLayout()
        columns.setSpacing(7)

        left = self._create_left_panel()
        center = self._create_center_panel()
        right = self._create_right_panel()

        columns.addWidget(left, 22)
        columns.addWidget(center, 56)
        columns.addWidget(right, 22)

        root.addLayout(columns, 1)

        self.statusBar().showMessage(
            "JARVIS // READY"
        )

    # ========================================================
    # LEFT PANEL
    # ========================================================

    def _create_left_panel(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        title = QLabel("SYSTEMS")
        title.setFont(QFont("Consolas", 12, QFont.Bold))
        title.setStyleSheet("color: #e9f5f7;")
        layout.addWidget(title)

        self.face_management_button = QPushButton("MANAGE FACES")
        self.face_management_button.clicked.connect(
            self._open_face_management
        )
        layout.addWidget(self.face_management_button)

        # Brain.
        layout.addWidget(self._section_label("BRAIN MODE"))

        brain_row = QHBoxLayout()

        self.brain_combo = QComboBox()
        self.brain_combo.addItems(["OFFLINE", "ONLINE"])
        self.brain_combo.setCurrentText(jarvis_settings.BRAIN_MODE)
        self.brain_combo.currentTextChanged.connect(
            self._on_brain_mode_changed
        )

        self.brain_info = QLabel(
            "GEMINI ONLINE"
            if self.brain_mode == BrainMode.ONLINE
            else "LFM2.5 LOCAL"
        )
        self.brain_info.setStyleSheet(
            "color: #ff9a32; font-size: 8px;"
        )

        brain_row.addWidget(self.brain_combo, 1)
        brain_row.addWidget(self.brain_info)

        layout.addLayout(brain_row)

        # STT.
        layout.addWidget(
            self._section_label("SPEECH-TO-TEXT")
        )

        stt_row = QHBoxLayout()

        self.stt_combo = QComboBox()
        self.stt_combo.addItems(["LOCAL", "CLOUD"])
        self.stt_combo.setCurrentText(jarvis_settings.STT_MODE)
        self.stt_combo.currentTextChanged.connect(
            self._on_stt_mode_changed
        )

        self.stt_info = QLabel(
            "WHISPER BASE"
            if self.stt_mode == STTMode.LOCAL
            else "CLOUD"
        )
        self.stt_info.setStyleSheet(
            "color: #ff9a32; font-size: 8px;"
        )

        stt_row.addWidget(self.stt_combo, 1)
        stt_row.addWidget(self.stt_info)

        layout.addLayout(stt_row)

        layout.addSpacing(12)

        layout.addWidget(
            self._section_label("HARDWARE")
        )

        self.cpu_bar = self._stat_label()
        self.mem_bar = self._stat_label()
        self.disk_bar = self._stat_label()
        self.disk_speed_label = self._stat_label()
        self.temp_label = self._stat_label()

        layout.addWidget(QLabel("CPU"))
        layout.addWidget(self.cpu_bar)

        layout.addWidget(QLabel("MEMORY"))
        layout.addWidget(self.mem_bar)

        layout.addWidget(QLabel("DISK"))
        layout.addWidget(self.disk_bar)

        layout.addWidget(QLabel("DISK SPEED"))
        layout.addWidget(self.disk_speed_label)

        layout.addWidget(QLabel("TEMPERATURE"))
        layout.addWidget(self.temp_label)

        layout.addStretch()

        identity = QLabel(
            "J.A.R.V.I.S\n"
            "ONLINE / OFFLINE CAPABLE\n"
            "VOICE • TOOLS • MEMORY"
        )
        identity.setStyleSheet(
            "color: #7c9198; font-size: 8px;"
        )
        layout.addWidget(identity)

        return frame

    def _section_label(self, text):
        label = QLabel(text)
        label.setFont(QFont("Consolas", 9, QFont.Bold))
        label.setStyleSheet(
            "color: #b8cbd0; "
            "border-bottom: 1px solid #17313a; "
            "padding-bottom: 5px;"
        )
        return label

    def _stat_label(self):
        label = QLabel("░░░░░░░░░░ 0%")
        label.setFont(QFont("Consolas", 8))
        label.setStyleSheet(
            "color: #ff9a32; "
            "padding-bottom: 4px;"
        )
        return label

    # ========================================================
    # CENTER PANEL
    # ========================================================

    def _create_center_panel(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(5)

        header = QHBoxLayout()

        core_title = QLabel("CENTRAL CORE 01")
        core_title.setFont(
            QFont("Consolas", 11, QFont.Bold)
        )
        core_title.setStyleSheet(
            "color: #ff9a32;"
        )

        self.core_mode = QLabel("HOLOGRAPHIC CORE // IDLE")
        self.core_mode.setStyleSheet(
            "color: #718a92; font-size: 8px;"
        )

        header.addWidget(core_title)
        header.addStretch()
        header.addWidget(self.core_mode)

        layout.addLayout(header)

        if OPENGL_AVAILABLE:
            self.core = JarvisCore()
            layout.addWidget(self.core, 1)
        else:
            fallback = QLabel(
                "3D CORE UNAVAILABLE\n\n"
                "Install:\n"
                "pip install PyOpenGL"
            )
            fallback.setAlignment(Qt.AlignCenter)
            fallback.setStyleSheet(
                "color: #ff9a32; font-size: 12px;"
            )
            layout.addWidget(fallback, 1)

        self.core_status = QLabel(
            "JARVIS // READY"
        )
        self.core_status.setAlignment(
            Qt.AlignCenter
        )
        self.core_status.setFont(
            QFont("Consolas", 12, QFont.Bold)
        )
        self.core_status.setStyleSheet(
            "color: #e8f4f6; "
            "padding: 12px;"
        )

        layout.addWidget(self.core_status)

        return frame

    # ========================================================
    # RIGHT PANEL
    # ========================================================

    def _create_right_panel(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)

        activity_title = QLabel("ACTIVITY LOG")
        activity_title.setFont(
            QFont("Consolas", 10, QFont.Bold)
        )
        activity_title.setStyleSheet(
            "color: #e9f5f7;"
        )
        layout.addWidget(activity_title)

        self.activity_text = QTextEdit()
        self.activity_text.setReadOnly(True)
        self.activity_text.setFont(
            QFont("Consolas", 7)
        )
        self.activity_text.setStyleSheet("""
            QTextEdit {
                background: #041018;
                color: #829da5;
                border: 1px solid #17313a;
            }
        """)
        layout.addWidget(
            self.activity_text, 1
        )

        conversation_title = QLabel("CONVERSATION")
        conversation_title.setFont(
            QFont("Consolas", 10, QFont.Bold)
        )
        conversation_title.setStyleSheet(
            "color: #e9f5f7;"
        )
        layout.addWidget(conversation_title)

        self.conversation_text = QTextEdit()
        self.conversation_text.setReadOnly(True)
        self.conversation_text.setFont(
            QFont("Consolas", 8)
        )
        layout.addWidget(
            self.conversation_text, 2
        )

        input_row = QHBoxLayout()

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText(
            "ENTER COMMAND..."
        )
        self.command_input.returnPressed.connect(
            self._on_command_entered
        )

        self.execute_btn = QPushButton(
            "EXECUTE"
        )
        self.execute_btn.clicked.connect(
            self._on_command_entered
        )

        self.voice_btn = QPushButton(
            "VOICE"
        )
        self.voice_btn.clicked.connect(
            self._on_voice_input
        )

        input_row.addWidget(
            self.command_input, 1
        )
        input_row.addWidget(
            self.execute_btn
        )
        input_row.addWidget(
            self.voice_btn
        )

        layout.addLayout(input_row)

        return frame

    # ========================================================
    # SIGNALS
    # ========================================================

    def _connect_signals(self):
        self.signals.command_done.connect(
            self._on_response_ready
        )

        self.signals.command_error.connect(
            self._on_error
        )

        self.signals.voice_result.connect(
            self._on_voice_result
        )

        self.signals.voice_error.connect(
            self._on_voice_error
        )

        self.signals.speaking.connect(
            self._on_speaking_changed
        )

        self.signals.system_log.connect(
            self._log_activity
        )

    # ========================================================
    # HARDWARE
    # ========================================================

    def _update_hardware_stats(self):
        try:
            cpu = self.hw_monitor.get_cpu_percent()
            mem, mem_text = self.hw_monitor.get_memory_info()
            disk, disk_text = self.hw_monitor.get_disk_info()

            self.cpu_bar.setText(
                self._bar(cpu) +
                f" {cpu:.0f}%"
            )

            self.mem_bar.setText(
                self._bar(mem) +
                f" {mem:.0f}% | {mem_text}"
            )

            self.disk_bar.setText(
                self._bar(disk) +
                f" {disk:.0f}% | {disk_text}"
            )

            self.disk_speed_label.setText(
                self.hw_monitor.get_disk_speed()
            )

            self.temp_label.setText(
                self.hw_monitor.get_temp()
            )

        except Exception as e:
            print(
                f"Hardware monitor error: {e}"
            )

    def _bar(self, percent):
        n = max(
            0,
            min(10, int(percent / 10))
        )
        return "█" * n + "░" * (10 - n)

    # ========================================================
    # ACTIVITY
    # ========================================================

    def _log_activity(self, message):
        timestamp = datetime.now().strftime(
            "%H:%M:%S"
        )

        self.activity_log.append(
            f"{timestamp}  {message}"
        )

        if hasattr(
            self,
            "activity_text"
        ):
            self.activity_text.setPlainText(
                "\n".join(
                    self.activity_log
                )
            )

            cursor = (
                self.activity_text.textCursor()
            )
            cursor.movePosition(
                QTextCursor.End
            )
            self.activity_text.setTextCursor(
                cursor
            )

    # ========================================================
    # BRAIN MODE
    # ========================================================

    def _on_brain_mode_changed(self, mode):
        previous_mode = self.brain_mode.value
        if (
            previous_mode == "ONLINE"
            and mode != "ONLINE"
            and self.active_command_cancel is not None
        ):
            self.active_command_cancel.set()
            self.active_command_cancel = None
            self.command_running = False
            self._set_inputs_enabled(True)
            self._log_activity(
                f"STOPPING {previous_mode} BRAIN ACTIVITY"
            )
            self.state = ProcessingState.IDLE

        if mode != "ONLINE" and previous_mode == "ONLINE":
            gemini = sys.modules.get("gemini_UPDATED")
            if gemini is not None:
                try:
                    gemini.shutdown_gemini()
                except Exception as e:
                    self._log_activity(
                        f"GEMINI SHUTDOWN ERROR: {type(e).__name__}: {e}"
                    )

        if mode == "ONLINE":
            if not jarvis_settings.set_brain_mode(mode):
                raise ValueError(f"Unsupported brain mode: {mode}")
            self.brain_mode = BrainMode.ONLINE
            self.brain_info.setText(
                "GEMINI ONLINE"
            )

            self._set_core_state(
                "PROCESSING"
            )

            self._log_activity(
                "ONLINE BRAIN SELECTED (GEMINI)"
            )

            self.core_status.setText(
                "JARVIS // GEMINI"
            )

        else:
            if not jarvis_settings.set_brain_mode(mode):
                raise ValueError(f"Unsupported brain mode: {mode}")
            self.brain_mode = BrainMode.OFFLINE
            self.brain_info.setText(
                "LFM2.5 LOCAL"
            )

            self._set_core_state(
                "IDLE"
            )

            self._log_activity(
                "OFFLINE BRAIN SELECTED (LFM2.5)"
            )

            self.core_status.setText(
                "JARVIS // READY"
            )

    def _on_stt_mode_changed(self, mode):
        if mode == "LOCAL":
            if not jarvis_settings.set_stt_mode(mode):
                raise ValueError(f"Unsupported speech-to-text mode: {mode}")
            self.stt_mode = STTMode.LOCAL
            self.stt_info.setText(
                "WHISPER BASE"
            )
            self._log_activity(
                "STT: LOCAL (WHISPER BASE)"
            )
        else:
            if not jarvis_settings.set_stt_mode(mode):
                raise ValueError(f"Unsupported speech-to-text mode: {mode}")
            self.stt_mode = STTMode.CLOUD
            self.stt_info.setText(
                "CLOUD"
            )
            self._log_activity(
                "STT: CLOUD SELECTED"
            )

    def _open_face_management(self):
        dialog = FaceManagementDialog(
            self.face_store,
            self.face_engine,
            self.authenticated_person["id"],
            self,
        )
        dialog.exec()

        current_person = next(
            (
                person for person in self.face_store.users
                if person["id"] == self.authenticated_person["id"]
            ),
            self.authenticated_person,
        )
        self.authenticated_person = current_person
        jarvis_settings.CURRENT_PERSON_CONTEXT = {
            "name": current_person["name"],
            "profile": current_person.get("profile", ""),
        }

    # ========================================================
    # COMMAND INPUT
    # ========================================================

    def _on_command_entered(self):
        if self.command_running:
            return

        command = (
            self.command_input.text()
            .strip()
        )

        if not command:
            return

        self.command_input.clear()
        self.command_history.append(
            command
        )

        self.conversation_text.append(
            f"YOU  //  {command}"
        )

        self._log_activity(
            f"INPUT: {command[:45]}"
        )

        self._run_command(command)

    def _run_command(self, command):
        if self.command_running:
            return

        self.command_running = True
        cancel_event = threading.Event()
        self.active_command_cancel = cancel_event
        self._set_inputs_enabled(False)

        self.state = (
            ProcessingState.PROCESSING
        )

        self.core_status.setText(
            "JARVIS // PROCESSING"
        )

        self.core_mode.setText(
            "HOLOGRAPHIC CORE // PROCESSING"
        )

        self._set_core_state(
            "PROCESSING"
        )

        thread = threading.Thread(
            target=self._command_worker,
            args=(
                command,
                self.brain_mode,
                cancel_event
            ),
            daemon=True
        )

        thread.start()

    def _command_worker(self, command, brain_mode, cancel_event):
        try:
            if brain_mode == BrainMode.OFFLINE:
                response = (
                    self.worker.process_offline(
                        command
                    )
                )

            else:
                # Import the existing Gemini file only
                # when Online mode is selected.
                import gemini_UPDATED as gemini

                response = gemini.complete(
                    command,
                    cancel_event=cancel_event
                )

                if cancel_event.is_set():
                    return

                # Your Gemini module returns text.
                # Use the same Jarvis TTS for the GUI.
                self.worker.speak_online(
                    str(response)
                )

            if cancel_event.is_set():
                return

            self.signals.command_done.emit(str(response), cancel_event)

        except Exception as e:
            if cancel_event.is_set():
                return

            traceback.print_exc()

            self.signals.command_error.emit(
                f"{type(e).__name__}: {e}",
                cancel_event
            )

    # ========================================================
    # RESPONSE
    # ========================================================

    def _on_response_ready(self, response, cancel_event):
        if (
            cancel_event.is_set()
            or self.active_command_cancel is not cancel_event
        ):
            return

        self.conversation_text.append(
            f"JARVIS  //  {response}"
        )

        self._log_activity(
            f"RESPONSE: {response[:45]}"
        )

        self.command_running = False
        self.active_command_cancel = None
        self.state = ProcessingState.IDLE

        self.core_status.setText(
            "JARVIS // READY"
        )

        self.core_mode.setText(
            "HOLOGRAPHIC CORE // IDLE"
        )

        self._set_core_state(
            "IDLE"
        )

        self._set_inputs_enabled(True)

    def _on_error(self, error, cancel_event):
        if (
            cancel_event.is_set()
            or self.active_command_cancel is not cancel_event
        ):
            return

        self.conversation_text.append(
            f"JARVIS // ERROR: {error}"
        )

        self._log_activity(
            f"ERROR: {error[:45]}"
        )

        self.command_running = False
        self.active_command_cancel = None
        self.state = ProcessingState.ERROR

        self.core_status.setText(
            "JARVIS // ERROR"
        )

        self.core_mode.setText(
            "HOLOGRAPHIC CORE // ERROR"
        )

        self._set_core_state(
            "IDLE"
        )

        self._set_inputs_enabled(True)

    # ========================================================
    # SPEAKING ANIMATION
    # ========================================================

    def _on_speaking_changed(self, speaking):
        if speaking:
            self.state = (
                ProcessingState.SPEAKING
            )

            self.core_status.setText(
                "JARVIS // SPEAKING"
            )

            self.core_mode.setText(
                "HOLOGRAPHIC CORE // VOICE ACTIVE"
            )

            self.top_status.setText(
                "● VOICE OUTPUT ACTIVE"
            )

            if self.core:
                self.core.set_speaking(
                    True
                )

            self._log_activity(
                "VOICE OUTPUT ACTIVE"
            )

        else:
            self.state = (
                ProcessingState.PROCESSING
                if self.command_running
                else ProcessingState.IDLE
            )

            if self.command_running:
                self.core_status.setText(
                    "JARVIS // PROCESSING"
                )
            else:
                self.core_status.setText(
                    "JARVIS // READY"
                )

            self.core_mode.setText(
                "HOLOGRAPHIC CORE // IDLE"
            )

            self.top_status.setText(
                "● ALL SYSTEMS READY"
            )

            if self.core:
                self.core.set_speaking(
                    False
                )

    def _set_core_state(self, state):
        if not self.core:
            return

        self.core.set_mode(
            state
        )

    # ========================================================
    # VOICE
    # ========================================================

    def _on_voice_input(self):
        if self.listening or self.command_running:
            return

        if sr is None:
            self._on_voice_error(
                "speech_recognition is not installed."
            )
            return

        self.listening = True
        self.state = ProcessingState.LISTENING

        self._set_inputs_enabled(False)

        self.core_status.setText(
            "JARVIS // LISTENING"
        )

        self.core_mode.setText(
            "HOLOGRAPHIC CORE // VOICE INPUT"
        )

        self.top_status.setText(
            "● LISTENING"
        )

        self._set_core_state(
            "LISTENING"
        )

        self._log_activity(
            "VOICE INPUT ACTIVATED"
        )

        thread = threading.Thread(
            target=self._voice_worker,
            daemon=True
        )

        thread.start()

    def _voice_worker(self):
        try:
            # main.py contains the real local Whisper
            # recognizer, so we use it instead of creating
            # a second Whisper model here.
            jarvis = self.worker.load_main()

            recognizer = sr.Recognizer()

            with sr.Microphone() as source:
                command = (
                    jarvis.recognizeVoice(
                        source,
                        recognizer
                    )
                )

            if not command or not command.strip():
                self.signals.voice_error.emit(
                    "I could not understand that."
                )
                return

            self.signals.voice_result.emit(
                command
            )

        except sr.WaitTimeoutError:
            self.signals.voice_error.emit(
                "No speech detected."
            )

        except sr.UnknownValueError:
            self.signals.voice_error.emit(
                "I could not understand the speech."
            )

        except Exception as e:
            traceback.print_exc()

            self.signals.voice_error.emit(
                f"Microphone error: {e}"
            )

    def _on_voice_result(self, command):
        self.listening = False

        self.conversation_text.append(
            f"YOU  //  {command}"
        )

        self._log_activity(
            f"VOICE: {command[:45]}"
        )

        self._run_command(
            command
        )

    def _on_voice_error(self, message):
        self.listening = False
        self.command_running = False

        self.conversation_text.append(
            f"JARVIS // {message}"
        )

        self._log_activity(
            f"VOICE ERROR: {message[:45]}"
        )

        self.core_status.setText(
            "JARVIS // READY"
        )

        self.core_mode.setText(
            "HOLOGRAPHIC CORE // IDLE"
        )

        self.top_status.setText(
            "● ALL SYSTEMS READY"
        )

        self._set_core_state(
            "IDLE"
        )

        self._set_inputs_enabled(
            True
        )

    # ========================================================
    # INPUT ENABLE/DISABLE
    # ========================================================

    def _set_inputs_enabled(self, enabled):
        self.command_input.setEnabled(
            enabled
        )

        self.execute_btn.setEnabled(
            enabled
        )

        self.voice_btn.setEnabled(
            enabled
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def closeEvent(self, event):
        self._log_activity(
            "SYSTEM SHUTDOWN"
        )

        try:
            jarvis = self.worker.jarvis_main

            if jarvis is not None:
                # Keep your LFM2.5 server lifetime tied
                # to the complete Jarvis application.
                server = getattr(
                    jarvis,
                    "lfm_server",
                    None
                )

                if server is not None:
                    if server.poll() is None:
                        server.terminate()
                        server.wait(
                            timeout=3
                        )

        except Exception as e:
            print(
                f"Shutdown error: {e}"
            )

        event.accept()


# ============================================================
# MAIN
# ============================================================

def main():
    app = QApplication(sys.argv)

    try:
        face_store = FaceAuthStore()
        face_engine = FaceEngine()
    except FaceAuthError as exc:
        QMessageBox.critical(
            None,
            "Jarvis face security unavailable",
            str(exc),
        )
        return

    if not face_store.is_configured:
        setup_dialog = FaceSetupDialog(face_store, face_engine)
        if setup_dialog.exec() != QDialog.Accepted:
            return
        authenticated_person = setup_dialog.authenticated_person
    else:
        unlock_dialog = FaceUnlockDialog(face_store, face_engine)
        if unlock_dialog.exec() != QDialog.Accepted:
            return
        authenticated_person = unlock_dialog.authenticated_person

    jarvis_settings.CURRENT_PERSON_CONTEXT = {
        "name": authenticated_person["name"],
        "profile": authenticated_person.get("profile", ""),
    }

    window = JarvisGUI(
        authenticated_person,
        face_store,
        face_engine,
    )
    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
