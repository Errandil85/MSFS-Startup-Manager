import sys
import os
import socket
import threading
import json
from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication


class SingleInstanceManager(QObject):
    """Manages single instance functionality and inter-process communication"""
    
    # Signals
    show_window_requested = Signal()
    shutdown_requested = Signal()
    
    def __init__(self, app_name="MSFSStartupManager"):
        super().__init__()
        self.app_name = app_name
        self.server_name = f"{app_name}_SingleInstance"
        self.server = None
        self.is_primary = False
        
    def try_connect_to_existing(self):
        """Try to connect to existing instance. Returns True if connected."""
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        
        if socket.waitForConnected(1000):
            # Send show command to existing instance
            message = json.dumps({"command": "show"})
            socket.write(message.encode())
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            return True
        
        return False
    
    def start_server(self):
        """Start the local server for single instance communication"""
        # Remove any existing server first
        QLocalServer.removeServer(self.server_name)
        
        self.server = QLocalServer()
        self.server.newConnection.connect(self._handle_new_connection)
        
        if self.server.listen(self.server_name):
            self.is_primary = True
            print(f"Started single instance server: {self.server_name}")
            return True
        else:
            print(f"Failed to start server: {self.server.errorString()}")
            return False
    
    def _handle_new_connection(self):
        """Handle incoming connection from another instance"""
        socket = self.server.nextPendingConnection()
        if socket:
            socket.readyRead.connect(lambda: self._handle_client_message(socket))
    
    def _handle_client_message(self, socket):
        """Handle message from client instance"""
        try:
            data = socket.readAll().data().decode()
            message = json.loads(data)
            
            command = message.get("command")
            if command == "show":
                self.show_window_requested.emit()
            elif command == "shutdown":
                self.shutdown_requested.emit()
                
        except Exception as e:
            print(f"Error handling client message: {e}")
        finally:
            socket.disconnectFromServer()
    
    def send_shutdown_signal(self):
        """Send shutdown signal to running instance"""
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        
        if socket.waitForConnected(1000):
            message = json.dumps({"command": "shutdown"})
            socket.write(message.encode())
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            return True
        
        return False
    
    def cleanup(self):
        """Cleanup server resources"""
        if self.server:
            self.server.close()
            QLocalServer.removeServer(self.server_name)