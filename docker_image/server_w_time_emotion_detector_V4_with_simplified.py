import socket
import os
import time
import threading
#from flask import Flask, request, jsonify
import datetime
import cv2
import numpy as np
import mediapipe as mp
from fer import FER
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import wget

# Flask app initialization

def get_container_ip():
    return socket.gethostbyname(socket.gethostname())

def get_time():
    """Calculates and returns time difference in nanoseconds."""
    try:
        data = request.get_json()
        windows_time = datetime.datetime.fromisoformat(data['time'])
        linux_time = datetime.datetime.now(datetime.timezone.utc).astimezone()
        
        time_diff_ns = (windows_time - linux_time).total_seconds() * 1e9
        return jsonify({'time_difference': str(int(time_diff_ns))})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def get_value():
    return jsonify({'status': 'success'})

# Download gesture recognizer model if not present
MODEL_PATH = 'gesture_recognizer.task'
if not os.path.exists(MODEL_PATH):
    wget.download('https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task')

# Initialize MediaPipe modules
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_face_detection = mp.solutions.face_detection

def receive_data(conn, save_path):
    """Receives image data from the client and saves it."""
    size = int.from_bytes(conn.recv(8), byteorder='big')
    received = 0
    with open(save_path, 'wb') as f:
        while received < size:
            data = conn.recv(4096)
            if not data:
                break
            f.write(data)
            received += len(data)
    print("[INFO] Data received and saved.")

def send_string(conn, string):
    """Sends a string message to the client."""
    conn.sendall(len(string).to_bytes(8, byteorder='big'))
    conn.sendall(string.encode())

def detect_emotions(img):
    """Detects emotions in the given image."""
    detector = FER(mtcnn=True)
    return detector.detect_emotions(img)

def process_image(file_path):
    """Processes the image to detect emotions."""
    img = cv2.imread(file_path)
    if img is None:
        return "Error: Image not loaded"
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    emotions = detect_emotions(img)
    if not emotions:
        return "No face detected"
    
    max_emotion = max(emotions[0]['emotions'], key=emotions[0]['emotions'].get)
    return max_emotion

def main():
    host = get_container_ip()
    port = 51820
    save_path = 'received_data.jpg'
    print(f"[INFO] Server running on {host}:{port}")
    
    while True:
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((host, port))
            server_socket.listen(5)
            print("[INFO] Waiting for new connections...")
            
            conn, addr = server_socket.accept()
            print(f"[INFO] Connected by {addr}")
            conn.settimeout(5)
        except socket.error as e:
            print(f"[ERROR] Connection error: {e}")
            continue

        except KeyboardInterrupt:
            print("\nInterrupted! Stopping gracefully.")
            break
        
        try:
            while True:
                print("[INFO] Receiving new data...")
                receive_data(conn, save_path)
                
                start_time = time.time_ns()
                emotion_text = process_image(save_path)
                end_time = time.time_ns()
                processing_time = end_time - start_time
                
                print(f"[INFO] Processing time: {processing_time} ns")
                conn.sendall(processing_time.to_bytes(8, byteorder='big'))
                send_string(conn, emotion_text)
                
                rcv_message = conn.recv(1024).decode()
                if rcv_message == "STOP":
                    print("[INFO] Closing connection...")
                    break
        except socket.error as e:
            print(f"[ERROR] Connection lost: {e}")

        except KeyboardInterrupt:
            print("\nInterrupted! Stopping gracefully.")
            break

        finally:
            conn.close()
            print("[INFO] Connection closed.")
            time.sleep(1)

if __name__ == '__main__':
    main()
