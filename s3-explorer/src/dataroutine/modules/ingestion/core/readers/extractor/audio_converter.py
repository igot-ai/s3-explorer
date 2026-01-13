import base64
from typing import Any, BinaryIO, Union

from markitdown import DocumentConverter, DocumentConverterResult, StreamInfo

ACCEPTED_MIME_TYPE_PREFIXES = [
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
]

ACCEPTED_FILE_EXTENSIONS = [".mp3", ".wav"]


class AudioLLMConverter(DocumentConverter):
    """
    Converts audio files to markdown via a multimodal LLM using the `input_audio` format.
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()

        if extension in ACCEPTED_FILE_EXTENSIONS:
            return True

        for prefix in ACCEPTED_MIME_TYPE_PREFIXES:
            if mimetype.startswith(prefix):
                return True

        return False

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,  # Options to pass to the converter
    ) -> DocumentConverterResult:
        md_content = ""

        # Try transcribing/describing the audio with LLM
        llm_client = kwargs.get("llm_client")
        llm_model = kwargs.get("llm_model")
        if llm_client is not None and llm_model is not None:
            llm_description = self._get_llm_description(
                file_stream,
                stream_info,
                client=llm_client,
                model=llm_model,
                prompt=kwargs.get("llm_prompt"),
            )

            if llm_description is not None:
                md_content = llm_description.strip()

        return DocumentConverterResult(
            markdown=md_content,
        )

    def _get_llm_description(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        *,
        client,
        model,
        prompt=None,
    ) -> Union[None, str]:
        if prompt is None or prompt.strip() == "":
            prompt = "Please transcribe this audio and provide a summary if applicable."

        # Get the content type and extension
        extension = (stream_info.extension or "").lower()
        if extension and extension.startswith("."):
            audio_format = extension[1:] # Remove leading dot
        elif extension:
            audio_format = extension
        else:
            # Fallback to mimetype detection
            mimetype = stream_info.mimetype or ""
            if "mpeg" in mimetype or "mp3" in mimetype:
                audio_format = "mp3"
            elif "wav" in mimetype:
                audio_format = "wav"
            else:
                audio_format = "mp3" # Default

        # Convert to base64
        cur_pos = file_stream.tell()
        try:
            file_stream.seek(0)
            base64_audio = base64.b64encode(file_stream.read()).decode("utf-8")
        except Exception:
            return None
        finally:
            file_stream.seek(cur_pos)

        # Prepare the OpenAI API request with input_audio
        # Following the format: {"type": "input_audio", "input_audio": {"data": base64_audio, "format": "mp3" | "wav"}}
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64_audio,
                            "format": audio_format,
                        },
                    },
                ],
            }
        ]

        # Call the OpenAI API via the provided client
        try:
            response = client.chat.completions.create(model=model, messages=messages)
            return response.choices[0].message.content
        except Exception:
            return None # Error already handled in convert() method
