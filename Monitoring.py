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

def send_file(tcp_socket, file_path):
    """Send a file to the manager."""
    try:
        if not os.path.exists(file_path):
            tcp_socket.send("ERROR: File not found.".encode())
            return

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        tcp_socket.send(f"FILE {file_name} {file_size}".encode())

        ack = tcp_socket.recv(1024).decode()
        if ack != "READY":
            print("Manager not ready to receive file.")
            return

        with open(file_path, "rb") as f:
            while chunk := f.read(1024):
                tcp_socket.send(chunk)

        print(f"File '{file_name}' sent successfully.")
        tcp_socket.send("FILE_SENT".encode())
    except Exception as e:
        print(f"Error sending file: {e}")

def monitor_system(manager_ip, udp_port, agent_id):
    """Monitor system and send events to the manager via UDP."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:
        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage > 80:
            event_message = f"Agent ID: {agent_id}, High CPU Usage Alert: {cpu_usage}%"
            udp_socket.sendto(event_message.encode(), (manager_ip, udp_port))

# ==================== Manager Code ====================
def handle_client(client_socket, client_address, udp_port):
    """Handle communication with a connected agent."""
    try:
        if client_address[0] not in AUTHORIZED_AGENTS:
            print(f"Unauthorized agent {client_address[0]} attempted to connect. Connection refused.")
            client_socket.close()
            return

        agent_id = client_socket.recv(1024).decode()
        AGENTS.append({"id": agent_id, "address": client_address, "socket": client_socket})
        print(f"Authorized agent {agent_id} connected: {client_address}")

        client_socket.send(str(udp_port).encode())

        while True:
            print("\nAvailable Agents:")
            for i, agent in enumerate(AGENTS):
                print(f"{i + 1}. ID: {agent['id']}, Address: {agent['address']}")

            try:
                selected_agent = int(input("Select a representative by number or turn off the program by entering the number 0: ")) - 1
                if selected_agent == -1:
                    print("Shutting Down :)")
                    os._exit(0)
                if 0 <= selected_agent < len(AGENTS):
                    selected_id = AGENTS[selected_agent]['id']
                    selected_socket = AGENTS[selected_agent]['socket']
                    print(f"Selected Agent: {selected_id}")
                    print("\nAvailable Commands:")
                    print("1. Get_Status")
                    print("2. Get_Process_Count")
                    print("3. Get_File")
                    print("4. Restart")
                    command_number = input("Enter command number: ").strip()
                    commands = {"1": "get_status", "2": "get_process_count", "3": "send_file", "4": "restart"}
                    if command_number in commands:
                        command = commands[command_number]
                        selected_socket.send(command.encode())
                        if command == "send_file":
                            receive_file(selected_socket)
                        else:
                            response = selected_socket.recv(1024).decode()
                            print(f"Agent Response: {response}")
                    else:
                        print("Invalid command number. Try again.")
                else:
                    print("Invalid selection. Try again.")
            except ValueError:
                print("Invalid input. Please enter a valid number.")
    except Exception as e:
        print(f"Client Handler Error: {e}")
    finally:
        disconnected_agent = next((agent for agent in AGENTS if agent['socket'] == client_socket), None)
        if disconnected_agent:
            print(f"Agent {disconnected_agent['id']} disconnected.")
            AGENTS.remove(disconnected_agent)
        client_socket.close()
        print("\nUpdated Available Agents:")
        for i, agent in enumerate(AGENTS):
            print(f"{i + 1}. ID: {agent['id']}, Address: {agent['address']}")

def receive_file(client_socket):
    """Receive a file from the agent."""
    try:
        metadata = client_socket.recv(1024).decode()
        if not metadata.startswith("FILE"):
            print("Invalid file metadata received.")
            return

        _, file_name, file_size = metadata.split()
        file_size = int(file_size)

        print(f"Receiving file: {file_name}")

        client_socket.send("READY".encode())

        with open(file_name, "wb") as f:
            received = 0
            while received < file_size:
                data = client_socket.recv(1024)
                f.write(data)
                received += len(data)

        print(f"File '{file_name}' received successfully.")
        client_socket.send("File received successfully.".encode())
    except Exception as e:
        print(f"Error receiving file: {e}")