import os
import subprocess
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, emit
import imageio
import imageio_ffmpeg as ioffmpeg
from engineio.payload import Payload
from time import sleep
import ssl

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
#VIDEO_PATH = os.path.join(os.getcwd(), 'waterfall-compressed.mp4')
Payload.max_decode_packets = 50
ffmpegs = [[], []]

#ssl for the server, I'm not using it right now though since I'm just doing localhost and no need for it.
#context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
#context.load_cert_chain('certificate.crt', keyfile='private.key')

@app.route('/')
def send_homepage():
  return send_from_directory('public', "index.html")

@app.route('/<path:path>')
def send_static(path):
  if not "." in path:
    return send_from_directory('public/' + str(path), "index.html")
  else:
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

    # Simulate a frame...
    frame = imageio.imread('imageio:astronaut.png')

    sizestr = f"{frame.shape[1]}x{frame.shape[0]}"
    ffmpeg_process = subprocess.Popen(
      [
          ioffmpeg.get_ffmpeg_exe(),
          '-hide_banner',
          '-loglevel', 'error',
          '-f', 'rawvideo',
          '-pix_fmt', 'rgb24',
          '-s', sizestr,
          '-r', '1',
          '-i', 'pipe:',
          '-vcodec', 'libvpx-vp9',
          '-an',
          '-preset', 'ultrafast',
          '-deadline', 'realtime',
          '-cpu-used', '8',
          '-speed', '16',
          '-threads', '8',
          '-f', 'webm',
          '-s', client_resolution, '-'
      ],
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE
    )

    ffmpegs[0].append(request.sid)
    ffmpegs[1].append(ffmpeg_process)
    print(ffmpegs)

    # Write data to the FFmpeg process
    for factor in (1., 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1):
      ffmpeg_process.stdin.write((frame * factor).astype('uint8').tobytes())
    # Now terminate the input stream
    ffmpeg_process.stdin.close()
    while True:
      # Timeout after 0.1 seconds
      data = ffmpeg_process.stdout.read(1024)
      if not data:
        break
      emit('video-stream', data, room=request.sid)
    ffmpeg_process.stderr.read()  # Log any errors from FFmpeg

if __name__ == '__main__':
  socketio.run(app, host='0.0.0.0', port=3000, allow_unsafe_werkzeug=True)
  #ssl_context=context
