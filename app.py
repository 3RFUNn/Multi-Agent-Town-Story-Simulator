import os
from flask import Flask, send_from_directory, render_template_string

# Initialize the Flask application
app = Flask(__name__)

# Define the directory where your HTML, CSS, and JS files will be located
# It's good practice to put them in a 'static' folder or similar
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')

# Ensure the static directory exists
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

# Route to serve the main HTML file
@app.route('/')
def index():
    # In a real application, you'd render a template.
    # For simplicity, we'll just serve the 'index.html' from the static folder.
    return send_from_directory(STATIC_FOLDER, 'index.html')

# Route to serve other static files (CSS, JS, images)
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_FOLDER, filename)

if __name__ == '__main__':
    # Run the Flask app
    # In a production environment, you would use a more robust WSGI server like Gunicorn or uWSGI.
    # For development, debug=True is useful as it provides a reloader and debugger.
    print(f"Serving files from: {STATIC_FOLDER}")
    print("Open your browser and navigate to http://127.0.0.1:5000/")
    app.run(debug=True)

