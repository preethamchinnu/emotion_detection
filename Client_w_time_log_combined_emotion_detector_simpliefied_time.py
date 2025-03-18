import socket
import os
import time
import datetime
import requests
from multiprocessing import Process, Event, Value, Lock # mayber also try subprocess
import logging
import threading
import sys
import subprocess

def send_data(client_socket, image_path):
    # Send data from the client to the Server. 
    # Get the data size
    size = os.path.getsize(image_path)
    # Send the data size
    client_socket.sendall(size.to_bytes(8, byteorder='big'))
    # Send data
    with open(image_path, 'rb') as f:
        start_time = time.perf_counter_ns()
        while True:
            data = f.read(1024)
            if not data:
                break
            client_socket.sendall(data)
        end_time = time.perf_counter_ns()
    bandwidth = size*1*10**9/10**6/(end_time - start_time)
    return size 

def receive_string(client_socket):
    # Receive data from the Server. The File size is transmitted first followed by the data.
    # Receive the data size
    string= ""
    size = client_socket.recv(8)
    size = int.from_bytes(size, byteorder='big')
    data = client_socket.recv(size)
    string = data.decode()
    return string

def receive_data(client_socket, save_path):
    # Receive data from the Server. The File size is transmitted first followed by the data.
    # Receive the data size
    size = client_socket.recv(8)
    size = int.from_bytes(size, byteorder='big')
    # Receive data
    with open(save_path, 'wb') as f:
        received = 0
        while received < size:
            data = client_socket.recv(4096)
            #print("data: ",data)
            if not data:
                break
            f.write(data)
            received += len(data)

def recv_msg(client_socket, msg):
    # Used to decode incoming status messages. Can be used to realize a state machine
    msg_len = len(msg)
    msg = ''
    data = client_socket.recv(msg_len)
    msg = data.decode()
    return msg

def setup_logger(path, handler_name):
    # Setup the data logger. A new handler will be created for each new log.

    logger_name = f"Thread-{threading.get_ident()}"         # set unique name
    connectivity_logger = logging.getLogger(logger_name)    # create new logger with unique name
    connectivity_logger.setLevel(logging.INFO)              # set logging level to INFO

    # Überprüfen, ob der Handler bereits existiert
    handler_exists = False                                  
    for handler in connectivity_logger.handlers:            # check if the defined handler exists
        if handler.get_name() == handler_name:
            handler_exists = True
            break

    if not handler_exists:                                  # if not, create one and
        handler = logging.FileHandler(path)                 # set the log path
        handler.set_name(handler_name)                      # set the loggers name
        formatter = logging.Formatter("%(asctime)s - %(message)s")  # and log format
        handler.setFormatter(formatter)             
        connectivity_logger.addHandler(handler)             # finally, create the handler

    return connectivity_logger                              # return handler type

def measurement(path, handler_name, log_time, iteration, image, image_size, connection_time, time_start_ns, processing_time_s, time_end_ns, signal_val, RSSI_val, data):#, time_disconnect):
    measurement_logger = logging.getLogger(f"Thread-{threading.get_ident()}")
    measurement_logger.setLevel(logging.INFO)

    handler_exists = False
    for handler in measurement_logger.handlers:
        if handler.get_name() == handler_name:
            handler_exists = True
            break
        
    if not handler_exists:
        handler = logging.FileHandler(path)
        handler.set_name(handler_name)
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        handler.setFormatter(formatter)
        measurement_logger.addHandler(handler)
    #data_logger = logging.getLogger(f"Thread-{threading.get_ident()}")
    #data_logger.addHandler(logging.FileHandler(path))
    #data_logger.setLevel(logging.INFO)
    #formatter = logging.Formatter("%(asctime)s - %(message)s")
    #data_logger.handlers[0].setFormatter(formatter)  # Weise den Formatter dem Handler zu
    data_size = sys.getsizeof(data)
    try:
        measurement_logger.info(f"{log_time}; {iteration}; {image}; {image_size}; {connection_time}; {time_start_ns}; {processing_time_s}; {time_end_ns}; {signal_val}; {RSSI_val}; {data}; {data_size}") #; {time_disconnect}; {overall_time}")
        pass
    except Exception as e:
        measurement_logger.error(f"an error has occured: {e}")
    finally:
        for handler in measurement_logger.handlers:
            if handler.get_name() == handler_name:
                measurement_logger.removeHandler(handler)
                handler.close()

# Funktion zur Ausführung von Befehlen
def run_command(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    return result.stdout, result.stderr

def define_command(net_type, operating_system):
    signal_val = None
    RSSI_val = None
    error = None
    stdout = None
    stderr = None
    #print(operating_system)
    if operating_system == "windows" or operating_system == "Windows":
        if net_type == 'mbn':
            command = 'netsh mbn show interfaces'
        elif net_type == 'wlan':
            command = 'netsh wlan show interfaces'
        stdout, stderr = run_command(command)
        stdout = stdout.decode('ISO-8859-1')
        error = stderr.decode('ISO-8859-1')
        
        if stderr:
            print("errorcode: ", stderr)
        elif error:
            print(error)
        # Parse the command output
        lines = stdout.split('\n')
        #print('lines; ', len(lines))
        for line in lines:
            #print('line: ', line)
            if 'Signal' in line:
                new_lines = line.split(":")
                signal_val = (new_lines[1].strip())
                #print(signal_val)
                #print(new_lines)
            elif  'RSSI' in line:
                new_lines = line.split(":")
                RSSI_val = (new_lines[1].strip())
                #print(RSSI_val)
                #print(new_lines)

    elif operating_system == "linux" or operating_system == "Linux": 
        if net_type == 'mbn':
            command = 'mmcli -m 0'
        elif net_type == 'wlan':
            command = 'iwconfig'
        stdout, stderr = run_command(command)
        stdout = stdout.decode()
        error = stderr.decode()
        if stderr and net_type=='mbn':
            print("errorcode: ", stderr)
        # Parse the command output
        #print(stdout)
        lines = stdout.split('\n')
        #print('lines; ', len(lines))
        #print('Lines \n', lines)
        if net_type == 'mbn':
            for line in lines: 
                #print('Line ', line)
                if "signal quality" in line: 
                    signal_val = line.split(':')[1].split('%')[0].strip() + '%'
                    #print(signal_val)
                    RSSI_val = None
        elif net_type == 'wlan':
            for line in lines: 
                if "Link Quality" in line: 
                    signal_val = line.split('=')[1].split(' ')[0].strip() 
                if "Signal level" in line: 
                    RSSI_val = line.split('Signal level=')[1].split(' ')[0].strip()
        else: 
            error = "no or wrong connection type"
            sys.exit()
    else:
        error = "no or wrong operating system selected"
        sys.exit()
    return signal_val, RSSI_val, error

def get_mbn_info(net_type, operating_system):
    signal_val = None
    RSSI_val = None
    try:        
 
        signal_val, RSSI_val, error = define_command(net_type, operating_system)
        
        return {signal_val, RSSI_val}

    except Exception as f:
        print(f"an error has occurred {f}")
        sys.exit(0)

def send_msg(conn, msg):
    conn.sendall(msg.encode()) 

def get_windows_time():
    # Get the current system time
    current_time = datetime.datetime.now(datetime.timezone.utc)
    return current_time

def time_synchronisation_offset(host, port, result):
    windows_time = get_windows_time()
    windows_time_iso = windows_time.isoformat()
    ipadress = "http://" + host + ":" + str(port)
    response_time = requests.post(ipadress + '/time', json={'time': windows_time_iso})
    #print("Time difference:", response_time.json().get('time_difference'))

    # Calculate Transfer time
    start_time = get_windows_time()
    response = requests.get(ipadress + '/transfer')
    end_time = get_windows_time()

    # Calculate the time difference
    time_diff = (end_time - start_time)/2
    #print("Transfer time:",time_diff)

    time_difference_str = response_time.json().get('time_difference')
    time_difference_float = float(time_difference_str)
    # Zeitdifferenz in ein datetime.timedelta-Objekt umwandeln
    nanoseconds_offset = int(time_difference_float)
    print(f"nanosec {nanoseconds_offset}")
    
    time_seconds = time_diff.total_seconds() 
    # Zeit in Nanosekunden umrechnen 
    transfer_time_nanoseconds = int(time_seconds * 1e9) 
    print(f"transfertime in nanoseconds: {transfer_time_nanoseconds}")

    total_time_offset =  transfer_time_nanoseconds + nanoseconds_offset
    print(f"Time in total_time_offset: {total_time_offset}")
    # todo: Zeitdifferenz berechnen und dann als Offset auf die Zeit aufaddieren
    # Achtung, response muss umgerechnet werden auf ein integer wert und die time diff ebenfalls
    result['total_time_offset'] = total_time_offset

def main():
    #host_uri = "kubernetes-uni-stuttgart-5g-tes.frankfurt-main-tdg.eu.app.edge.telekom.com" #"messung-uni-stuttgart-5g-tes.frankfurt-main-tdg.eu.app.edge.telekom.com"
    #host = socket.gethostbyname(host_uri)
    #host = '193.196.55.50' 
    #host = '193.196.54.78'
    host = '172.27.16.1' 
    #port = 1194 
    port = 51821 
    #port = 1194

    conn_type = 'wlan'
    operating_system = "windows"
    input_path = 'Input/'
    output_path = 'Output/'
    im_max = 0 # numer of images
    it_max = 100 # number of iterations
    iteration = 0
    connected = 0
    image = 0
    keyboard_interrupt_occurred = False
    total_time_offset = 0

    path_connectivity_log = "log_files/conn/connectivity_log.log"
    path_data_log = "log_files/combined_log.log"

    
    while True: # infinite loop for data transmission
        last_time = time.time_ns()  # set init time for timing
        image_size = 0
        if not connected:
            try:    # try to setup connection to server
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Measure RTT on the client side
                connection_time = time.perf_counter_ns()
                client_socket.connect((host, port))
                client_socket.settimeout(5)
                connected = 1
                #print(client_socket)
            except socket.error as e:   # if connection fails, retry after 2 seconds
                timestamp = datetime.datetime.now()
                log_time = timestamp.strftime("%H:%M:%S.%f")[:-3]                           # create log-timestamp wihout the last 3 zeroes
                error_msg = f"No connection possible: {e}"
                print(error_msg)

                result = get_mbn_info(conn_type, operating_system)
                result = list(result)
                if result[0] == None:
                    signal_val = 'None'
                    RSSI_val = 'None'
                else:
                    signal_val = result[0]
                    RSSI_val = result[1]
                measurement(path_data_log, 'handler1', log_time, iteration, image, image_size, 0, 0, 0, 0, signal_val, RSSI_val, error_msg)#, time_disconnect))

                time.sleep(2)
    
        if connected:                                                                           # if connected to the server continue, otherwise skip
            try:                                                                                # try to transfer date
                while iteration <= it_max:  
                    #print("process new image")                                                   #till the number of iterations is reaches
                    current_time = time.time_ns()
                    #log_date = datetime.date.today()
                    timestamp = datetime.datetime.now()
                    # Formatierung als "Stunde:Minute:Sekunde Mikrosekunden"
                    log_time = timestamp.strftime("%H:%M:%S.%f")[:-3]                           # create log-timestamp wihout the last 3 zeroes
        
                    #print("iteration: ", iteration)
                    #print("image: ", image)
                    if current_time - last_time >=0.3*10**-9:                                     # if the last iteration was 1s earlier
                        last_time = current_time                                                # set new time value
                        image_path = input_path + str(image) + "_in.jpg"                        # read image path
                        save_path = output_path + str(iteration) + "_"+ str(image) + "_out.jpg" # set output path
                        
                        time_start_ns = time.time_ns()
                        image_size = send_data(client_socket, image_path)                 # send data to the Server
                        processing_time_ns = int.from_bytes(client_socket.recv(8), byteorder='big')
                        data = receive_string(client_socket)
                        time_end_ns = time.time_ns()
                                                       
                        result = get_mbn_info(conn_type, operating_system)
                        result = list(result)
                        print(result)
                        signal_val = result[0]
                        RSSI_val = result[1]
                        
                        measurement(path_data_log, 'handler1', log_time, iteration, image, image_size, connection_time, time_start_ns, processing_time_ns, time_end_ns, signal_val, RSSI_val, data)#, time_disconnect))
                        #print('success')
                        if image == im_max:                # continue with the next image. If the last one is reched, iteration +1
                            image = 0
                            iteration += 1
                            print('iteration', iteration)
                            print('it_max', it_max)

                            if iteration > it_max:          # stop condition
                                send_msg(client_socket, "STOP") # leave inner loop
                                print('send_msg stop')
                                break 
                            send_msg(client_socket, "CONT") #
                        else:
                            image += 1                      # next image
                            #print('image', image)
                            send_msg(client_socket, "CONT")
            except KeyboardInterrupt: 
                print("\nKeyboardInterrupt detected. Setze it_max auf die aktuelle Iteration...") 
                it_max = iteration 
                print("new_it max", it_max) 
                keyboard_interrupt_occurred = True
            except socket.error as e:
                error_msg = f'Connection lost {e}'
                timestamp = datetime.datetime.now()
                log_time = timestamp.strftime("%H:%M:%S.%f")[:-3]                           # create log-timestamp wihout the last 3 zeroes
                print(error_msg)

                result = get_mbn_info(conn_type, operating_system)
                result = list(result)
                signal_val = result[0]
                RSSI_val = result[1]
                measurement(path_data_log, 'handler1', log_time, iteration, image, image_size, 0, 0, 0, 0, signal_val, RSSI_val, error_msg)#, time_disconnect))

            finally: 
                if not keyboard_interrupt_occurred: 
                    print('close socket') 
                    client_socket.close() 
                    connected = False 
                    if iteration >= it_max:
                        break
                    time.sleep(2) 
                    time_disconnect = time.time_ns() 
                else: 
                    keyboard_interrupt_occurred = False
                    continue # Reset the flag for the next iteration print('continue processing after KeyboardInterrupt')
            #finally:    # if the connection is lost, close socket and retry to reconnect after 2 seconds
            #    print('close socket')
            #    client_socket.close()
            #    if iteration >= it_max:
            #        break
            #    time.sleep(2)
            #    time_disconnect = time.perf_counter_ns()
            #    ## round-trip time

if __name__ == '__main__':
    main()
