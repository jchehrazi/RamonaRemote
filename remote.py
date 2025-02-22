import os
import subprocess
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, emit
import ssl
import time
import pygfx as gfx
import multiprocessing
import threading
from wgpu.gui.auto import WgpuCanvas, run
from rendercanvas.offscreen import RenderCanvas as OffscreenCanvas
#from rendercanvas.auto import RenderCanvas as OffscreenCanvas

# Initialize the PyGFX scene and offscreen renderer
canvas = OffscreenCanvas(size=(1920, 1080))
renderer = gfx.WgpuRenderer(canvas)
scene = gfx.Scene()
camera = gfx.PerspectiveCamera(70, 16/9)
latest_frame = None

# Create some objects for the scene
geometry = gfx.box_geometry(1, 1, 1)
material = gfx.MeshBasicMaterial(color=(1, 0, 0, 1))
cube = gfx.Mesh(geometry, material)
scene.add(cube)

#initialize flask
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
ffmpegs = [[], []]

#ssl for the server, I'm not using it right now though since I'm just doing localhost and no need for it.
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
context.load_cert_chain('certificate.crt', keyfile='private.key')

#route for static files
@app.route('/<path:path>')
def send_static(path):
  return send_from_directory('public', path)

#route for websocket connect
@socketio.on('connect')
def handle_connect():
  print(f"New client connected: {request.sid}")

#handle websocket disconnect
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

#handle websocket message + start ffmpeg
@socketio.on('data-message')
def handle_data_message(message):
  print(f"Received message from client: {message}")
  if "{clientData-resolution=" in message:
    resolution = message.split("{clientData-resolution=")[1].split("}")[0]
    width = int(float(resolution))
    height = int(width * 9 / 16)
    client_resolution = f"{width}x{height}"

    ffmpeg_process = subprocess.Popen(
      ['C:\\FFmpeg\\bin\\ffmpeg.exe', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-r', '30', '-i', 'pipe:1', '-f', 'webm', '-vcodec', 'libvpx-vp9',
       '-acodec', 'libvorbis', '-preset', 'ultrafast', '-deadline', 'realtime',
       '-cpu-used', '8', '-speed', '16', '-threads', '8', '-s', client_resolution, '-'],
      stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True
    )

    ffmpegs[0].append(request.sid)
    ffmpegs[1].append(ffmpeg_process)
    print(ffmpegs)

    # multiprocessing queue
    q = multiprocessing.Queue()


    def animation():
      global latest_frame
      renderer.render(scene, camera)
      latest_frame = renderer.snapshot()
      canvas.request_draw()

    def capture():
      global latest_frame
      while True:
        q.put(latest_frame)
        time.sleep(1 / 30)
        if latest_frame is not None:
          ffmpeg_process.stdin.write(latest_frame)

    t = threading.Thread(target=capture)

    canvas.request_draw(animation)
    run()
    t.start()

    while True:

      """if ffmpeg_process.poll() is None:
        renderer.render(scene, camera)
      # Capture the frame as raw RGBA data
        frame_data = canvas.draw()
        renderer.snapshot()
        print(frame_data.tobytes())
        print(memoryview(frame_data))
        print(str(frame_data))
        ffmpeg_process.stdin.write(str(frame_data.tobytes()))"""

      data = ffmpeg_process.stdout.read(1024)
      if not data:
        break
      emit('video-stream', data, room=request.sid)

    ffmpeg_process.stderr.read()  # Log any errors from FFmpeg

if __name__ == '__main__':
  socketio.run(app, host='0.0.0.0', port=3000, allow_unsafe_werkzeug=True)
  #ssl_context=context
