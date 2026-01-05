#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import os

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
from pipecat.transports.websocket.server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)

# Get the directory of the current script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys_prompt_path = os.path.join(CURRENT_DIR, "system_prompt.txt")

try:
    with open(sys_prompt_path, "r") as f:
        SYSTEM_INSTRUCTION = f.read()
except FileNotFoundError:
    logger.error(f"System prompt file not found at {sys_prompt_path}")
    SYSTEM_INSTRUCTION = "You are a helpful assistant."


async def run_bot_websocket_server():
    ws_transport = WebsocketServerTransport(
        params=WebsocketServerParams(
            serializer=ProtobufFrameSerializer(),
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),
            session_timeout=60 * 3,  # 3 minutes
        )
    )

    llm = GeminiLiveLLMService(
        api_key=os.getenv("GOOGLE_API_KEY"),
        model="gemini-2.5-flash-native-audio-preview-12-2025",
        voice_id="Puck",  # Aoede, Charon, Fenrir, Kore, Puck
        transcribe_model_audio=True,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    context = LLMContext([])
    context_aggregator = LLMContextAggregatorPair(context)

    # RTVI events for Pipecat client UI
    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

    pipeline = Pipeline(
        [
            ws_transport.input(),
            context_aggregator.user(),
            rtvi,
            llm,  # LLM
            ws_transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[RTVIObserver(rtvi)],
    )

    @rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info("Pipecat client ready.")
        await rtvi.set_bot_ready()
        # Kick off the conversation.
        # await task.queue_frames([LLMRunFrame()])

    @ws_transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Pipecat Client connected")

    @ws_transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Pipecat Client disconnected")
        await task.cancel()

    @ws_transport.event_handler("on_session_timeout")
    async def on_session_timeout(transport, client):
        logger.info(f"Entering in timeout for {client.remote_address}")
        await task.cancel()

    runner = PipelineRunner()

    await runner.run(task)
