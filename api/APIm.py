from flask import Flask, jsonify
import time

app = Flask(__name__)

@app.route("/")
def home():
    return "Pi Flask Server Running 🚀"

@app.route("/data")
def data():
    return jsonify({
        "time": time.time(),
        "value": "hello from pi"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
