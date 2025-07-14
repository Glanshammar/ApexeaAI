import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QListWidgetItem, QTextEdit, QPushButton, QLabel, 
                             QSplitter, QFrame, QLineEdit, QMessageBox, QSizePolicy)
from PyQt6.QtCore import Qt, QSize, pyqtSlot
import os
from datetime import datetime
import sqlite3
from PyQt6.QtGui import QIcon, QFont


# Create a custom widget for chat list items with delete button
class ChatItemWidget(QWidget):
    def __init__(self, title, chat_id, parent=None):
        super().__init__(parent)
        self.chat_id = chat_id
        self.title = title
        self.parent_list = parent
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 5, 8)
        layout.setSpacing(5)
        
        # Chat title - fix the label appearance
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("""
            color: #ffffff; 
            font-size: 14px;
            padding: 5px;
        """)
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(150)  # Ensure minimum width for text
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        layout.addWidget(self.title_label, 1)
        
        # Delete button (keep as is)
        self.delete_button = QPushButton("×")
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #777777;
                font-size: 16px;
                font-weight: bold;
                border: none;
                padding: 2px 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #ff3333;
                color: white;
            }
        """)
        self.delete_button.setMaximumWidth(30)
        self.delete_button.clicked.connect(self.on_delete_clicked)
        layout.addWidget(self.delete_button, 0)
        
        # Ensure the widget takes full width of the list item
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, 
            QSizePolicy.Policy.Preferred
        )


    def on_delete_clicked(self):
        # Find the chat app instance (parent of the list widget)
        chat_app = None
        parent = self.parent_list
        while parent:
            if isinstance(parent, ChatApp):
                chat_app = parent
                break
            parent = parent.parent()
        
        if chat_app:
            chat_app.confirm_delete_chat(self.chat_id, self.title)


class ChatMessage(QFrame):
    def __init__(self, text, is_user=False):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "background-color: #e6f7ff; border-radius: 10px; padding: 10px;" 
            if not is_user else 
            "background-color: #dcf8c6; border-radius: 10px; padding: 10px;"
        )
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        sender = QLabel("You" if is_user else "AI")
        sender.setStyleSheet("font-weight: bold; color: #333;")
        
        message = QLabel(text)
        message.setWordWrap(True)
        
        layout.addWidget(sender)
        layout.addWidget(message)


class ChatDatabase:
    def __init__(self, db_path='messages.db'):
        self.db_path = db_path
        self.initialize_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def initialize_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Create tables (existing code)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                is_user BOOLEAN NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats (id)
            )
            ''')
    
    def create_chat(self, title):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO chats (title) VALUES (?)", (title,))
            return cursor.lastrowid
    
    def get_chats(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, created_at FROM chats ORDER BY created_at DESC")
            return cursor.fetchall()
    
    def add_message(self, chat_id, content, is_user):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (chat_id, content, is_user) VALUES (?, ?, ?)",
                (chat_id, content, is_user)
            )
            return cursor.lastrowid
    
    def get_messages(self, chat_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content, is_user, timestamp FROM messages WHERE chat_id = ? ORDER BY timestamp",
                (chat_id,)
            )
            return cursor.fetchall()
    
    def close(self):
        # The original code had self.conn.close(), but self.conn was removed.
        # Assuming the intent was to close the connection if it were managed differently.
        # Since the original code had self.conn, and self.conn is no longer initialized,
        # this method effectively does nothing now.
        pass


class ChatApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ApexeaAI Chat")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize database
        self.db = ChatDatabase()
        
        # Current chat id
        self.current_chat_id = None
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        
        # Create a splitter for resizable sidebar and chat area
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Sidebar for chat list
        sidebar_widget = QWidget()
        sidebar_widget.setStyleSheet("background-color: #1a1a1a; border-right: 1px solid #333333;")
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(10, 15, 10, 15)
        
        # Header for sidebar
        new_chat_btn = QPushButton("New Chat")
        new_chat_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #4CAF50; color: white;")
        new_chat_btn.clicked.connect(self.create_new_chat)
        sidebar_layout.addWidget(new_chat_btn)
        
        # Chat list
        self.chat_list = QListWidget()
        self.chat_list.setStyleSheet("QListWidget { background-color: #252525; border: none; color: #ffffff; border-radius: 5px; }")
        self.chat_list.itemClicked.connect(self.on_chat_selected)
        sidebar_layout.addWidget(self.chat_list)
        
        # Main chat area
        chat_area = QWidget()
        chat_layout = QVBoxLayout(chat_area)
        
        # Scroll area for messages
        self.messages_scroll = QTextEdit()
        self.messages_scroll.setReadOnly(True)
        self.messages_scroll.setStyleSheet("border: none; background-color: #1e1e1e; color: #e0e0e0;")
        
        # Chat messages container
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(15)
        
        # Add welcome message when no chat is selected
        self.welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(self.welcome_widget)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        welcome_title = QLabel("Welcome to ApexeaAI Chat")
        welcome_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #e0e0e0;")
        welcome_desc = QLabel("Select a chat from the sidebar or create a new one to get started.")
        welcome_desc.setStyleSheet("font-size: 16px; color: #b0b0b0;")
        
        welcome_layout.addWidget(welcome_title)
        welcome_layout.addWidget(welcome_desc)
        
        chat_layout.addWidget(self.welcome_widget)
        
        # Input area
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.setMaximumHeight(100)
        self.message_input.setStyleSheet("border-radius: 15px; padding: 10px; background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d;")
        
        send_button = QPushButton()
        send_button.setIcon(QIcon.fromTheme("mail-send"))
        send_button.setText("Send")
        send_button.setStyleSheet("padding: 10px; background-color: #4CAF50; color: white;")
        send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.message_input, 5)
        input_layout.addWidget(send_button, 1)
        
        chat_layout.addWidget(self.messages_scroll, 5)
        chat_layout.addWidget(input_container, 1)
        
        # Add widgets to splitter
        splitter.addWidget(sidebar_widget)
        splitter.addWidget(chat_area)
        
        # Set the initial sizes of the splitter
        splitter.setSizes([300, 900])  # Sidebar width: 300px, Chat area: 900px
        
        # Set the style
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QListWidget {
                background-color: #252525;
                border: none;
                color: #ffffff;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #333333;
                color: #ffffff;
                font-size: 14px;
            }
            QListWidget::item:hover {
                background-color: #353535;
            }
            QListWidget::item:selected {
                background-color: #404040;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton {
                border-radius: 5px;
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)

        # Update the welcome widget styles
        welcome_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #e0e0e0;")
        welcome_desc.setStyleSheet("font-size: 16px; color: #b0b0b0;")

        # Update messages_scroll style
        self.messages_scroll.setStyleSheet("border: none; background-color: #1e1e1e; color: #e0e0e0;")

        # Update message input style
        self.message_input.setStyleSheet("border-radius: 15px; padding: 10px; background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d;")

        # Load existing chats
        self.load_chats()

    def load_chats(self):
        """Load existing chats from database"""
        self.chat_list.clear()
        chats = self.db.get_chats()
        
        for chat_id, title, created_at in chats:
            item = QListWidgetItem(self.chat_list)
            chat_widget = ChatItemWidget(title, chat_id, self.chat_list)
            item.setSizeHint(chat_widget.sizeHint())
            self.chat_list.addItem(item)
            self.chat_list.setItemWidget(item, chat_widget)
        
        # If no chats exist, create a default one
        if not chats:
            self.create_new_chat()

    def create_new_chat(self):
        """Create a new chat"""
        title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        chat_id = self.db.create_chat(title)
        
        item = QListWidgetItem(self.chat_list)
        chat_widget = ChatItemWidget(title, chat_id, self.chat_list)
        item.setSizeHint(chat_widget.sizeHint())
        self.chat_list.insertItem(0, item)
        self.chat_list.setItemWidget(item, chat_widget)
        self.chat_list.setCurrentItem(item)
        
        self.on_chat_selected(item, chat_id)

    def confirm_delete_chat(self, chat_id, title):
        """Show confirmation dialog for deleting a chat"""
        confirm = QMessageBox()
        confirm.setWindowTitle("Delete Chat")
        confirm.setText(f"Are you sure you want to delete the chat '{title}'?")
        confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        confirm.setIcon(QMessageBox.Icon.Question)
        
        if confirm.exec() == QMessageBox.StandardButton.Yes:
            self.delete_chat(chat_id)

    def delete_chat(self, chat_id):
        """Delete a chat from database and UI"""
        # Remove from database
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # First delete all messages
            cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            # Then delete the chat
            cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        
        # Remove from UI
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            widget = self.chat_list.itemWidget(item)
            if widget and isinstance(widget, ChatItemWidget) and widget.chat_id == chat_id:
                self.chat_list.takeItem(i)
                break
        
        # If current chat was deleted, clear the chat area
        if self.current_chat_id == chat_id:
            self.current_chat_id = None
            self.messages_scroll.clear()
            self.welcome_widget.setVisible(True)

    @pyqtSlot(QListWidgetItem)
    def on_chat_selected(self, item, chat_id=None):
        """Handle chat selection"""
        # Get chat_id from widget
        widget = self.chat_list.itemWidget(item)
        if widget and isinstance(widget, ChatItemWidget):
            chat_id = widget.chat_id
        else:
            return
        
        self.current_chat_id = chat_id
        self.welcome_widget.setVisible(False)
        self.messages_scroll.setVisible(True)
        
        self.load_messages(chat_id)

    def load_messages(self, chat_id):
        self.messages_scroll.clear()
        
        messages = self.db.get_messages(chat_id)
        
        for msg_id, content, is_user, timestamp in messages:
            self.add_message_to_ui(content, bool(is_user))

    def add_message_to_ui(self, text, is_user):
        """Add a message to the UI with improved dark mode styling"""
        # Define colors based on sender
        bg_color = "#4F8EF7" if is_user else "#52ff52"  # Blue for user, green for AI
        name_color = "#FFFFFF" if is_user else "#000000"  # White on blue, black on green
        time_color = "#E0E0E0" if is_user else "#006600"  # Light gray for user, dark green for AI
        
        # Use a more robust HTML structure with table for consistent background
        msg_html = f"""
        <table style="margin: 15px 10px; max-width: 85%; border-collapse: collapse; 
                     border-radius: 18px; background-color: {bg_color}; 
                     box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                     {'margin-left: auto;' if is_user else ''}">
          <tr>
            <td style="padding: 15px; color: #ffffff; border-radius: 18px;">
              <div style="font-weight: bold; margin-bottom: 6px; font-size: 14px; color: {name_color};">
                {'You' if is_user else 'AI'}
              </div>
              <div style="word-wrap: break-word; color: {name_color}; font-size: 16px; line-height: 1.4;">
                {text}
              </div>
              <div style="text-align: right; font-size: 11px; margin-top: 5px; color: {time_color};">
                {datetime.now().strftime('%H:%M')}
              </div>
            </td>
          </tr>
        </table>
        """
        
        self.messages_scroll.append(msg_html)
        
        # Scroll to bottom
        scrollbar = self.messages_scroll.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot()
    def send_message(self):
        if not self.current_chat_id:
            return
            
        message_text = self.message_input.toPlainText().strip()
        if not message_text:
            return
            
        # Save user message to database
        self.db.add_message(self.current_chat_id, message_text, True)
        
        # Add message to UI
        self.add_message_to_ui(message_text, True)
        
        # Clear input field
        self.message_input.clear()
        
        # In a real application, you would send the message to an AI service
        # and get a response, then save it to the database
        # For now, we'll just mock an AI response
        ai_response = "This is a mock AI response. In a real application, you would get a response from an AI service."
        self.db.add_message(self.current_chat_id, ai_response, False)
        self.add_message_to_ui(ai_response, False)

    def closeEvent(self, event):
        """Clean up database connection when closing the app"""
        self.db.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatApp()
    window.show()
    sys.exit(app.exec())
