import socket
import os
import time
import datetime
import requests
import logging
import threading
import sys
import subprocess

# ========================= LOGGER SETUP =========================
def setup_logger(log_path, handler_name):
    """Creates a logger to track connectivity and measurements."""
    logger_name = f"Thread-{threading.get_ident()}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if not any(handler.get_name() == handler_name for handler in logger.handlers):
        handler = logging.FileHandler(log_path)
        handler.set_name(handler_name)
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# ========================= NETWORK OPERATIONS =========================
def send_data(client_socket, image_path):
    """Send image data to the server."""
    size = os.path.getsize(image_path)
    print(f"Sending file: {image_path} ({size} bytes)")

    client_socket.sendall(size.to_bytes(8, byteorder='big'))
    
    with open(image_path, 'rb') as f:
        start_time = time.perf_counter_ns()
        while chunk := f.read(1024):
            client_socket.sendall(chunk)
        end_time = time.perf_counter_ns()

    bandwidth = size * 1e9 / 1e6 / (end_time - start_time)
    print(f"File sent. Bandwidth: {bandwidth} MBps")
    return size


def receive_string(client_socket):
    """Receive a string from the server."""
    size = int.from_bytes(client_socket.recv(8), byteorder='big')
    return client_socket.recv(size).decode()


def receive_data(client_socket, save_path):
    """Receive a file from the server."""
    size = int.from_bytes(client_socket.recv(8), byteorder='big')
    print(f"Receiving file. Expected size: {size} bytes")

    with open(save_path, 'wb') as f:
        received = 0
        while received < size:
            data = client_socket.recv(4096)
            if not data:
                break
            f.write(data)
            received += len(data)

    print(f"File received: {save_path}")


def send_msg(conn, msg):
    """Send a simple message to the server."""
    conn.sendall(msg.encode())


# ========================= NETWORK INFO =========================
def run_command(cmd):
    """Run a system command and return output."""
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    return result.stdout.decode(), result.stderr.decode()


def get_network_info(net_type, operating_system):
    """Retrieve signal strength and RSSI values."""
    command = {
        ("windows", "mbn"): 'netsh mbn show interfaces',
        ("windows", "wlan"): 'netsh wlan show interfaces',
        ("linux", "mbn"): 'mmcli -m 0',
        ("linux", "wlan"): 'iwconfig',
    }.get((operating_system.lower(), net_type.lower()))

    if not command:
        print("Error: Invalid OS or network type")
        return None, None

    stdout, stderr = run_command(command)
    if stderr:
        print(f"Command Error: {stderr}")
        return None, None

    signal_val = RSSI_val = None
    for line in stdout.split('\n'):
        if 'Signal' in line:
            signal_val = line.split(":")[1].strip()
        if 'RSSI' in line:
            RSSI_val = line.split(":")[1].strip()

    print(f"Signal Strength: {signal_val}, RSSI: {RSSI_val}")
    return signal_val, RSSI_val


# ========================= MAIN CLIENT LOGIC =========================
def main():
    host = 'localhost'
    port = 51820
    conn_type = 'wlan'
    operating_system = "Windows"
    input_path = 'Input/'
    output_path = 'Output/'
    max_iterations = 16
    image_count = 0
    iteration = 0
    connected = False

    log_path = "log_files/combined_log.log"

    print(f"Client started. Connecting to {host}:{port}")

    while iteration <= max_iterations:
        if not connected:
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print("Attempting to connect...")
                client_socket.connect((host, port))
                client_socket.settimeout(5)
                connected = True
                print("Connected to server.")
            except socket.error as e:
                print(f"Connection failed: {e}")
                time.sleep(2)
                continue

        try:
            while iteration <= max_iterations:
                timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"\n[Iteration {iteration}, Image {image_count}] - Timestamp: {timestamp}")

                image_path = f"{input_path}{image_count}_in.jpg"
                save_path = f"{output_path}{iteration}_{image_count}_out.jpg"

                start_time_ns = time.time_ns()
                image_size = send_data(client_socket, image_path)

                processing_time_ns = int.from_bytes(client_socket.recv(8), byteorder='big')
                received_data = receive_string(client_socket)
                end_time_ns = time.time_ns()

                signal_val, RSSI_val = get_network_info(conn_type, operating_system)

                log_data = f"{timestamp}; {iteration}; {image_count}; {image_size}; {start_time_ns}; {processing_time_ns}; {end_time_ns}; {signal_val}; {RSSI_val}; {received_data}"
                setup_logger(log_path, 'handler1').info(log_data)

                iteration += 1

                if iteration > max_iterations:
                    send_msg(client_socket, "STOP")
                    print("Max iterations reached. Stopping.")
                else:
                    image_count += 1
                    send_msg(client_socket, "CONT")

        except KeyboardInterrupt:
            print("\nInterrupted! Stopping gracefully.")
            break
        except socket.error as e:
            print(f"Connection lost: {e}")
            connected = False
            client_socket.close()
            time.sleep(2)
        finally:
            if iteration > max_iterations:
                break
            print("Closing connection...")
            client_socket.close()
            connected = False
            
if __name__ == '__main__':
    main()     