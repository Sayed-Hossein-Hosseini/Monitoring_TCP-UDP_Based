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