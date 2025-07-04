import sqlite3
from database import init_db, add_user, verify_code, is_verified
import smtplib
import random
import flask
from flask_cors import CORS
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from torchvision import models
import numpy as np
from PIL import Image
import io
import os
import requests

app = flask.Flask(__name__)
init_db()
CORS(app, resources={r"/*": {"origins": "*"}})
password_reset_codes = {}

# Define your DenseNet model
class DenseNetModel(nn.Module):
    def __init__(self, num_classes=10):
        super(DenseNetModel, self).__init__()
        self.model = models.densenet161(weights=models.DenseNet161_Weights.IMAGENET1K_V1)
        num_features = self.model.classifier.in_features
        self.model.classifier = nn.Sequential(
            nn.Linear(num_features, 1024),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(1024, 512),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(512, num_classes)
        )

    def forward(self, x):
        return self.model(x)

# Device setup
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Global model variable
model = None

def download_model_from_s3():
    url = "https://hmodel.s3.eu-north-1.amazonaws.com/model2.pth"
    response = requests.get(url)
    local_path = "model2.pth"

    if os.path.exists(local_path):
        print("🗑️ Removing old model file...")
        os.remove(local_path)

    print("🔻 Downloading model from S3...")
    try:
        response = requests.get(url)
        with open(local_path, 'wb') as f:
            f.write(response.content)
        print("✅ Model downloaded from S3.")
    except Exception as e:
        print(f"❌ Failed to download model: {e}")

def load_model():
    global model
    model_path = 'model2.pth'
    try:
        if not os.path.exists(model_path):
            download_model_from_s3()

        model = DenseNetModel(num_classes=10)
        checkpoint = torch.load(model_path, map_location=device)
        model.load_state_dict(checkpoint)
        model.to(device)
        model.eval()
        print("✅ Model loaded successfully!")
        return True
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return False

# Start logging
print("🚀 Starting PyTorch Flask server...")
print(f"📍 Working directory: {os.getcwd()}")
print(f"🐍 PyTorch version: {torch.__version__}")

if load_model():
    print("✅ Server ready!")
else:
    print("⚠️ Server starting without model")

# Class labels
class_names = [
    'Eczema', 'Warts Molluscum', 'Melanoma', 'Atopic Dermatitis',
    'Basal Cell Carcinoma', 'Melanocytic Nevi',
    'Benign Keratosis', 'Psoriasis', 'Seborrheic Keratoses',
    'Tinea Ringworm'
]

# Image preprocessing
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.5]*3, [0.5]*3)
])

def send_verification_email(email):
    code = str(random.randint(100000, 999999))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("rrimawi123@gmail.com", "hcwkzyzfqrnyhtov")
        message = f"Subject: Your Verification Code\n\nYour code is: {code}"
        server.sendmail("rrimawi123@gmail.com", email, message)
        server.quit()
        return code
    except Exception as e:
        print(f"Error sending email: {e}")
        return None

@app.route('/register', methods=['POST'])
def register_user():
    data = flask.request.get_json()
    name = data['name']
    email = data['email']
    password = data['password']

    code = send_verification_email(email)
    if code is None:
        return flask.jsonify({'error': 'Failed to send email'}), 500

    if not add_user(name, email, password, code):
        return flask.jsonify({'error': 'User already exists'}), 400

    return flask.jsonify({'message': 'Verification code sent', 'email': email})

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = flask.request.get_json()
    email = data.get('email')

    code = str(random.randint(100000, 999999))
    password_reset_codes[email] = code

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("rrimawi123@gmail.com", "hcwkzyzfqrnyhtov")
        message = f"Subject: Password Reset Code\n\nYour reset code is: {code}"
        server.sendmail("rrimawi123@gmail.com", email, message)
        server.quit()
        return flask.jsonify({'message': 'Reset code sent successfully'})
    except Exception as e:
        print(f"Error sending email: {e}")
        return flask.jsonify({'error': 'Failed to send reset code'}), 500

@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = flask.request.get_json()
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('newPassword')

    if email in password_reset_codes and password_reset_codes[email] == code:
        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("UPDATE users SET password=? WHERE email=?", (new_password, email))
            conn.commit()
            conn.close()
            print("✅ Password updated for:", email)
        except Exception as e:
            print("❌ Error updating DB:", e)
            return flask.jsonify({'error': 'Database error'}), 500

        del password_reset_codes[email]
        return flask.jsonify({'message': 'Password updated successfully'})
    else:
        return flask.jsonify({'error': 'Invalid code'}), 400

@app.route('/verify-code', methods=['POST'])
def verify_user_code():
    data = flask.request.get_json()
    email = data['email']
    code = data['code']
    if verify_code(email, code):
        return flask.jsonify({'status': 'verified'})
    return flask.jsonify({'error': 'Invalid code'}), 400

@app.route('/predict', methods=['POST'])
def predict():
    print("Received request at /predict")
    global model
    if model is None:
        print("Model not loaded. Attempting to load now...")
        if not load_model():
            return flask.jsonify({'error': 'Model not loaded. Check logs.'}), 500

    try:
        if 'image' not in flask.request.files:
            return flask.jsonify({'error': 'No image file provided'}), 400

        file = flask.request.files['image']
        if file.filename == '':
            return flask.jsonify({'error': 'No file selected'}), 400

        file_bytes = file.read()
        image = Image.open(io.BytesIO(file_bytes)).convert('RGB')
        image_tensor = transform(image).unsqueeze(0).to(device)

        with torch.no_grad():
            outputs = model(image_tensor)
            probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
            predicted_class = torch.argmax(outputs, 1).item()
            confidence = float(probabilities[predicted_class]) * 100

        return flask.jsonify({
            'disease': class_names[predicted_class],
            'confidence': round(confidence, 2),
            'recommendations': 'Please consult with a dermatologist for proper diagnosis.'
        })

    except Exception as e:
        return flask.jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return flask.jsonify({
        'status': 'running',
        'model_type': 'PyTorch',
        'device': str(device),
        'model_loaded': model is not None,
        'working_directory': os.getcwd()
    })

@app.route('/', methods=['GET'])
def home():
    return flask.jsonify({
        'message': 'Skin Disease Detection API',
        'endpoints': {
            'health': '/health',
            'predict': '/predict (POST with image file)'
        }
    })

@app.route('/login', methods=['POST'])
def login_user():
    data = flask.request.get_json()
    email = data['email']
    password = data['password']

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, name, verified FROM users WHERE email=? AND password=?", (email, password))
    row = c.fetchone()
    conn.close()

    if row:
        if row[2] == 0:
            return flask.jsonify({'error': 'Account not verified'}), 403
        return flask.jsonify({'id': row[0], 'name': row[1], 'email': email})
    else:
        return flask.jsonify({'error': 'Invalid credentials'}), 401

if __name__ == '__main__':
    if load_model():
        print("✅ Server ready!")
    else:
        print("⚠️ Server starting without model")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
