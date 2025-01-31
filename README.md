# Agent-Manager Monitoring and Management System

This project is a network-based monitoring and management system consisting of two main components: **Manager** (central server) and **Agent** (client). It allows network administrators to monitor the status of networked systems and send various commands to them.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Features](#features)
3. [Project Structure](#project-structure)
4. [How to Run](#how-to-run)
5. [Configuration](#configuration)
6. [Usage Examples](#usage-examples)
7. [Contribution](#contribution)
8. [License](#license)

---

## Introduction

This project is designed for managing and monitoring networked systems. It consists of two main components:

- **Manager**: The central server responsible for managing and receiving information from Agents.
- **Agent**: Clients that connect to the Manager and send system information.

The system uses TCP and UDP protocols for communication between the Manager and Agents.

---

## Features

### 1. **System Monitoring**
   - **CPU Usage**: Sends an alert when CPU usage exceeds 80% and notifies when it returns to normal.
   - **Memory Usage**: Reports the percentage of RAM usage.
   - **Disk Usage**: Reports the percentage of disk space usage.
   - **Network Status**: Reports the amount of data sent and received over the network.
   - **System Uptime**: Reports the system's uptime.

### 2. **Sending Commands to Agents**
   - **Get System Status**: Retrieves complete system status information from the Agent.
   - **Get Process Count**: Retrieves the number of processes running on the Agent's system.
   - **Get System Logs**: Retrieves the latest system logs (for Windows and Linux).
   - **Receive File from Agent**: Downloads a file from the Agent's system.
   - **Restart Agent System**: Sends a restart command to the Agent's system.

### 3. **Secure Communication**
   - **Authorized Agents List**: Only Agents with IP addresses in the Manager's authorized list can connect to the system.

### 4. **Automatic Reconnection**
   - If the connection between the Agent and Manager is lost, the Agent automatically attempts to reconnect to the Manager.

---

## Project Structure

### Main Files

- **Manager**:
  - `start_manager(tcp_port, udp_port)`: Starts the Manager server and listens for TCP and UDP connections.
  - `handle_client(client_socket, client_address, udp_port)`: Manages communication with each Agent.
  - `udp_server(udp_port)`: UDP server for receiving CPU alerts from Agents.

- **Agent**:
  - `agent_tcp_handler(manager_ip, manager_port)`: Manages communication with the Manager and sends system information.
  - `monitor_system(manager_ip, udp_port, agent_id)`: Monitors CPU status and sends alerts to the Manager.
  - `reconnect_tcp(manager_ip, manager_port)`: Attempts to reconnect to the Manager if the connection is lost.

---

## How to Run

### Prerequisites

- Python 3.x
- Required Libraries:
  - `psutil`
  - `socket`
  - `threading`
  - `os`
  - `time`
  - `subprocess`

To install the required libraries, run the following command:

```bash
pip install psutil
```

### Running the Manager  

1. Download the project files.  
2. Run the following command:  

    ```bash  
    python main.py  
    ```  

3. When prompted, select **Manager**.  
4. The Manager listens on TCP port **5005** and UDP port **5006** by default.  

### Running the Agent  

1. Copy the project files to the Agent's system.  
2. Run the following command:  

    ```bash  
    python main.py  
    ```  

3. When prompted, select **Agent**.  
4. Enter the IP address of the Manager (default is **127.0.0.1**).

---

## Configuration  

- **Ports**: You can change the TCP and UDP ports in the code.  
- **Authorized Agents List**: You can modify the list of authorized Agent IPs in the `AUTHORIZED_AGENTS` variable in the Manager code.
