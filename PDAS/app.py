import os
import re
import time
import threading
import numpy as np
import tensorflow as tf
import sqlite3
import pickle
import random
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import base64
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_mail import Mail, Message
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

app = Flask(__name__, template_folder='templates')

# Configure Flask-Mail with Mailtrap credentials
app.config.update(
    MAIL_SERVER='sandbox.smtp.mailtrap.io',
    MAIL_PORT=2525,
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_DEFAULT_SENDER='noreply@mailtrap.io'
)

mail = Mail(app)

DATABASE = 'pdas.db'

# AES encryption key and IV (store these securely in production!)
ENCRYPTION_KEY = get_random_bytes(32)  # 256-bit key
IV = get_random_bytes(16)  # 128-bit IV

def encrypt_password(password):
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, IV)
    padded_data = pad(password.encode(), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return base64.b64encode(encrypted_data).decode('utf-8')

def decrypt_password(encrypted_password):
    try:
        cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, IV)
        encrypted_data = base64.b64decode(encrypted_password.encode('utf-8'))
        decrypted_data = cipher.decrypt(encrypted_data)
        unpadded_data = unpad(decrypted_data, AES.block_size)
        return unpadded_data.decode('utf-8')
    except Exception as e:
        print(f"Decryption error: {str(e)}")
        return None

def is_strong_password(password):
    """Enhanced password strength validation."""
    if len(password) < 12:  # Increased minimum length to 12
        return False, "Password must be at least 12 characters long"
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    
    # Check for common patterns
    if re.search(r"(.)\1{2,}", password):  # Check for repeated characters
        return False, "Password cannot contain repeated characters (3 or more times)"
    
    if re.search(r"(123|abc|qwerty|password|admin)", password.lower()):
        return False, "Password contains common patterns that are not allowed"
    
    return True, "Password meets all requirements"

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Add new columns for security questions if they don't exist
    try:
        c.execute('ALTER TABLE users ADD COLUMN question1 TEXT')
        c.execute('ALTER TABLE users ADD COLUMN question2 TEXT')
        c.execute('ALTER TABLE users ADD COLUMN answer1 TEXT')
        c.execute('ALTER TABLE users ADD COLUMN answer2 TEXT')
    except sqlite3.OperationalError:
        # Columns might already exist
        pass
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Load the LSTM model for password generation
try:
    model = tf.keras.models.load_model('password_model.h5')
    with open('char_to_int.pkl', 'rb') as f:
        char_to_int = pickle.load(f)
    with open('int_to_char.pkl', 'rb') as f:
        int_to_char = pickle.load(f)
except Exception as e:
    print(f"Error loading model or mappings: {str(e)}")
    char_to_int = {str(i): i for i in range(10)}
    int_to_char = {i: str(i) for i in range(10)}

def generate_random_seed():
    valid_chars = list(char_to_int.keys())
    return ''.join(random.choice(valid_chars) for _ in range(6))

def generate_password_with_temperature(seed, model, char_to_int, int_to_char, temperature=1.0, length=12):
    password = ''
    current_seed = seed

    for _ in range(length):
        seed_int = [char_to_int[char] for char in current_seed]
        pred = model.predict(np.array([seed_int]), verbose=0)[0]
        pred = np.asarray(pred).astype('float64')
        pred = np.log(pred + 1e-7) / temperature
        pred = np.exp(pred) / np.sum(np.exp(pred))
        next_char_index = np.random.choice(len(int_to_char), p=pred)
        next_char = int_to_char[next_char_index]
        password += next_char
        current_seed = current_seed[1:] + next_char

    return password

def store_generated_password(user_id, generated_password):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        encrypted_password = encrypt_password(generated_password)
        cursor.execute("UPDATE users SET generated_password = ? WHERE id = ?", 
                      (encrypted_password, user_id))
        conn.commit()
    except Exception as e:
        print(f"Error storing generated password: {str(e)}")

def verify_dynamic_password(password, stored_encrypted_password):
    if stored_encrypted_password:
        decrypted_password = decrypt_password(stored_encrypted_password)
        return password == decrypted_password
    return False

def periodic_password_update():
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, password_seed FROM users WHERE password_seed IS NOT NULL")
            users = cursor.fetchall()

            for user in users:
                new_dynamic_password = generate_password_with_temperature(
                    user['password_seed'], model, char_to_int, int_to_char, temperature=1.0)
                store_generated_password(user['id'], new_dynamic_password)
                
            conn.close()
        except Exception as e:
            print(f"Error in periodic password update: {str(e)}")
        time.sleep(120)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'message': 'No data provided'}), 400

            required_fields = ['first_name', 'last_name', 'username_email', 
                             'country_code', 'phone', 'password']
            if not all(field in data for field in required_fields):
                return jsonify({'message': 'Missing required fields'}), 400

            # Enhanced password validation
            is_valid, message = is_strong_password(data['password'])
            if not is_valid:
                return jsonify({'message': message}), 400

            encrypted_password = encrypt_password(data['password'])
            password_seed = generate_random_seed()
            dynamic_password = generate_password_with_temperature(
                password_seed, model, char_to_int, int_to_char, temperature=1.0)
            encrypted_dynamic_password = encrypt_password(dynamic_password)

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (
                        first_name, last_name, username_email, country_code,
                        phone, password, generated_password, password_seed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data['first_name'], data['last_name'], data['username_email'],
                    data['country_code'], data['phone'], encrypted_password,
                    encrypted_dynamic_password, password_seed
                ))
                conn.commit()
                user_id = cursor.lastrowid

                try:
                    msg = Message(
                        subject='Your Dynamic Password for PDAS',
                        recipients=[data['username_email']]
                    )
                    msg.body = f"""
                    Dear {data['first_name']} {data['last_name']},

                    Thank you for registering with PDAS.
                    Your dynamic password is: {dynamic_password}

                    Note: This password will update periodically. Please check your account for updates.

                    Regards,
                    PDAS Team
                    """
                    mail.send(msg)
                except Exception as e:
                    print(f"Error sending email: {str(e)}")

                return jsonify({
                    'message': 'Registration successful', 
                    'redirect_url': f'/security?user_id={user_id}'
                }), 201
            except sqlite3.IntegrityError:
                return jsonify({'message': 'Email already registered'}), 400
            finally:
                conn.close()
        except Exception as e:
            print(f"Registration error: {str(e)}")
            return jsonify({'message': 'An error occurred during registration'}), 500

    return render_template('register.html')

@app.route('/security', methods=['GET', 'POST'])
def security():
    if request.method == 'POST':
        try:
            data = request.get_json()
            user_id = request.args.get('user_id')

            if not data or not user_id:
                return jsonify({'message': 'No data or user ID provided'}), 400

            required_fields = ['question1', 'answer1', 'question2', 'answer2']
            if not all(field in data for field in required_fields):
                return jsonify({'message': 'Missing required fields'}), 400

            if data['question1'] == data['question2']:
                return jsonify({'message': 'Please select different security questions'}), 400

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users 
                    SET question1 = ?, answer1 = ?, question2 = ?, answer2 = ?
                    WHERE id = ?
                """, (
                    data['question1'], data['answer1'],
                    data['question2'], data['answer2'],
                    user_id
                ))
                conn.commit()
                return jsonify({
                    'message': 'Security questions set successfully',
                    'redirect_url': '/main'
                }), 201
            except Exception as e:
                print(f"Error setting security questions: {str(e)}")
                return jsonify({'message': 'Failed to set security questions'}), 500
            finally:
                conn.close()
        except Exception as e:
            print(f"Security questions error: {str(e)}")
            return jsonify({'message': 'An error occurred while setting security questions'}), 500

    return render_template('security.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json()
            username_email = data.get('username_email')
            password = data.get('password')
            dynamic_password = data.get('dynamic_password')

            if not password:
                return jsonify({'message': 'Password cannot be empty'}), 400

            if dynamic_password is not None and dynamic_password == "":
                return jsonify({'message': 'Dynamic password cannot be empty'}), 400

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""SELECT id, password, password_seed, generated_password 
                                FROM users WHERE username_email = ?""", 
                             (username_email,))
                user = cursor.fetchone()

                if not user:
                    return jsonify({'message': 'Invalid credentials'}), 401

                # Verify static password
                stored_password = decrypt_password(user['password'])
                if password != stored_password:
                    return jsonify({'message': 'Invalid credentials'}), 401

                # Verify dynamic password
                if dynamic_password:
                    if not verify_dynamic_password(dynamic_password, 
                                                 user['generated_password']):
                        return jsonify({'message': 'Invalid dynamic password'}), 401

                return jsonify({'message': 'Login successful', 
                              'user_id': user['id']}), 200
            finally:
                conn.close()
        except Exception as e:
            print(f"Login error: {str(e)}")
            return jsonify({'message': 'An error occurred during login'}), 500

    return render_template('login.html')

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data = request.get_json()
        username_email = data.get('username_email')
        question1 = data.get('question1')
        answer1 = data.get('answer1')
        question2 = data.get('question2')
        answer2 = data.get('answer2')

        if not all([username_email, question1, answer1, question2, answer2]):
            return jsonify({'message': 'All fields are required'}), 400

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT password, question1, question2, answer1, answer2, first_name, last_name
                FROM users 
                WHERE username_email = ?
            """, (username_email,))
            user = cursor.fetchone()

            if not user:
                return jsonify({'message': 'Email not found'}), 404

            if (question1 != user['question1'] or 
                question2 != user['question2'] or 
                answer1.lower() != user['answer1'].lower() or 
                answer2.lower() != user['answer2'].lower()):
                return jsonify({'message': 'Security answers do not match'}), 401

            # Decrypt the password
            decrypted_password = decrypt_password(user['password'])
            if not decrypted_password:
                return jsonify({'message': 'Error retrieving password'}), 500

            # Send email with the password
            msg = Message(
                subject='Your PDAS Password Recovery',
                recipients=[username_email]
            )
            msg.body = f"""
            Dear {user['first_name']} {user['last_name']},

            You have requested to recover your password.
            Your password is: {decrypted_password}

            Please change your password after logging in for security purposes.

            Regards,
            PDAS Team
            """
            mail.send(msg)

            return jsonify({'message': 'Password has been sent to your email'}), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"Password recovery error: {str(e)}")
        return jsonify({'message': 'An error occurred during password recovery'}), 500

@app.route('/')
def index():
    return render_template('main.html')

@app.route('/main')
def main():
    return render_template('main.html')

@app.route('/final')
def final():
    return render_template('final.html')

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
        print("Database initialized successfully!")

    threading.Thread(target=periodic_password_update, daemon=True).start()
    app.run(debug=True, port=5000)