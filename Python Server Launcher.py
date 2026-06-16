import tkinter as tk
import os
import subprocess
import threading
import json
import datetime

SERVERS_DIR = "servers"
CONFIG_FILE = "config.json"
LOG_DIR = os.path.join(SERVERS_DIR, "logs")

directories = []
current_process = None
history = []
history_index = -1

# RAM STORE
server_ram = {}


# ---------------- CONFIG ----------------
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

def on_close():
    save_config({**config, "theme": THEME})
    root.destroy()

config = load_config()
THEME = config.get("theme", "dark")


# ---------------- LOGGING ----------------
def log(text):
    server = None

    if listbox.curselection():
        server = directories[listbox.curselection()[0]]

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    final = f"[{timestamp}] [{server or 'UI'}] {text}"

    if "[ERROR]" in text:
        console.insert(tk.END, final + "\n", "error")
    elif "[INFO]" in text:
        console.insert(tk.END, final + "\n", "info")
    elif text.startswith(">"):
        console.insert(tk.END, final + "\n", "input")
    else:
        console.insert(tk.END, final + "\n", "normal")

    console.see(tk.END)

    if server:
        try:
            date = datetime.date.today().isoformat()

            safe_server = server.replace('"', '').replace("/", "_").replace("\\", "_")
            folder_name = f"logs for {safe_server}"

            server_dir = os.path.join(LOG_DIR, folder_name)
            os.makedirs(server_dir, exist_ok=True)

            file_path = os.path.join(server_dir, f"{date}.log")

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(final + "\n")

        except Exception:
            pass


def safe_log(text):
    root.after(0, lambda: log(text))


def log_button(cmd):
    log(f"[BUTTON] > {cmd}")


def open_logs_folder():
    os.makedirs(LOG_DIR, exist_ok=True)
    os.startfile(LOG_DIR)
    log("[INFO] Opened logs folder")


# ---------------- SERVERS ----------------
def load_servers():
    global directories
    directories = []

    if not os.path.exists(SERVERS_DIR):
        os.makedirs(SERVERS_DIR)

    for folder in os.listdir(SERVERS_DIR):
        path = os.path.join(SERVERS_DIR, folder)

        if folder == "logs":
            continue

        if os.path.isdir(path):
            directories.append(folder)

    update_listbox()


def update_listbox(filter_text=""):
    if "listbox" not in globals():
        return

    listbox.delete(0, tk.END)
    for d in directories:
        if filter_text.lower() in d.lower():
            listbox.insert(tk.END, d)


# ---------------- RAM SELECT ----------------
def on_server_select(event):
    if listbox.curselection():
        name = directories[listbox.curselection()[0]]
        if name in server_ram:
            ram_slider.set(server_ram[name])
            ram_entry.delete(0, tk.END)
            ram_entry.insert(0, str(server_ram[name]))


# ---------------- SEARCH ----------------
def on_search(*args):
    text = search_var.get()
    if text == "Search servers...":
        text = ""
    update_listbox(text)


def on_search_focus_in(event):
    if search_entry.get() == "Search servers...":
        search_entry.delete(0, tk.END)

    color = "white" if THEME == "dark" else "black"
    search_entry.config(fg=color)


def on_search_focus_out(event):
    if search_entry.get().strip() == "":
        search_entry.insert(0, "Search servers...")
        search_entry.config(fg="gray")


# ---------------- PROCESS ----------------
def is_server_running():
    return current_process is not None and current_process.poll() is None


def find_launch_file(path):
    for f in os.listdir(path):
        lf = f.lower()
        if lf.endswith(".jar") or lf.endswith(".bat") or lf.endswith(".sh"):
            return f
    return None


def send_to_server(cmd):
    global current_process

    if not is_server_running():
        if not hasattr(send_to_server, "warned"):
            log("[ERROR] No running server (start a server first)")
            send_to_server.warned = True
        return

    try:
        current_process.stdin.write(cmd + "\n")
        current_process.stdin.flush()
        log(f"> {cmd}")
    except Exception as e:
        log(f"[ERROR] {e}")


def stop_server():
    global current_process

    if is_server_running():
        try:
            current_process.terminate()
            safe_log("[INFO] Server stopped")
        except Exception as e:
            safe_log(f"[ERROR] Stop failed: {e}")

        current_process = None
        send_to_server.warned = False


# ---------------- LAUNCH ----------------
def launch():
    global current_process

    if is_server_running():
        log("[ERROR] Already running")
        return

    selected = listbox.curselection()
    if not selected:
        log("[ERROR] No server selected")
        return

    folder = directories[selected[0]]
    path = os.path.join(SERVERS_DIR, folder)

    file = find_launch_file(path)
    if not file:
        log("[ERROR] No launch file found")
        return

    full = os.path.join(path, file)

    # RAM ALWAYS FROM ENTRY (safe + synced)
    try:
        ram = int(ram_entry.get())
    except:
        ram = ram_slider.get()

    ram_slider.set(ram)
    ram_entry.delete(0, tk.END)
    ram_entry.insert(0, str(ram))

    server_ram[folder] = ram

    log(f"[INFO] Launching {file} ({ram}MB)")

    def stream(proc):
        for line in proc.stdout:
            if line:
                safe_log(line.rstrip())

    def task():
        global current_process

        try:
            if file.endswith(".jar"):
                current_process = subprocess.Popen(
                    ["java", f"-Xmx{ram}M", "-jar", full],
                    cwd=path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )

            elif file.endswith(".sh"):
                current_process = subprocess.Popen(
                    ["bash", full],
                    cwd=path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True
                )

            elif file.endswith(".bat"):
                current_process = subprocess.Popen(
                    ["cmd", "/c", file],
                    cwd=path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True
                )

            send_to_server.warned = False
            threading.Thread(target=stream, args=(current_process,), daemon=True).start()

        except Exception as e:
            safe_log(f"[ERROR] {e}")

    threading.Thread(target=task, daemon=True).start()


# ---------------- INPUT ----------------
def send_command(event=None):
    global history, history_index

    cmd = input_var.get().strip()
    if not cmd:
        return

    send_to_server(cmd)

    history.append(cmd)
    history_index = len(history)

    input_var.set("")


def history_up(event):
    global history_index
    if history:
        history_index = max(0, history_index - 1)
        input_var.set(history[history_index])
    return "break"


def history_down(event):
    global history_index
    if history:
        history_index = min(len(history) - 1, history_index + 1)
        input_var.set(history[history_index])
    return "break"


# ---------------- OPEN FOLDER ----------------
def open_server_directory():
    try:
        selected = listbox.curselection()

        if selected and len(directories) > 0:
            folder = directories[selected[0]]
            path = os.path.join(SERVERS_DIR, folder)
        else:
            path = SERVERS_DIR

        os.startfile(path)
        log("[INFO] Opened folder")

    except Exception as e:
        log(f"[ERROR] {e}")


def on_listbox_click(event):
    index = listbox.nearest(event.y)

    if index < 0 or index >= listbox.size():
        listbox.selection_clear(0, tk.END)
        return

    bbox = listbox.bbox(index)

    if bbox is None:
        listbox.selection_clear(0, tk.END)
        return

    if listbox.selection_includes(index):
        listbox.selection_clear(0, tk.END)
        return


# ---------------- THEME ----------------
def apply_theme():
    global THEME

    if THEME == "dark":
        bg = "#1b1b1b"
        fg = "#d0d0d0"
        box = "#222222"
        entry_bg = "#202020"
        console_bg = "#101010"
        accent = "#444444"
    else:
        bg = "#f2f2f2"
        fg = "#111111"
        box = "#ffffff"
        entry_bg = "#ffffff"
        console_bg = "#ffffff"
        accent = "#cccccc"

    root.configure(bg=bg)

    search_entry.config(bg=entry_bg)

    if search_entry.get() != "Search servers...":
        color = "white" if THEME == "dark" else "black"
        search_entry.config(fg=color, insertbackground=color)

    listbox.config(bg=box, fg=fg, selectbackground=accent)

    for w in btn_frame.winfo_children():
        w.config(bg=box, fg=fg, activebackground=accent)

    ram_slider.config(bg=bg, fg=fg)
    ram_entry.config(bg=entry_bg, fg=fg, insertbackground=fg)

    status_label.config(bg=bg, fg=fg)

    console.config(bg=console_bg, fg=fg, insertbackground=fg)
    entry.config(bg=entry_bg, fg=fg, insertbackground=fg)

    save_config({**config, "theme": THEME})


def toggle_theme():
    global THEME
    THEME = "light" if THEME == "dark" else "dark"
    apply_theme()
    theme_button.config(text="Change Theme")


def toggle_fullscreen():
    root.attributes("-fullscreen", not root.attributes("-fullscreen"))


# ---------------- RAM SYNC (FINAL FIX) ----------------
def sync_ram_entry(val):
    val = int(float(val))
    ram_entry.delete(0, tk.END)
    ram_entry.insert(0, str(val))

def sync_ram_slider(event=None):
    try:
        val = int(ram_entry.get().strip())
        ram_slider.set(val)
    except:
        pass


# ---------------- STATUS ----------------
def update_status():
    status_label.config(text="🟢 Running" if is_server_running() else "🔴 Stopped")
    root.after(1000, update_status)


# ---------------- UI ----------------
root = tk.Tk()
root.protocol("WM_DELETE_WINDOW", on_close)
root.title("Server Panel")
root.geometry("720x650")

search_var = tk.StringVar()
search_var.trace("w", on_search)

search_entry = tk.Entry(root, textvariable=search_var, fg="gray")
search_entry.pack(fill="x")
search_entry.insert(0, "Search servers...")

search_entry.bind("<FocusIn>", on_search_focus_in)
search_entry.bind("<FocusOut>", on_search_focus_out)


listbox = tk.Listbox(root, height=10)
listbox.pack(fill="x", pady=5)
listbox.bind("<Button-1>", on_listbox_click)
listbox.bind("<<ListboxSelect>>", on_server_select)


btn_frame = tk.Frame(root)
btn_frame.pack()

tk.Button(btn_frame, text="Launch", command=launch).pack(side="left")
tk.Button(btn_frame, text="Refresh", command=load_servers).pack(side="left")
tk.Button(btn_frame, text="Fullscreen", command=toggle_fullscreen).pack(side="left")
tk.Button(btn_frame, text="Open Main Folder", command=lambda: os.startfile(SERVERS_DIR)).pack(side="left")
tk.Button(btn_frame, text="Open Server Logs Folder", command=open_logs_folder).pack(side="left")
tk.Button(btn_frame, text="Open Selected Servers Folder", command=open_server_directory).pack(side="left")
theme_button = tk.Button(btn_frame, text="Change Theme", command=toggle_theme)
theme_button.pack(side="left")


tk.Label(root, text="RAM (MB)").pack(anchor="w", padx=5)

ram_slider = tk.Scale(root, from_=512, to=32768, orient="horizontal", command=sync_ram_entry)
ram_slider.set(2048)
ram_slider.pack(fill="x")

ram_entry = tk.Entry(root)
ram_entry.insert(0, "2048")
ram_entry.pack(fill="x", padx=5)

ram_entry.bind("<KeyRelease>", sync_ram_slider)


cmd_frame = tk.Frame(root)
cmd_frame.pack(pady=5)

tk.Button(cmd_frame, text="Say Hi",
          command=lambda: (log_button("say Hello"), send_to_server("say Hello"))
).pack(side="left")

tk.Button(cmd_frame, text="List",
          command=lambda: (log_button("list"), send_to_server("list"))
).pack(side="left")

tk.Button(cmd_frame, text="Save",
          command=lambda: (log_button("save-all"), send_to_server("save-all"))
).pack(side="left")

tk.Button(cmd_frame, text="Stop",
          command=lambda: (log_button("stop"), stop_server())
).pack(side="left")


status_label = tk.Label(root, text="🔴 Stopped")
status_label.pack()


console = tk.Text(root, height=18)
console.pack(fill="both", expand=True)

console.tag_config("error", foreground="#ff6b6b")
console.tag_config("info", foreground="#9ad1ff")
console.tag_config("input", foreground="#90ee90")
console.tag_config("normal", foreground="#cfcfcf")


input_var = tk.StringVar()

entry = tk.Entry(root, textvariable=input_var)
entry.pack(fill="x")

entry.bind("<Return>", send_command)
entry.bind("<Up>", history_up)
entry.bind("<Down>", history_down)
entry.focus()


load_servers()

if "last_server" in config:
    try:
        idx = directories.index(config["last_server"])
        listbox.select_set(idx)
    except:
        pass


apply_theme()
update_status()

root.mainloop()