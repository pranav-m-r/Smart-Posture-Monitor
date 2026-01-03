"""
MoveNet Pose Estimation - Raspberry Pi Camera Test
Displays live camera feed with pose estimation annotations
"""

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
import time

# Try to import picamzero for RPi camera support
try:
    from picamzero import Camera
    PICAMZERO_AVAILABLE = True
except ImportError as e:
    PICAMZERO_AVAILABLE = False
    print(f"picamzero not available: {e}")
    print("Will use OpenCV for camera access")


def load_model(model_path):
    """Load the TFLite model and allocate tensors."""
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter


def preprocess_frame(frame, input_size):
    """Preprocess the frame for MoveNet model input."""
    # Resize to model input size
    img = cv2.resize(frame, (input_size, input_size))
    # Convert to RGB (MoveNet expects RGB)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    # Expand dimensions to match model input shape [1, height, width, 3]
    img = np.expand_dims(img, axis=0)
    return img.astype(np.uint8)


def run_inference(interpreter, input_image):
    """Run inference on the preprocessed image."""
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    
    # Set the tensor
    interpreter.set_tensor(input_details[0]['index'], input_image)
    
    # Run inference
    interpreter.invoke()
    
    # Get the output
    keypoints_with_scores = interpreter.get_tensor(output_details[0]['index'])
    
    # MoveNet outputs shape: [1, 1, 17, 3] where 3 = (y, x, confidence)
    # Reshape to [17, 3]
    keypoints = keypoints_with_scores[0][0]
    
    return keypoints


def draw_keypoints(frame, keypoints, confidence_threshold=0.3):
    """Draw keypoints on the frame."""
    h, w = frame.shape[:2]
    
    for i, (y, x, confidence) in enumerate(keypoints):
        if confidence > confidence_threshold:
            # Convert normalized coordinates to pixel coordinates
            cx = int(x * w)
            cy = int(y * h)
            
            # Draw circle for keypoint
            cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
    
    return frame


def draw_skeleton(frame, keypoints, confidence_threshold=0.3):
    """Draw skeleton connections between keypoints."""
    h, w = frame.shape[:2]
    
    # MoveNet keypoint indices (COCO format)
    # 0: nose, 1: left eye, 2: right eye, 3: left ear, 4: right ear,
    # 5: left shoulder, 6: right shoulder, 7: left elbow, 8: right elbow,
    # 9: left wrist, 10: right wrist, 11: left hip, 12: right hip,
    # 13: left knee, 14: right knee, 15: left ankle, 16: right ankle
    
    # Define skeleton connections
    connections = [
        (0, 1), (0, 2), (1, 3), (2, 4),  # Head
        (5, 6),  # Shoulders
        (5, 7), (7, 9),  # Left arm
        (6, 8), (8, 10),  # Right arm
        (5, 11), (6, 12),  # Torso
        (11, 12),  # Hips
        (11, 13), (13, 15),  # Left leg
        (12, 14), (14, 16),  # Right leg
    ]
    
    for start_idx, end_idx in connections:
        if (keypoints[start_idx][2] > confidence_threshold and 
            keypoints[end_idx][2] > confidence_threshold):
            
            # Get start point
            start_y, start_x = keypoints[start_idx][:2]
            start_point = (int(start_x * w), int(start_y * h))
            
            # Get end point
            end_y, end_x = keypoints[end_idx][:2]
            end_point = (int(end_x * w), int(end_y * h))
            
            # Draw line
            cv2.line(frame, start_point, end_point, (255, 0, 0), 2)
    
    return frame


def main():
    """Main function to run pose estimation on camera feed."""
    # Path to the TFLite model
    model_path = "model.tflite"
    
    print("Loading MoveNet model...")
    interpreter = load_model(model_path)
    
    # Get model input size
    input_details = interpreter.get_input_details()
    input_shape = input_details[0]['shape']
    input_size = input_shape[1]
    print(f"Model input size: {input_size}x{input_size}")
    
    # Initialize camera
    print("Initializing camera...")
    use_picamzero = False
    cap = None
    cam = None
    
    # Try picamzero first
    if PICAMZERO_AVAILABLE:
        try:
            print("Attempting to initialize with picamzero...")
            cam = Camera()
            use_picamzero = True
            print("Successfully initialized camera with picamzero")
        except Exception as e:
            print(f"Failed to initialize picamzero: {e}")
            cam = None
    
    # Fall back to OpenCV if picamzero didn't work
    if not use_picamzero:
        print("Trying OpenCV camera access...")
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        
        if not cap.isOpened():
            for cam_index in [0, 1, 2]:
                print(f"Trying camera index {cam_index}...")
                cap = cv2.VideoCapture(cam_index)
                if cap.isOpened():
                    print(f"Successfully opened camera at index {cam_index}")
                    break
                cap.release()
        
        if not cap.isOpened():
            print("Error: Could not open camera with any method.")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    print("Starting pose estimation... Press 'q' to quit.")
    time.sleep(0.5)
    
    try:
        while True:
            # Capture frame
            if use_picamzero:
                # picamzero captures as numpy array
                frame = cam.capture_array()
                # Convert RGB to BGR for OpenCV
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                ret, frame = cap.read()
                if not ret:
                    print("Warning: Failed to capture frame")
                    time.sleep(0.1)
                    continue
            
            # Preprocess frame
            input_image = preprocess_frame(frame, input_size)
            
            # Run inference
            keypoints = run_inference(interpreter, input_image)
            
            # Draw annotations on frame
            frame = draw_skeleton(frame, keypoints)
            frame = draw_keypoints(frame, keypoints)
            
            # Add instructions
            cv2.putText(frame, "Press 'q' to quit", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            # Display the frame
            cv2.imshow('MoveNet Pose Estimation', frame)
            
            # Check for quit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        # Cleanup
        if use_picamzero and cam:
            cam.close()
        elif cap:
            cap.release()
        cv2.destroyAllWindows()
        print("Done!")


if __name__ == "__main__":
    main()