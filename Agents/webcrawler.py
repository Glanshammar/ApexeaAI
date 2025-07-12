import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

import zmq
import time
from enum import Enum
from multiprocessing import Process
from .agents import Agent, COMMAND_PORT, STATUS_PORT, AgentStatus
from AI.autobrowser import AutoBrowser, BrowserType
import requests
import json
from datetime import datetime, timedelta
from playwright.sync_api import Error, TimeoutError
from playwright.sync_api import sync_playwright
from time import sleep
from typing import List
import re

class WebCrawler(Agent):
    def __init__(self, agent_id):
        super().__init__(agent_id)

    def initialize(self):
        self.logger.info(f"Initializing WebCrawler {self.agent_id}", extra={'agent_id': self.agent_id})
        return True

    def handle_command(self, command):
        """Handle WebCrawler-specific commands"""
        if not self.command_socket:
            self.logger.error("Command socket not initialized", extra={'agent_id': self.agent_id})
            return
        
        if command == "stop" or command == "test":
            super().handle_command(command)
        elif command == "crawl":
            self.logger.info("Received crawl command", extra={'agent_id': self.agent_id})
            self.command_socket.send_string("Crawling")
            self.send_status("Crawling command received and acknowledged")
            self.set_status(AgentStatus.CRAWLING)
            self.Crawl()
            self.set_status(AgentStatus.IDLE)
        elif command.startswith("crawl:"):
            # Handle parameterized crawl commands
            try:
                limits = command.split(":", 1)[1].strip()
                
                self.logger.info(f"Received limited crawl command: {limits}", 
                               extra={'agent_id': self.agent_id})
                self.command_socket.send_string(f"Crawling with limits: {limits}")
                
                self.set_status(AgentStatus.CRAWLING)
                self.Crawl()
                self.set_status(AgentStatus.IDLE)
            except Exception as e:
                error_msg = f"Error parsing crawl limits: {str(e)}"
                self.logger.error(error_msg, extra={'agent_id': self.agent_id})
                self.command_socket.send_string(f"Error: {error_msg}")
        else:
            self.command_socket.send_string(f"Unknown command: {command}")
            self.send_status(f"Received unknown command: {command}")

    def Crawl(self):
        """Crawl the web. This is the main function that will be called when the crawl command is received.
        You must implement this function.
        """
        self.logger.info(f"Starting crawl operation", extra={'agent_id': self.agent_id})
        self.send_status(f"Starting crawl operation")
        
