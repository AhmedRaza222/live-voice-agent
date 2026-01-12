
import os


from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    LLMRunFrame
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.serializers.base_serializer import FrameSerializer as BaseFrameSerializer, FrameSerializerType
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService

from fastapi import WebSocket, WebSocketDisconnect

from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
    FastAPIWebsocketClient,
    FastAPIWebsocketInputTransport,
    FastAPIWebsocketOutputTransport
)
import json
from pipecat.frames.frames import EndFrame, InputDTMFFrame
import json
from codec import ulaw2lin, lin2ulaw, resample_8k_to_16k, resample_16k_to_8k

class InfobipWebsocketClient(FastAPIWebsocketClient):
    def __init__(self, websocket: WebSocket, is_binary: bool, callbacks):
        super().__init__(websocket, is_binary, callbacks)

    async def receive(self):
        try:
            while True:
                message = await self._websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if "text" in message:
                    yield message["text"]
                elif "bytes" in message:
                    yield message["bytes"]
        except WebSocketDisconnect:
            pass


class InfobipWebsocketTransport(FastAPIWebsocketTransport):
    def __init__(self, websocket: WebSocket, params: FastAPIWebsocketParams):
        super().__init__(websocket, params)
        # Override client and input/output transports to use mixed-mode client
        self._client = InfobipWebsocketClient(
            websocket, 
            params.serializer.type == FrameSerializerType.BINARY, 
            self._callbacks
        )
        self._output = FastAPIWebsocketOutputTransport(self, self._client, params)
        self._input = FastAPIWebsocketInputTransport(self, self._client, params)


class InfobipFrameSerializer(BaseFrameSerializer):
    def __init__(self):
        pass

    @property
    def type(self) -> FrameSerializerType:
        return FrameSerializerType.BINARY

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, OutputAudioRawFrame):
            # Transcode PCM 16kHz -> G.711 u-law 8kHz
            try:
                # 1. Resample 16000 -> 8000
                audio_8k = resample_16k_to_8k(frame.audio)
                # 2. Linear PCM -> u-law
                ulaw_data = lin2ulaw(audio_8k)
                return ulaw_data
            except Exception as e:
                logger.error(f"Error during audio serialization/transcoding: {e}")
                return None
                
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            # Transcode G.711 u-law 8kHz -> PCM 16kHz
            try:
                # 1. u-law -> Linear PCM
                pcm_8k = ulaw2lin(data)
                # 2. Resample 8000 -> 16000
                audio_16k = resample_8k_to_16k(pcm_8k)
                return InputAudioRawFrame(audio=audio_16k, num_channels=1, sample_rate=16000)
            except Exception as e:
                logger.error(f"Error during audio deserialization/transcoding: {e}")
                return None
                
        if isinstance(data, str):
            logger.debug(f"Received JSON message from Infobip: {data}")
            try:
                payload = json.loads(data)
                
                # Handle DTMF
                if payload.get("event") == "dtmf":
                    digit = payload.get("digit") or payload.get("digits") or payload.get("dtmf")
                    if digit:
                        logger.info(f"User pressed DTMF: {digit}")
                        return InputDTMFFrame(digits=digit)

                # Handle Infobip specific events
                if payload.get("event") in ["callEnded", "disconnected", "hangup"]:
                    logger.info("Call ended by provider, closing pipeline.")
                    return EndFrame()
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from Infobip: {data}")
        return None


async def run_infobip_bot(websocket_client):
    try:
        transport = InfobipWebsocketTransport(
            websocket=websocket_client,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                vad_analyzer=SileroVADAnalyzer(),
                serializer=InfobipFrameSerializer(),
                audio_in_sample_rate=16000,
                audio_out_sample_rate=16000,
            ),
        )

        llm = GeminiLiveLLMService(
            api_key=os.getenv("GOOGLE_API_KEY"),
            voice_id="Puck",
            transcribe_model_audio=True,
            model="models/gemini-2.5-flash-native-audio-preview-12-2025",
        )
    except Exception as e:
        logger.exception(f"Failed to initialize services: {e}")
        await websocket_client.close()
        return

    # Improved System Prompt for Phone Interaction
    system_instruction = (
        "You are a helpful and polite AI voice assistant connected via a phone call. "
        "Your responses will be converted to speech, so avoid special characters. "
        "Speak naturally and clearly. "
        "Keep your answers concise, ideally 1-2 sentences, as this is a live conversation. "
        "Do not explicitly mention you are an AI unless asked. "
        "Pause briefly after your response to allow the user to reply."
    )

    context = LLMContext(
        [
            {
                "role": "system",
                "content": system_instruction,
            }
        ],
    )
    context_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            context_aggregator.user(),
            llm,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Infobip client connected.")
        # Start conversation immediately
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Infobip client disconnected.")
        await task.cancel()
        try:
             await websocket_client.close()
        except Exception:
             pass

    runner = PipelineRunner()
    
    try:
        await runner.run(task)
    except Exception as e:
        logger.exception(f"Pipeline execution crashed: {e}")
