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
from AutoBrowser import AutoBrowser, BrowserType
import requests
import json
from datetime import datetime, timedelta


class WebCrawler(Agent):
    def __init__(self, agent_id):
        super().__init__(agent_id)
        self.portals_to_crawl = []
        self.results_dir = os.path.join(current_dir, 'crawl_results')
        self.cache_dir = os.path.join(current_dir, 'cache')
        self.documents_dir = os.path.join(current_dir, f'documents')
        os.makedirs(self.documents_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.logger.debug(f"Results directory: {self.results_dir}", extra={'agent_id': self.agent_id})
        
        # Test mode limits (configurable via command)
        self.test_mode = False
        self.max_portal_links = 2     # Max number of tender links to extract from each portal
        self.max_tender_pages = 3     # Max number of tender pages to process
        self.max_document_links = 2   # Max number of document links to extract per tender
        self.max_documents = 3        # Max number of documents to download and process

    def Initialize(self):
        self.logger.info("Initializing crawler data", extra={'agent_id': self.agent_id})
        self.portals_to_crawl = self.UpdatePortals()
        self.logger.info(f"Initialized with {len(self.portals_to_crawl)} portals", extra={'agent_id': self.agent_id})
        return True


    def Crawl(self):
        try:
            self.logger.info(f"Starting crawl operation", extra={'agent_id': self.agent_id})
            self.send_status(f"Starting crawl operation")
            
            browser = AutoBrowser(BrowserType.Chromium)
            try: 
                success_msg = f""" """
                self.logger.info(success_msg, extra={'agent_id': self.agent_id})
                self.send_status(success_msg)
            finally:
                browser.Quit()
        except Exception as e:
            error_msg = f"Error during crawl: {str(e)}"
            self.logger.error(error_msg, extra={'agent_id': self.agent_id})
            self.send_status(error_msg)

    def run(self):
        self.running = True
        self.logger.info(f"WebCrawler {self.agent_id} starting", extra={'agent_id': self.agent_id})
        self.send_status(f"WebCrawler {self.agent_id} started")

        # Initialize the crawler data
        if not self.Initialize():
            self.logger.error("Failed to initialize crawler data", extra={'agent_id': self.agent_id})
            self.send_status("Failed to initialize crawler data")
            return

        # Initialize ZMQ context and sockets in the child process
        self.context = zmq.Context()
        
        # Setup command socket (bind)
        self.command_socket = self.context.socket(zmq.REP)
        port = int(self.agent_id) + COMMAND_PORT
        self.command_socket.bind(f"tcp://*:{port}")
        self.logger.debug(f"Command socket bound to port {port}", extra={'agent_id': self.agent_id})
        self.send_status(f"WebCrawler {self.agent_id} command socket bound to port {port}")

        # Setup status socket (connect to manager's PUB)
        self.status_socket = self.context.socket(zmq.PUB)
        self.status_socket.connect(f"tcp://localhost:{STATUS_PORT}")
        self.logger.debug(f"Status socket connected to port {STATUS_PORT}", extra={'agent_id': self.agent_id})
        self.send_status(f"WebCrawler {self.agent_id} status socket connected to port {STATUS_PORT}")

        poller = zmq.Poller()
        poller.register(self.command_socket, zmq.POLLIN)

        # Send initial status
        try:
            self.status_socket.send_multipart([
                str(self.agent_id).encode(),
                f"WebCrawler initialized with {len(self.portals_to_crawl)} URLs to crawl".encode()
            ])
            self.logger.info(f"Initial status sent with {len(self.portals_to_crawl)} URLs", extra={'agent_id': self.agent_id})
            self.send_status(f"WebCrawler {self.agent_id} sent initial status")
        except Exception as e:
            error_msg = f"Error sending initial status: {str(e)}"
            self.logger.error(error_msg, extra={'agent_id': self.agent_id})
            self.send_status(error_msg)

        while self.running:
            try:
                # Poll for commands with timeout (500ms)
                socks = dict(poller.poll(500))

                if self.command_socket in socks:
                    try:
                        command = self.command_socket.recv_string(zmq.NOBLOCK)
                        self.logger.debug(f"Received command: {command}", extra={'agent_id': self.agent_id})
                        
                        if command == "stop":
                            self.logger.info("Received stop command", extra={'agent_id': self.agent_id})
                            self.command_socket.send_string("Stopping")
                            self.status_socket.send_multipart([
                                str(self.agent_id).encode(),
                                "Received stop command, shutting down".encode()
                            ])
                            self.Stop()
                            continue
                        elif command == "test":
                            self.logger.debug("Received test command", extra={'agent_id': self.agent_id})
                            self.command_socket.send_string("Test received")
                            self.status_socket.send_multipart([
                                str(self.agent_id).encode(),
                                "Test command received and acknowledged".encode()
                            ])
                        elif command == "crawl":
                            self.logger.info("Received crawl command", extra={'agent_id': self.agent_id})
                            self.command_socket.send_string("Crawling")
                            self.status_socket.send_multipart([
                                str(self.agent_id).encode(),
                                "Crawling command received and acknowledged".encode()
                            ])
                            self.set_status(AgentStatus.CRAWLING)
                            self.send_status(f'Agent {self.agent_id} status: {self.get_status().name}')
                            self.Crawl()
                            self.set_status(AgentStatus.IDLE)
                            self.send_status(f'Agent {self.agent_id} status: {self.get_status().name}')
                        elif command.startswith("crawl:"):
                            try:
                                # Parse limits from command like "crawl:3,2" (3 tenders, 2 documents)
                                limits = command.split(":", 1)[1].strip()
                                parts = limits.split(",")
                                
                                max_tenders = int(parts[0]) if len(parts) > 0 and parts[0] else None
                                max_documents = int(parts[1]) if len(parts) > 1 and parts[1] else None
                                
                                self.logger.info(f"Received limited crawl command: max_tenders={max_tenders}, max_documents={max_documents}", 
                                               extra={'agent_id': self.agent_id})
                                self.command_socket.send_string(f"Crawling with limits: tenders={max_tenders}, documents={max_documents}")
                                
                                self.set_status(AgentStatus.CRAWLING)
                                self.send_status(f'Agent {self.agent_id} status: {self.get_status().name}')
                                self.Crawl()
                                self.set_status(AgentStatus.IDLE)
                                self.send_status(f'Agent {self.agent_id} status: {self.get_status().name}')
                            except Exception as e:
                                error_msg = f"Error parsing crawl limits: {str(e)}"
                                self.logger.error(error_msg, extra={'agent_id': self.agent_id})
                                self.command_socket.send_string(f"Error: {error_msg}")
                        else:
                            error_msg = f"Received unknown command: {command}"
                            self.logger.warning(error_msg, extra={'agent_id': self.agent_id})
                            self.command_socket.send_string(f"Unknown command: {command}")
                            self.status_socket.send_multipart([
                                str(self.agent_id).encode(),
                                error_msg.encode()
                            ])
                    except zmq.Again:
                        pass

            except Exception as e:
                error_msg = f"Error in WebCrawler main loop: {str(e)}"
                self.logger.error(error_msg, extra={'agent_id': self.agent_id})
                self.send_status(error_msg)
                time.sleep(1)  # Prevent tight loop in case of errors

        try:
            self.status_socket.send_multipart([
                str(self.agent_id).encode(),
                "WebCrawler shutting down".encode()
            ])
            self.logger.info("Shutdown message sent", extra={'agent_id': self.agent_id})
        except Exception as e:
            error_msg = f"Error sending shutdown status: {str(e)}"
            self.logger.error(error_msg, extra={'agent_id': self.agent_id})
            self.send_status(error_msg)
        
        self.Close()