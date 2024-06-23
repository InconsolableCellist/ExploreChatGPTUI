import json
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, Menu
import webbrowser
import os
import tempfile
import argparse
from datetime import datetime

class ChatSearchApp:
    def __init__(self, root, file_path=None):
        self.root = root
        self.root.title("ChatGPT Conversation Search")
        self.create_widgets()
        self.matches = []  # Initialize matches attribute
        if file_path:
            self.load_file(file_path)

    def create_widgets(self):
        # Frame for file input and load button
        file_frame = ttk.Frame(self.root)
        file_frame.pack(padx=10, pady=10, fill=tk.X)

        ttk.Label(file_frame, text="JSON File:").pack(side=tk.LEFT, padx=5)
        self.file_entry = ttk.Entry(file_frame, width=50)
        self.file_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Load", command=self.load_file_picker).pack(side=tk.LEFT, padx=5)

        # Frame for regex input and search buttons
        search_frame = ttk.Frame(self.root)
        search_frame.pack(padx=10, pady=10, fill=tk.X)

        ttk.Label(search_frame, text="Search Regex:").pack(side=tk.LEFT, padx=5)
        self.regex_entry = ttk.Entry(search_frame, width=50)
        self.regex_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Search", command=self.perform_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=5)

        # Treeview for displaying search results
        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.tree_scrollbar = ttk.Scrollbar(tree_frame)
        self.tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(tree_frame, columns=("Entry Number", "Title", "Date Created"), show="headings", yscrollcommand=self.tree_scrollbar.set)
        self.tree.heading("Entry Number", text="Entry Number", command=lambda: self.sort_tree("Entry Number", False))
        self.tree.heading("Title", text="Title", command=lambda: self.sort_tree("Title", False))
        self.tree.heading("Date Created", text="Date Created", command=lambda: self.sort_tree("Date Created", False))
        self.tree.column("Entry Number", width=100, anchor=tk.CENTER)
        self.tree.column("Title", width=300)
        self.tree.column("Date Created", width=150, anchor=tk.CENTER)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_single_click)

        self.tree_scrollbar.config(command=self.tree.yview)

        # Text box for displaying conversation details
        self.details_text = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=80, height=20, bg='white')
        self.details_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.details_text.bind("<Button-3>", self.show_context_menu)
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy_text)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def copy_text(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.details_text.selection_get())
        except tk.TclError:
            pass

    def load_file_picker(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path):
        self.file_entry.delete(0, tk.END)
        self.file_entry.insert(0, file_path)
        self.chat_data = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                self.chat_data = json.load(file)
            self.status_var.set("File loaded successfully.")
            self.display_all_conversations()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")
            self.status_var.set("Failed to load file.")
            self.chat_data = None

        self.chat_data.sort(key=lambda x: int(x.get('create_time', 0)))

    def display_all_conversations(self):
        self.tree.delete(*self.tree.get_children())
        for i, conversation in enumerate(self.chat_data):
            date_created = self.convert_timestamp(conversation.get('create_time', 'Unknown'))
            self.tree.insert("", "end", iid=i, values=(i, conversation['title'], date_created))

    def convert_timestamp(self, timestamp):
        try:
            dt = datetime.fromtimestamp(int(timestamp))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return 'Unknown'

    def perform_search(self):
        if not hasattr(self, 'chat_data'):
            messagebox.showerror("Error", "Please load a JSON file first.")
            return

        regex = self.regex_entry.get().strip()
        if not regex:
            self.clear_search()
            return

        # Ensure whole word match for the search term
        regex = fr"\b{regex}\b"

        self.tree.delete(*self.tree.get_children())
        self.matches = self.search_conversations(self.chat_data, regex)
        for i, (index, title, conversation, _) in enumerate(self.matches):
            date_created = self.convert_timestamp(conversation.get('create_time', 'Unknown'))
            self.tree.insert("", "end", iid=index, values=(index, title, date_created))

        self.status_var.set(f"Found {len(self.matches)} conversations matching the regex '{regex}'.")

    def clear_search(self):
        self.regex_entry.delete(0, tk.END)
        self.display_all_conversations()
        self.status_var.set("Cleared search and displayed all conversations.")

    def search_conversations(self, chat_data, regex_pattern):
        matches = []
        pattern = re.compile(regex_pattern, re.IGNORECASE)
        for i, conversation in enumerate(chat_data):
            if 'mapping' in conversation:
                messages = self.extract_conversations(conversation['mapping'])
                for message in messages:
                    content = message.get('content', '')
                    content_text = self.get_content_text(content)
                    if pattern.search(content_text):
                        matches.append((i, conversation['title'], conversation, messages))
                        break
        return matches

    def extract_conversations(self, mapping):
        conversations = []
        for node_id, node in mapping.items():
            if node and 'message' in node and node['message'] and 'content' in node['message']:
                conversations.append(node['message'])
        return conversations

    def get_content_text(self, content):
        if isinstance(content, str):
            return content
        elif isinstance(content, dict):
            parts = content.get('parts', [])
            if isinstance(parts, list):
                parts_text = [self.get_content_text(part) for part in parts if isinstance(part, (str, dict))]
                return ' '.join(parts_text)
        return ''

    def on_tree_double_click(self, event):
        selected_item = self.tree.selection()[0]
        entry_number = int(selected_item)
        conversation = next((conv for conv in self.matches if conv[0] == entry_number), None)
        if not conversation:
            conversation = (entry_number, self.chat_data[entry_number]['title'], self.chat_data[entry_number], self.extract_conversations(self.chat_data[entry_number]['mapping']))
        self.display_conversation(conversation)

        # Save the selected conversation to a temporary file and open it with the default editor
        formatted_content = self.get_formatted_content(conversation)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(formatted_content.encode('utf-8'))
        webbrowser.open(temp_file_path)

    def on_tree_single_click(self, event):
        selected_item = self.tree.selection()[0]
        entry_number = int(selected_item)
        conversation = next((conv for conv in self.matches if conv[0] == entry_number), None)
        if not conversation:
            conversation = (entry_number, self.chat_data[entry_number]['title'], self.chat_data[entry_number], self.extract_conversations(self.chat_data[entry_number]['mapping']))
        self.display_conversation(conversation)

    def display_conversation(self, conv):
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(tk.END, f"Title: {conv[1]}\n")
        self.details_text.insert(tk.END, f"Date Created: {self.convert_timestamp(conv[2].get('create_time', 'Unknown'))}\n\n")
        for message in conv[3]:
            role = message.get('author', 'unknown')
            if isinstance(role, dict):
                role = role.get('name', 'unknown')
            content = message.get('content', '')
            content_text = self.get_content_text(content)
            self.details_text.insert(tk.END, f"{role.capitalize() if isinstance(role, str) else 'unknown'}: {content_text}\n\n")

    def get_formatted_content(self, conv):
        formatted_content = f"Title: {conv[1]}\n"
        formatted_content += f"Date Created: {self.convert_timestamp(conv[2].get('create_time', 'Unknown'))}\n\n"
        for message in conv[3]:
            role = message.get('author', 'unknown')
            if isinstance(role, dict):
                role = role.get('name', 'unknown')
            content = message.get('content', '')
            content_text = self.get_content_text(content)
            formatted_content += f"{role.capitalize() if isinstance(role, str) else 'unknown'}: {content_text}\n\n"
        return formatted_content

    def sort_tree(self, col, reverse):
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        l.sort(reverse=reverse)

        for index, (val, k) in enumerate(l):
            self.tree.move(k, '', index)

        self.tree.heading(col, command=lambda: self.sort_tree(col, not reverse))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search and display ChatGPT conversations from an exported JSON file.")
    parser.add_argument('file', nargs='?', help="Path to the exported chat history JSON file", default=None)
    args = parser.parse_args()

    root = tk.Tk()
    app = ChatSearchApp(root, file_path=args.file)
    root.mainloop()
