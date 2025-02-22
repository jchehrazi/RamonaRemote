import os
import subprocess
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, emit
import ssl

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
VIDEO_PATH = os.path.join(os.getcwd(), 'waterfall-compressed.mp4')
ffmpegs = [[], []]

#ssl for the server, I'm not using it right now though since I'm just doing localhost and no need for it.
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
context.load_cert_chain('certificate.crt', keyfile='private.key')

@app.route('/<path:path>')
def send_static(path):
  return send_from_directory('public', path)

@socketio.on('connect')
def handle_connect():
  print(f"New client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
  print(f"Client disconnected: {request.sid}")
  if request.sid in ffmpegs[0]:
    index = ffmpegs[0].index(request.sid)
    ffmpeg_process = ffmpegs[1][index]
    ffmpeg_process.kill()
    ffmpegs[0].remove(request.sid)
    ffmpegs[1].remove(ffmpeg_process)
    print(ffmpegs)

@socketio.on('data-message')
def handle_data_message(message):
  print(f"Received message from client: {message}")
  if "{clientData-resolution=" in message:
    resolution = message.split("{clientData-resolution=")[1].split("}")[0]
    width = int(float(resolution))
    height = int(width * 9 / 16)
    client_resolution = f"{width}x{height}"

    ffmpeg_process = subprocess.Popen(
      ['C:\\FFmpeg\\bin\\ffmpeg.exe', '-re', '-i', VIDEO_PATH, '-f', 'webm', '-vcodec', 'libvpx-vp9',
       '-acodec', 'libvorbis', '-preset', 'ultrafast', '-deadline', 'realtime',
       '-cpu-used', '8', '-speed', '16', '-threads', '8', '-s', client_resolution, '-'],
      stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    ffmpegs[0].append(request.sid)
    ffmpegs[1].append(ffmpeg_process)
    print(ffmpegs)

    while True:
      data = ffmpeg_process.stdout.read(1024)
      if not data:
        break
      emit('video-stream', data, room=request.sid)
    ffmpeg_process.stderr.read()  # Log any errors from FFmpeg

if __name__ == '__main__':
  socketio.run(app, host='0.0.0.0', port=3000, allow_unsafe_werkzeug=True)
  #ssl_context=context
