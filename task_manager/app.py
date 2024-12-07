from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

app = Flask(__name__)

# Database setup
DATABASE = 'task_manager.db'

def get_db():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Helper function to initialize the database (you should run this only once)
def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            assigned_to INTEGER,
            status TEXT,
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            sender_email TEXT,
            receiver_email TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            group_name TEXT
        )''')
    print("Database initialized!")

@app.route('/')
def home():
    """Home page."""
    return render_template("home.html")

@app.route('/dashboard')
def dashboard():
    """Dashboard page."""
    return render_template("dashboard.html")

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max file size: 16 MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part"
    file = request.files['file']
    if file.filename == '':
        return "No selected file"
    if file and allowed_file(file.filename):
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)
        return "File uploaded successfully"
    return "Invalid file type"

@app.route('/messages', methods=['GET', 'POST'])
def messages():
    """Messages page where users can chat."""
    if request.method == 'POST':
        sender_email = request.form['sender_email']
        receiver_email = request.form['receiver_email']
        message = request.form['message']
        group_name = request.form.get('group_name', None)

        # Insert the message into the database
        with get_db() as conn:
            conn.execute('''INSERT INTO messages (sender_email, receiver_email, message, group_name) 
                             VALUES (?, ?, ?, ?)''', (sender_email, receiver_email, message, group_name))

        return redirect(url_for('messages'))

    # Fetch users for private chat
    with get_db() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()
    
    # Fetch available group chats
    with get_db() as conn:
        groups = conn.execute("SELECT DISTINCT group_name FROM messages WHERE group_name IS NOT NULL").fetchall()

    # Fetch all messages to display
    with get_db() as conn:
        messages = conn.execute("SELECT * FROM messages ORDER BY timestamp DESC").fetchall()
    
    return render_template("messages.html", users=users, groups=groups, messages=messages)

@app.route('/collaboration')
def collaboration():
    """Collaboration page."""
    with get_db() as conn:
        tasks = conn.execute("SELECT * FROM tasks").fetchall()
    return render_template("collaboration.html", tasks=tasks)

@app.route('/teams')
def teams():
    """Teams page."""
    return render_template("teams.html")

@app.route('/find_peer')
def find_peer():
    """Find Peer page."""
    return render_template("find_peer.html")

@app.route('/help')
def help_page():
    """Help page."""
    return render_template("help.html")
@app.route('/users', methods=['GET', 'POST'])
def manage_users():
    """Manage users."""
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']

        # Insert new user into the database
        with get_db() as conn:
            conn.execute('''INSERT INTO users (name, email) VALUES (?, ?)''', (name, email))
        return redirect(url_for('manage_users'))

    # Fetch existing users to display
    with get_db() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()
    return render_template("users.html", users=users)

@app.route('/add_group', methods=['POST'])
def add_group():
    """Create a new group."""
    group_name = request.form['group_name']

    # Insert the new group into the database
    with get_db() as conn:
        conn.execute('''INSERT INTO messages (group_name) VALUES (?)''', (group_name,))

    # Redirect back to the page where the action was initiated
    return redirect(request.referrer or url_for('messages'))

@app.route('/add_task', methods=['POST'])
def add_task():
    """Add a new task."""
    title = request.form['title']
    description = request.form['description']
    assigned_to = request.form.get('assigned_to')
    assigned_to = int(assigned_to) if assigned_to else None

    with get_db() as conn:
        conn.execute('''INSERT INTO tasks (title, description, assigned_to, status) 
                         VALUES (?, ?, ?, ?)''', (title, description, assigned_to, "Pending"))
    
    return redirect(url_for('collaboration'))

@app.route('/mark_complete/<int:task_id>')
def mark_complete(task_id):
    """Mark a task as complete."""
    with get_db() as conn:
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", ("Complete", task_id))
    return redirect(url_for('collaboration'))


@app.route('/chat/<chat_type>/<chat_id>', methods=['GET', 'POST'])
def open_chat(chat_type, chat_id):
    """Open a specific chat based on chat type (private or group)"""
    if request.method == 'POST':
        # Handle form submission to send a message
        sender_email = request.form['sender_email']
        message = request.form['message']
        file = request.files.get('file', None)  # Handle file uploads

        # Insert the message into the database
        with get_db() as conn:
            conn.execute('''INSERT INTO messages (sender_email, receiver_email, message, group_name) 
                             VALUES (?, ?, ?, ?)''', 
                             (sender_email, chat_id, message, chat_type))

            # If a file is uploaded, save it (you can handle file storage here)
            if file:
                file.save(f'uploads/{file.filename}')  # Save the file in the 'uploads' folder

        return redirect(url_for('open_chat', chat_type=chat_type, chat_id=chat_id))

    # Fetch messages from the database for the chat
    with get_db() as conn:
        if chat_type == 'private':
            messages = conn.execute('''SELECT * FROM messages WHERE receiver_email = ? AND group_name IS NULL ORDER BY timestamp ASC''', (chat_id,)).fetchall()
        else:
            messages = conn.execute('''SELECT * FROM messages WHERE group_name = ? ORDER BY timestamp ASC''', (chat_id,)).fetchall()

    return render_template('chat.html', messages=messages, chat_type=chat_type, chat_id=chat_id)

def get_users():
    conn = sqlite3.connect('peer_matching.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users')
    users = c.fetchall()
    conn.close()
    return users

# Function to find the best match for the user based on answers
def find_best_match(user_answers):
    users = get_users()
    best_match = None
    best_score = -1
    
    for user in users:
        score = sum([1 for i in range(1, 6) if user[i] == user_answers[i-1]])
        if score > best_score:
            best_score = score
            best_match = user
    return best_match

# Route for the home page (user form)
@app.route('/')
def index():
    return render_template('find_peer.html')

# Route to handle form submission and find a match
@app.route('/submit', methods=['POST'])
def submit():
    user_answers = [
        request.form['q1'],
        request.form['q2'],
        request.form['q3'],
        request.form['q4'],
        request.form['q5']
    ]
    
    best_match = find_best_match(user_answers)
    
    if best_match:
        return render_template('find_peer.html', user=best_match)
    return 'No match found'

# Route to accept the match
@app.route('/accept/<user_id>')
def accept(user_id):
    return f"You have accepted the match with user {user_id}"

# Route to reject the match
@app.route('/reject/<user_id>')
def reject(user_id):
    return f"You have rejected the match with user {user_id}"
def init_db():
    conn = sqlite3.connect('peer_matching.db')
    c = conn.cursor()

    # Create users table if it doesn't exist
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT,
        q1 TEXT,
        q2 TEXT,
        q3 TEXT,
        q4 TEXT,
        q5 TEXT
    )
    ''')

    # Insert mock data if the table is empty
    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        users_data = [
            ("Alice", "A", "B", "C", "D", "E"),
            ("Bob", "B", "A", "C", "E", "D"),
            ("Charlie", "C", "D", "B", "A", "E"),
            ("David", "D", "E", "A", "B", "C"),
            ("Eve", "E", "C", "D", "B", "A")
        ]
        c.executemany('''
        INSERT INTO users (name, q1, q2, q3, q4, q5)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', users_data)
        conn.commit()

    conn.close()

# Initialize the database with mock data
init_db()

# Function to get all users from the database
def get_users():
    conn = sqlite3.connect('peer_matching.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users')
    users = c.fetchall()
    conn.close()
    return users


if __name__ == "__main__":
    init_db()  # Initialize the database
    app.run(debug=True, port=8080)

