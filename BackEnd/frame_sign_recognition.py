
import threading
from pathlib import Path
from collections import deque, Counter

import cv2
import joblib
import mediapipe as mp
import numpy as np

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ========================================
# PATHS
# ========================================

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

RESOURCE_ROOTS = [PROJECT_ROOT, BACKEND_DIR]

MODEL_PATH = next(
    (
        root / "models" / "isl_word_mlp_v1.joblib"
        for root in RESOURCE_ROOTS
        if (root / "models" / "isl_word_mlp_v1.joblib").exists()
    ),
    PROJECT_ROOT / "models" / "isl_word_mlp_v1.joblib"
)

HAND_MODEL_PATH = next(
    (
        root / "hand_landmarker.task"
        for root in RESOURCE_ROOTS
        if (root / "hand_landmarker.task").exists()
    ),
    PROJECT_ROOT / "hand_landmarker.task"
)

FRAME_PATH = BACKEND_DIR / "received_frame.jpg"
OUTPUT_PATH = BACKEND_DIR / "output.txt"


# ========================================
# MODEL CONFIGURATION
# ========================================

NUM_HANDS = 2
HAND_FEATURES = 63
FEATURE_COUNT = 132

CONFIDENCE_THRESHOLD = 0.60
SMOOTHING_WINDOW = 5
STABLE_VOTES = 3


# ========================================
# FEATURE EXTRACTION
# Same feature structure as test_word_webcam.py
# ========================================

def normalize_hand(landmarks):

    coords = np.asarray(
        [[p.x, p.y, p.z] for p in landmarks],
        dtype=np.float32
    )

    wrist = coords[0].copy()

    coords -= wrist

    scale = float(
        np.max(np.linalg.norm(coords[:, :2], axis=1))
    )

    if scale < 1e-6:
        return None

    coords /= scale

    return coords.flatten(), wrist, scale


def extract_features(result):

    vector = np.zeros(
        FEATURE_COUNT,
        dtype=np.float32
    )

    hands = []

    for landmarks in (result.hand_landmarks or []):

        normalized = normalize_hand(landmarks)

        if normalized is None:
            continue

        coords, wrist, scale = normalized

        hands.append({
            "wrist_x": float(wrist[0]),
            "wrist": wrist,
            "scale": scale,
            "features": coords
        })

    if not hands:
        return None

    hands.sort(key=lambda hand: hand["wrist_x"])

    hands = hands[:NUM_HANDS]

    for index, hand in enumerate(hands):

        start = index * HAND_FEATURES

        vector[start:start + HAND_FEATURES] = (
            hand["features"]
        )

        vector[126 + index] = 1.0

    if len(hands) == 2:

        left_hand, right_hand = hands

        difference = (
            right_hand["wrist"] -
            left_hand["wrist"]
        )

        average_scale = (
            left_hand["scale"] +
            right_hand["scale"]
        ) / 2.0

        if average_scale < 1e-6:
            return None

        relative = difference / average_scale

        vector[128:131] = relative
        vector[131] = np.linalg.norm(relative)

    return vector


# ========================================
# FRAME RECOGNITION SERVICE
# ========================================

class SignFrameRecognizer:

    def __init__(self):

        self.model = None
        self.detector = None

        self.history = deque(
            maxlen=SMOOTHING_WINDOW
        )

        self.lock = threading.Lock()

    def load_models(self):

        if self.model is not None:
            return

        if not MODEL_PATH.exists():

            raise FileNotFoundError(
                f"Word model not found: {MODEL_PATH}"
            )

        if not HAND_MODEL_PATH.exists():

            raise FileNotFoundError(
                f"Hand landmark model not found: {HAND_MODEL_PATH}"
            )

        model = joblib.load(MODEL_PATH)

        if (
            not hasattr(model, "predict_proba")
            or getattr(model, "n_features_in_", None)
            != FEATURE_COUNT
        ):

            raise ValueError(
                "Word model has an incompatible feature format."
            )

        options = vision.HandLandmarkerOptions(

            base_options=python.BaseOptions(
                model_asset_path=str(HAND_MODEL_PATH)
            ),

            running_mode=vision.RunningMode.IMAGE,

            num_hands=NUM_HANDS,

            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5

        )

        self.model = model

        self.detector = (
            vision.HandLandmarker.create_from_options(options)
        )

        print("Sign recognition models loaded successfully.")

    def process_frame(self, image_bytes):

        with self.lock:

            self.load_models()

            # Decode incoming image.
            encoded = np.frombuffer(
                image_bytes,
                dtype=np.uint8
            )

            frame = cv2.imdecode(
                encoded,
                cv2.IMREAD_COLOR
            )

            if frame is None:
                raise ValueError("Invalid image frame.")

            # Store only the latest frame.
            FRAME_PATH.write_bytes(image_bytes)

            # Convert BGR to RGB for MediaPipe.
            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            rgb = np.ascontiguousarray(rgb)

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb
            )

            # Detect hands.
            result = self.detector.detect(mp_image)

            # Extract ML features.
            features = extract_features(result)

            if features is None:

                self.history.clear()

                recognized_text = "No hand detected"

            else:

                probabilities = self.model.predict_proba(
                    features.reshape(1, -1)
                )[0]

                best_index = int(
                    np.argmax(probabilities)
                )

                label = str(
                    self.model.named_steps["mlp"].classes_[best_index]
                )

                confidence = float(
                    probabilities[best_index]
                )

                if confidence >= CONFIDENCE_THRESHOLD:

                    self.history.append(label)

                    candidate, votes = Counter(
                        self.history
                    ).most_common(1)[0]

                    if votes >= STABLE_VOTES:
                        recognized_text = candidate
                    else:
                        recognized_text = "Recognizing..."

                else:

                    self.history.clear()

                    recognized_text = "Uncertain sign"

            # Save latest recognition text.
            OUTPUT_PATH.write_text(
                recognized_text,
                encoding="utf-8"
            )

            return recognized_text


# ========================================
# GLOBAL SERVICE
# Load models once and reuse them.
# ========================================

recognizer = SignFrameRecognizer()


def process_image_frame(image_bytes):

    return recognizer.process_frame(image_bytes)
