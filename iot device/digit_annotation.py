"""
YK-100 digit box calibration and annotation.

Produces yk100_digit_boxes_calibrated.pkl in the early_warning_system directory for use by
OCR live and debug_ocr_polygon. Input: live camera (SPACE to capture) or image file; use 1280x720
for consistency with OCR live. Single-parameter mode: annotate one parameter (e.g. pH) and merge
into existing calibration.

Usage:
  python early_warning_system/digit_annotation.py [image_path] [param]
  python early_warning_system/digit_annotation.py frame.jpg pH
"""
import sys
from pathlib import Path

import cv2
import pickle
import numpy as np
import matplotlib.pyplot as plt

# Run from project root. brightnessContrast and binarization are resolved from cwd.
import brightnessContrast as brco
import binarization as bi

# Paths: project root (for early_warning_system package), ocr_live (so ocr_camera can import ocr_config)
_EWS = Path(__file__).resolve().parent
_MAIN = _EWS.parent
_OCR_LIVE = _EWS / "ocr_live"
for p in (_MAIN, _OCR_LIVE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from early_warning_system.ocr_live.ocr_camera import initialize_camera, release_camera
from ocr_config import DISPLAY_TILT_CORRECTION_DEG
from ocr_engine import correct_tilt

# =====================================================
# CONFIGURATION — output path in early_warning_system for OCR and polygon debug
# =====================================================
PARAMETERS = ["pH", "TEMP", "DO", "CON"]
OUTPUT_FILE = _EWS / "yk100_digit_boxes_calibrated.pkl"

MIN_BOX_W = 8
MIN_BOX_H = 15

# Single-parameter mode: annotate only one parameter when argv[2] is provided (e.g. "pH").
single_param = None
if len(sys.argv) > 2 and sys.argv[2].strip().upper() in [p.upper() for p in PARAMETERS]:
    for p in PARAMETERS:
        if p.upper() == sys.argv[2].strip().upper():
            single_param = p
            break
if single_param:
    if not OUTPUT_FILE.exists():
        print("[ERROR] Single-parameter mode requires existing calibration file:", OUTPUT_FILE)
        print("Run without the parameter name first to create a full calibration.")
        exit(1)
    with open(OUTPUT_FILE, "rb") as f:
        setup = pickle.load(f)
    params_to_annotate = [single_param]
    print("Editing annotation for:", single_param, "(rest of calibration unchanged)")
else:
    setup = {}
    params_to_annotate = PARAMETERS

# =====================================================
# FRAME SOURCE — image file or live camera
# =====================================================
base_frame = None
if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
    img_path = Path(sys.argv[1])
    if img_path.exists():
        base_frame = cv2.imread(str(img_path))
        if base_frame is None:
            print("[ERROR] Could not load image:", img_path)
            exit(1)
        print("Loaded image:", img_path, "shape:", base_frame.shape)
    else:
        print("[ERROR] File not found:", img_path)
        exit(1)

if base_frame is None:
    # Live camera: same settings as OCR live (MJPG, 1280x720, warm-up, focus, exposure).
    cap = initialize_camera()
    if cap is None:
        print("[ERROR] Cannot open camera")
        exit()
    print("\nLIVE CAMERA (same as OCR live)")
    print("SPACE = capture frame | Q = quit")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        cv2.imshow("Live Camera", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 32:  # SPACE
            base_frame = frame.copy()
            break
        elif key == ord('q'):
            release_camera(cap)
            cv2.destroyAllWindows()
            exit()
    release_camera(cap)
    cv2.destroyAllWindows()
    print("Frame captured from camera\n")
else:
    print("Using image file for annotation\n")

# Apply same tilt correction as at runtime so annotation matches corrected view
if DISPLAY_TILT_CORRECTION_DEG != 0:
    base_frame = correct_tilt(base_frame, DISPLAY_TILT_CORRECTION_DEG)
    print(f"Applied tilt correction: {DISPLAY_TILT_CORRECTION_DEG} deg")

gray_full = cv2.cvtColor(base_frame, cv2.COLOR_BGR2GRAY)

# =====================================================
# MOUSE DRAWING
# =====================================================
drawing = False
start_point = None
current_box = None
boxes = []

def mouse_callback(event, x, y, flags, param):
    global drawing, start_point, current_box, boxes

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_point = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        current_box = (*start_point, x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False

        x1, y1 = start_point
        x2, y2 = x, y

        x_min, x_max = min(x1, x2), max(x1, x2)
        y_min, y_max = min(y1, y2), max(y1, y2)

        if (x_max - x_min) < MIN_BOX_W or (y_max - y_min) < MIN_BOX_H:
            print("[WARN] Box too small; ignored.")
            current_box = None
            return

        boxes.append((x_min, y_min, x_max, y_max))
        current_box = None

# =====================================================
# ANNOTATION + CALIBRATION
# =====================================================
for param in params_to_annotate:
    print("\n==============================")
    print(f"Annotating: {param}")
    print("==============================")

    num_digits = int(input(f"How many digits for {param}? >> "))
    boxes = []

    cv2.namedWindow("Annotation")
    cv2.setMouseCallback("Annotation", mouse_callback)

    while True:
        display = base_frame.copy()

        # Draw saved boxes
        for i, (x1, y1, x2, y2) in enumerate(boxes):
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(display, str(i+1), (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

        # Draw active box
        if current_box:
            x1, y1, x2, y2 = current_box
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 1)

        cv2.putText(
            display,
            f"{param}: {len(boxes)}/{num_digits}  |  Ctrl+Z = undo",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2
        )

        cv2.imshow("Annotation", display)
        key = cv2.waitKey(1) & 0xFF

        # Undo last box (Ctrl+Z)
        if key == 26 and boxes:
            boxes.pop()
            print("↩️ Undo last box")

        if len(boxes) == num_digits:
            break

    cv2.destroyWindow("Annotation")

    # =====================================================
    # SORT DIGITS LEFT → RIGHT
    # =====================================================
    boxes = sorted(boxes, key=lambda b: b[0])

    # =====================================================
    # ROI EXTRACTION (SAFE)
    # =====================================================
    digit_rois = []
    heights = []

    for (x1, y1, x2, y2) in boxes:
        roi = gray_full[y1:y2, x1:x2]

        if roi.size == 0:
            print("[WARN] Empty ROI skipped.")
            continue

        digit_rois.append(roi)
        heights.append(roi.shape[0])

    if not digit_rois:
        raise RuntimeError(f"No valid digit ROIs for {param}")

    target_height = min(heights)

    resized_rois = []
    for roi in digit_rois:
        h, w = roi.shape
        if h == 0 or w == 0:
            continue

        new_w = max(1, int(w * (target_height / h)))
        resized = cv2.resize(roi, (new_w, target_height))
        resized_rois.append(resized)

    composite = np.hstack(resized_rois)

    # =====================================================
    # BRIGHTNESS / CONTRAST
    # =====================================================
    bc = brco.BrightContr(composite)
    cv2.waitKey()
    cv2.destroyAllWindows()
    plt.close('all')

    # =====================================================
    # BINARIZATION
    # =====================================================
    binar = bi.Binarizador(bc.transformada)
    cv2.waitKey()
    cv2.destroyAllWindows()
    plt.close('all')

    setup[param] = {
        "digits": boxes,
        "alpha": bc.alpha,
        "beta": bc.beta,
        "blockSize": binar.size,
        "offset": binar.offset
    }

    print(f"[INFO] {param} calibration saved.")

# =====================================================
# SAVE SETUP
# =====================================================
with open(OUTPUT_FILE, "wb") as f:
    pickle.dump(setup, f)

print("\n🎉 DIGIT ANNOTATION + CALIBRATION COMPLETE")
print(f"Saved as: {OUTPUT_FILE}")
