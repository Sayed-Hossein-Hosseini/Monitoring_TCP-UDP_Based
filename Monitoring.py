import socket
import threading
import psutil
import os
import time
import subprocess

# ==================== Agent Code ====================
AUTHORIZED_AGENTS = {"127.0.0.1"}  # Allowed agent IPs
AGENTS = []  # List to hold information about connected agents


def reconnect_tcp(manager_ip, manager_port):
    """Try to reconnect to the manager if the connection is lost."""
    counter = 0
    while True:
        try:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.settimeout(10)  # Set timeout only for the connection attempt
            tcp_socket.connect((manager_ip, manager_port))
            tcp_socket.settimeout(None)  # Disable timeout after successful connection
            print(f"Successfully connected to Manager at {manager_ip}:{manager_port}")
            return tcp_socket
        except Exception as e:
            counter += 1
            print(f"Reconnection attempt {counter} failed: {e}. Retrying in 5 seconds...")
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
                try:
                    command = tcp_socket.recv(1024).decode()
                    if not command:
                        print("Connection closed by the manager.")
                        break

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
                    elif command == "get_logs":
                        logs = get_system_logs()
                        tcp_socket.send(logs.encode() if logs else "No logs available".encode())
                    elif command.startswith("send_file"):
                        print("Manager requested a file. Enter the file path to send:")
                        file_path = input("File Path: ").strip()
                        send_file(tcp_socket, file_path)
                    elif command == "restart":
                        tcp_socket.send("Restarting system...".encode())
                        os.system("shutdown -r -t 0")
                except Exception as e:
                    print(f"Error in communication: {e}. Reconnecting...")
                    break

        except Exception as e:
            print(f"Connection lost: {e}. Attempting to reconnect...")
            try:
                tcp_socket.send("AGENT_DISCONNECTED".encode())
            except:
                pass
            tcp_socket.close()
def get_system_logs():
    """Retrieve system logs with proper permissions."""
    if os.name == "nt":  # Windows
        try:
            result = subprocess.run(
                ["wevtutil", "qe", "Application", "/c:10", "/rd:true", "/f:text"],
                capture_output=True, text=True, check=True
            )
            return result.stdout if result.stdout else "No logs available"
        except Exception as e:
            return f"Error retrieving Windows logs: {e}"
    else:  # Linux/macOS
        log_file = "/var/log/syslog" if os.path.exists("/var/log/syslog") else None
        if log_file:
            try:
                with open(log_file, "r", errors="ignore") as f:
                    logs = f.readlines()[-10:]
                return "\n".join(logs) if logs else "No logs available"
            except Exception as e:
                return f"Error retrieving Linux logs: {e}"
        return "System log file not found."


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
    previous_cpu_state = "normal"  # Track the previous CPU state (normal or high)

    while True:
        cpu_usage = psutil.cpu_percent(interval=1)

        if cpu_usage > 80 and previous_cpu_state == "normal":
            # CPU usage crossed 80% threshold (normal -> high)
            event_message = f"Agent ID: {agent_id}, High CPU Usage Alert: {cpu_usage}%"
            try:
                udp_socket.sendto(event_message.encode(), (manager_ip, udp_port))
                print(f"High CPU Usage Alert: {cpu_usage}%")  # Print only when state changes
                previous_cpu_state = "high"  # Update the state
            except Exception as e:
                print(f"Error sending UDP alert: {e}")

        elif cpu_usage <= 80 and previous_cpu_state == "high":
            # CPU usage returned to normal (high -> normal)
            normal_message = f"Agent ID: {agent_id}, CPU Usage Back to Normal: {cpu_usage}%"
            try:
                udp_socket.sendto(normal_message.encode(), (manager_ip, udp_port))
                print(f"CPU Usage Back to Normal: {cpu_usage}%")  # Print only when state changes
                previous_cpu_state = "normal"  # Update the state
            except Exception as e:
                print(f"Error sending UDP normal message: {e}")

        time.sleep(5)  # Add a delay to avoid spamming

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
                selected_agent = int(input("Select an agent by number or enter 0 to exit: ")) - 1
                if selected_agent == -1:
                    print("Shutting Down :)")
                    os._exit(0)
                if 0 <= selected_agent < len(AGENTS):
                    selected_id = AGENTS[selected_agent]['id']
                    selected_socket = AGENTS[selected_agent]['socket']
                    print(f"Selected Agent: {selected_id}")

                    while True:
                        print("\nAvailable Commands:")
                        print("1. Get_Status")
                        print("2. Get_Process_Count")
                        print("3. Get_Logs")
                        print("4. Get_File")
                        print("5. Restart")
                        print("6. Back to Agent List")
                        command_number = input("Enter command number: ").strip()
                        commands = {"1": "get_status", "2": "get_process_count", "3": "get_logs", "4": "send_file",
                                    "5": "restart", "6": "back"}
                        if command_number in commands:
                            command = commands[command_number]
                            if command == "back":
                                break
                            selected_socket.send(command.encode())
                            if command == "send_file":
                                receive_file(selected_socket)
                            else:
                                response = selected_socket.recv(4096).decode()
                                if response == "AGENT_DISCONNECTED":
                                    print(f"Agent {selected_id} has disconnected.")
                                    AGENTS.remove(AGENTS[selected_agent])
                                    break
                                print(f"Agent Response: {response}")
                        else:
                            print("Invalid command number. Try again.")
                else:
                    print("Invalid selection. Try again.")
            except ValueError:
                print("Invalid input. Please enter a valid number.")
            except Exception as e:
                print(f"Client Handler Error: {e}")
                break
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
        print("Receiving file address from agent, please wait...")
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


def start_manager(tcp_port, udp_port):
    """Start the central manager."""
    # Start UDP server in a separate thread
    def udp_server():
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(("", udp_port))
        while True:
            try:
                data, addr = udp_socket.recvfrom(1024)
                message = data.decode()
                print(f"Received UDP message from {addr}: {message}")
            except Exception as e:
                print(f"UDP server error: {e}")

    threading.Thread(target=udp_server, daemon=True).start()

    # Start TCP server
    while True:
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind(("", tcp_port))
            server_socket.listen(5)
            print(f"Manager listening on TCP port {tcp_port}...")
            print(f"Manager listening on UDP port {udp_port}...")

            while True:
                client_socket, client_address = server_socket.accept()
                threading.Thread(target=handle_client, args=(client_socket, client_address, udp_port), daemon=True).start()
        except Exception as e:
            print(f"Manager error: {e}. Restarting in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    mode = input("Start as (Manager/Agent): ").strip().lower()
    if mode == "manager":
        tcp_port = 5005
        udp_port = 5006
        start_manager(tcp_port, udp_port)
    elif mode == "agent":
        manager_ip = input("Enter Manager IP: ").strip()
        manager_port = 5005
        agent_tcp_handler(manager_ip, manager_port)
    else:
        print("Invalid mode. Exiting.")
