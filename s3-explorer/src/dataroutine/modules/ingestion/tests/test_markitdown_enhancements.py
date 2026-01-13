import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import io

from dataroutine.modules.ingestion.core.readers.markitdown_reader import MarkitdownReader
from dataroutine.modules.ingestion.core.readers.extractor.audio_converter import AudioLLMConverter
from markitdown import StreamInfo

class TestMarkitdownEnhancements(unittest.TestCase):
    def setUp(self):
        self.reader = MarkitdownReader()

    def test_markitdown_reader_can_read_always_true(self):
        # Test that can_read always returns True regardless of extension
        self.assertTrue(self.reader.can_read(Path("test.pdf")))
        self.assertTrue(self.reader.can_read(Path("test.png")))
        self.assertTrue(self.reader.can_read(Path("test.mp3")))
        self.assertTrue(self.reader.can_read(Path("test.unknown")))

    def test_markitdown_reader_get_page_count(self):
        # PDF should call pymupdf (mocked)
        with patch("pymupdf.open") as mock_open:
            mock_doc = MagicMock()
            mock_doc.__len__.return_value = 5
            mock_open.return_value = mock_doc
            
            self.assertEqual(self.reader.get_page_count(Path("test.pdf")), 5)
            
        # Non-PDF should return 1
        self.assertEqual(self.reader.get_page_count(Path("test.png")), 1)
        self.assertEqual(self.reader.get_page_count(Path("test.mp3")), 1)

    def test_audio_llm_converter_accepts(self):
        converter = AudioLLMConverter()
        
        # Test accepted extensions
        stream_info_mp3 = StreamInfo(extension=".mp3", mimetype="audio/mpeg")
        self.assertTrue(converter.accepts(io.BytesIO(), stream_info_mp3))
        
        stream_info_wav = StreamInfo(extension=".wav", mimetype="audio/wav")
        self.assertTrue(converter.accepts(io.BytesIO(), stream_info_wav))
        
        # Test rejected extensions
        stream_info_pdf = StreamInfo(extension=".pdf", mimetype="application/pdf")
        self.assertFalse(converter.accepts(io.BytesIO(), stream_info_pdf))

    @patch("base64.b64encode")
    def test_audio_llm_converter_convert(self, mock_b64):
        converter = AudioLLMConverter()
        mock_client = MagicMock()
        mock_model = "test-model"
        mock_b64.return_value = b"base64data"
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Transcribed text"
        mock_client.chat.completions.create.return_value = mock_response
        
        file_stream = io.BytesIO(b"fake audio data")
        stream_info = StreamInfo(extension=".mp3", mimetype="audio/mpeg")
        
        result = converter.convert(
            file_stream, 
            stream_info, 
            llm_client=mock_client, 
            llm_model=mock_model
        )
        
        self.assertEqual(result.markdown, "Transcribed text")
        
        # Verify the call to LLM contains input_audio
        mock_client.chat.completions.create.assert_called_once()
        args, kwargs = mock_client.chat.completions.create.call_args
        messages = kwargs['messages']
        content = messages[0]['content']
        
        self.assertEqual(content[1]['type'], "input_audio")
        self.assertEqual(content[1]['input_audio']['data'], "base64data")
        self.assertEqual(content[1]['input_audio']['format'], "mp3")

if __name__ == "__main__":
    unittest.main()
