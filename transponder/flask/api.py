from flask import Flask, request, render_template
from flask_cors import CORS, cross_origin
from flask_socketio import SocketIO, emit
import json

drone_data = {}

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*')

@socketio.on('connect')
def connect():
    print('Client connected')

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected')

def construct_list():
    response = []
    for key in drone_data:
        response.append(drone_data[key])
    return response

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/update', methods = ["POST"])
def update_drone():
    droneid = request.json['droneid']
    payload = request.json['data']
    drone_data[droneid] = payload
    message = {'status': 'OK', 'action': 'UPDATE', 'drones': construct_list()}
    socketio.emit('update_drone_data', json.dumps(message), broadcast=True)
    return "Drone updated."

@app.route('/create', methods = ["POST"])
def create_drone():
    droneid = request.json['droneid']
    payload = request.json['data']
    drone_data[droneid] = payload
    message = {'status': 'OK', 'action': 'CREATE', 'drones': construct_list()}
    socketio.emit('update_drone_data', json.dumps(message), broadcast=True)
    return "Drone created."

@app.route('/delete', methods = ["POST"])
def delete_drone():
    droneid = request.json['droneid']
    drone_data.pop(droneid, None)
    message = {'status': 'OK', 'action': 'DELETE', 'drones': construct_list()}
    socketio.emit('update_drone_data', json.dumps(message), broadcast=True)
    return "Drone deleted."

@app.route('/<droneid>', methods = ["GET"])
def get_drone_data(droneid):
    return drone_data[droneid]

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')
