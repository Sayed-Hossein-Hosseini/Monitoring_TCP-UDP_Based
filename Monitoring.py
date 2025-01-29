import socket
import threading
import psutil
import os
import time

# ==================== Agent Code ====================
AUTHORIZED_AGENTS = {"127.0.0.1"}  # Allowed agent IPs
AGENTS = []  # List to hold information about connected agents

def reconnect_tcp(manager_ip, manager_port):
    """Try to reconnect to the manager if the connection is lost."""
    counter = 0
    while True:
        try:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.connect((manager_ip, manager_port))
            return tcp_socket
        except Exception as e:
            counter += 1
            print(f"Reconnection attempt failed: {e}. Retrying in 5 seconds...")
            if counter % 5 == 0:
                manager_ip = input("Enter Manager IP: ").strip()
            time.sleep(5)

def agent_tcp_handler(manager_ip, manager_port):
    """Handle TCP connection with the central manager."""
    while True:
        tcp_socket = reconnect_tcp(manager_ip, manager_port)

        try:
            local_ip, local_port = tcp_socket.getsockname()
            print(f"Connected to Manager. Local TCP Port: {local_port}")

            agent_id = socket.gethostname()
            tcp_socket.send(agent_id.encode())

            data = tcp_socket.recv(1024).decode()
            udp_port = int(data)

            print(f"Received UDP Port from Manager: {udp_port}")

            threading.Thread(target=monitor_system, args=(manager_ip, udp_port, agent_id), daemon=True).start()

            while True:
                command = tcp_socket.recv(1024).decode()

                if command == "get_status":
                    memory = psutil.virtual_memory().percent
                    cpu = psutil.cpu_percent(interval=1)
                    disk_usage = psutil.disk_usage('/').percent
                    net_io = psutil.net_io_counters()
                    net_info = f"Sent: {net_io.bytes_sent / (1024 ** 2):.2f} MB, Received: {net_io.bytes_recv / (1024 ** 2):.2f} MB"
                    uptime_seconds = time.time() - psutil.boot_time()
                    uptime = time.strftime('%H:%M:%S', time.gmtime(uptime_seconds))

                    response = (f"Memory Usage: {memory}%, CPU Usage: {cpu}%, "
                                f"Disk Usage: {disk_usage}%, Network: {net_info}, "
                                f"Uptime: {uptime}")
                    tcp_socket.send(response.encode())
                elif command == "get_process_count":
                    process_count = len(psutil.pids())
                    tcp_socket.send(f"Processes: {process_count}".encode())
                elif command.startswith("send_file"):
                    print("Manager requested a file. Enter the file path to send:")
                    file_path = input("File Path: ").strip()
                    send_file(tcp_socket, file_path)
                elif command == "restart":
                    tcp_socket.send("Restarting system...".encode())
                    os.system("shutdown -r -t 0")
        except Exception as e:
            print(f"Connection lost: {e}. Attempting to reconnect...")
            tcp_socket.close()

