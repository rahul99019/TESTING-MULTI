from flask import Flask, render_template, request, redirect, url_for, flash
import mechanize
import os
import datetime
import threading
from time import sleep

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Global variables
active_threads = {}
status_logs = {}

class FacebookAccount:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.browser = mechanize.Browser()
        self.browser.set_handle_robots(False)
        self.cookies = mechanize.CookieJar()
        self.browser.set_cookiejar(self.cookies)
        self.browser.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36')]
        self.browser.set_handle_refresh(False)
        self.logged_in = False
        self.status = "Not logged in"

    def login(self):
        try:
            url = 'https://m.facebook.com/login.php'
            self.browser.open(url)
            self.browser.select_form(nr=0)
            self.browser.form['email'] = self.username
            self.browser.form['pass'] = self.password
            r = self.browser.submit()
            
            # Check if login was successful
            if "login_attempt" not in r.geturl():
                self.logged_in = True
                self.status = "Logged in successfully"
                return True
            else:
                self.status = "Login failed - check credentials"
                return False
        except Exception as e:
            self.status = f"Login error: {str(e)}"
            return False

    def send_message(self, cid, message):
        if not self.logged_in:
            return False, "Not logged in"
        
        try:
            curl = f'https://m.facebook.com/messages/t/{cid}'
            self.browser.open(curl)
            
            try:
                self.browser.select_form(nr=1)
                self.browser.form['body'] = message
                r = self.browser.submit()
                timestamp = datetime.datetime.now().strftime("%d/%m/%Y %I:%M:%S %p")
                return True, f"{timestamp} - Message sent: {message[:30]}..."
            except Exception as e:
                return False, f"Failed to send: {str(e)}"
        except Exception as e:
            return False, f"Failed to access chat: {str(e)}"

def messaging_task(task_id, accounts, cid, messages, delay):
    global active_threads, status_logs
    
    status_logs[task_id] = []
    
    # Login all accounts first
    for account in accounts:
        if task_id not in active_threads or not active_threads[task_id]['running']:
            break
        success = account.login()
        status = f"{account.username}: {'Login successful' if success else account.status}"
        status_logs[task_id].append(status)
        sleep(2)  # Add delay between logins
    
    # Start messaging
    message_index = 0
    while task_id in active_threads and active_threads[task_id]['running'] and message_index < len(messages):
        current_message = messages[message_index].strip()
        if not current_message:
            message_index += 1
            continue
            
        for account in accounts:
            if task_id not in active_threads or not active_threads[task_id]['running']:
                break
                
            if account.logged_in:
                success, result = account.send_message(cid, current_message)
                status = f"{account.username}: {result}"
                status_logs[task_id].append(status)
                sleep(1)  # Small delay between account messages
            
        message_index += 1
        if task_id in active_threads and active_threads[task_id]['running'] and message_index < len(messages):
            sleep(delay)  # Delay between message sets
    
    if task_id in active_threads:
        active_threads[task_id]['running'] = False
        status_logs[task_id].append("Task completed")

@app.route('/', methods=['GET', 'POST'])
def index():
    global active_threads
    
    if request.method == 'POST':
        if 'start' in request.form:
            # Get form data
            accounts_data = request.form['accounts_data'].strip()
            messages_data = request.form['messages_data'].strip()
            cid = request.form['cid'].strip()
            
            try:
                delay = int(request.form['delay'])
            except:
                flash('Invalid delay value')
                return redirect(request.url)
                
            if not accounts_data or not messages_data or not cid:
                flash('All fields are required')
                return redirect(request.url)
                
            # Parse accounts (format: username:password, one per line)
            accounts = []
            for line in accounts_data.split('\n'):
                line = line.strip()
                if line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        username = parts[0].strip()
                        password = parts[1].strip()
                        accounts.append(FacebookAccount(username, password))
            
            if not accounts:
                flash('No valid accounts provided')
                return redirect(request.url)
                
            # Parse messages (one per line)
            messages = [line.strip() for line in messages_data.split('\n') if line.strip()]
            
            if not messages:
                flash('No messages provided')
                return redirect(request.url)
                
            # Start thread
            task_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            active_threads[task_id] = {
                'running': True,
                'thread': threading.Thread(
                    target=messaging_task,
                    args=(task_id, accounts, cid, messages, delay)
                )
            }
            active_threads[task_id]['thread'].start()
            
            flash('Task started successfully')
            return redirect(url_for('task_status', task_id=task_id))
    
    return render_template('index.html')

@app.route('/stop_task/<task_id>')
def stop_task(task_id):
    global active_threads
    if task_id in active_threads:
        active_threads[task_id]['running'] = False
        flash('Task stopped successfully')
    else:
        flash('Task not found')
    return redirect(url_for('index'))

@app.route('/task_status/<task_id>')
def task_status(task_id):
    global status_logs
    logs = status_logs.get(task_id, [])
    is_running = active_threads.get(task_id, {}).get('running', False)
    return render_template('task_status.html', task_id=task_id, logs=logs, is_running=is_running)

@app.route('/get_logs/<task_id>')
def get_logs(task_id):
    global status_logs
    logs = status_logs.get(task_id, [])
    return {'logs': logs}

if __name__ == '__main__':
    app.run(debug=True)
