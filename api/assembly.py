import streamlit as st
import websockets
import asyncio
import base64
import json
from configure import ai_auth_key, keyphrase
import assistant

import pyaudio



if 'text' not in st.session_state or 'run' not in st.session_state:
    st.session_state['text'] = 'Listening...'
    st.session_state['run'] = False
    print("adding session state keys")

FRAMES_PER_BUFFER = 3200
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
p = pyaudio.PyAudio()

# starts recording
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=FRAMES_PER_BUFFER
)


def start_listening():
    st.session_state['run'] = True


def stop_listening():
    st.session_state['run'] = False


st.title('Get real-time transcription')

start, stop = st.columns(2)
start.button('Start listening', on_click=start_listening)

stop.button('Stop listening', on_click=stop_listening)


# assembly AI / assistant variables
URL = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"
transcript = "" # complete transcript
index = 0 # index updated after assistant called (to prevent repeated calls)



async def send_receive():
    print(f'Connecting websocket to url ${URL}')

    async with websockets.connect(
            URL,
            extra_headers=(("Authorization", ai_auth_key),),
            ping_interval=5,
            ping_timeout=20
    ) as _ws:

        r = await asyncio.sleep(0.1)
        print("Receiving SessionBegins ...")

        session_begins = await _ws.recv()
        print(session_begins)
        print("Sending messages ...")

        async def send():
            while st.session_state['run']:
                try:
                    data = stream.read(FRAMES_PER_BUFFER)
                    data = base64.b64encode(data).decode("utf-8")
                    json_data = json.dumps({"audio_data": str(data)})
                    r = await _ws.send(json_data)

                except websockets.exceptions.ConnectionClosedError as e:
                    print(e)
                    assert e.code == 4008
                    break

                except Exception as e:
                    print(e)
                    assert False, "Not a websocket 4008 error"

                r = await asyncio.sleep(0.01)

        async def receive():
            global index
            while st.session_state['run']:
                try:
                    result_str = await _ws.recv()
                    result = json.loads(result_str)['text']

                    # FinalTranscript means it'll only update at the end of each sentence, not every single word
                    if json.loads(result_str)['message_type'] == 'FinalTranscript':
                        print(result)
                        ####
                        st.session_state['text'] = result # comment these out -- ST will be obselete once deployed on webapp
                        st.markdown(st.session_state['text'])
                        ####
                        latest_index = result.rfind(keyphrase) # latest occurence of keyphrase
                        if latest_index > index:
                            index = latest_index
                            success = assistant.execute(result[index:])
                        transcript = result


                except websockets.exceptions.ConnectionClosedError as e:
                    print(e)
                    assert e.code == 4008
                    break

                except Exception as e:
                    print(e)
                    assert False, "Not a websocket 4008 error"

        send_result, receive_result = await asyncio.gather(send(), receive())


asyncio.run(send_receive())