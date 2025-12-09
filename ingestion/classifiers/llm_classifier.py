"""Unified LLM classifier supporting multiple providers."""

import logging
import json
from typing import List, Dict, Any, Optional
from .base import Classifier
from ..core.models import Catalog, ClassificationResult

logger = logging.getLogger(__name__)


class LLMClassifier(Classifier):
    """Unified LLM classifier with pluggable provider backends.
    
    Supports multiple LLM providers through a single interface:
    - OpenAI (GPT-4, GPT-3.5-turbo)
    - Anthropic (Claude 3)
    - Ollama (Local models)
    - Azure OpenAI
    - Any OpenAI-compatible API
    """

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """Initialize LLM classifier.
        
        Args:
            provider: LLM provider (openai, anthropic, ollama, azure)
            model: Model to use (defaults based on provider)
            api_key: API key (required for openai, anthropic, azure)
            base_url: Custom base URL (for ollama or custom endpoints)
            **kwargs: Additional provider-specific arguments
        """
        self.provider = provider.lower()
        self.api_key = api_key
        self.base_url = base_url
        self.kwargs = kwargs
        
        # Set default models
        if model is None:
            model = self._get_default_model()
        self.model = model
        
        # Initialize provider
        self.client = None
        self.available = self._initialize_provider()

    def _get_default_model(self) -> str:
        """Get default model for the provider."""
        defaults = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-sonnet-20241022",
            "ollama": "llama3.1",
            "azure": "gpt-4o-mini"
        }
        return defaults.get(self.provider, "gpt-4o-mini")

    def _initialize_provider(self) -> bool:
        """Initialize the LLM provider client."""
        try:
            if self.provider == "openai":
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                logger.info(f"Initialized OpenAI client with model: {self.model}")
                return True
                
            elif self.provider == "anthropic":
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
                logger.info(f"Initialized Anthropic client with model: {self.model}")
                return True
                
            elif self.provider == "ollama":
                import requests
                base_url = self.base_url or "http://localhost:11434"
                # Check if Ollama is available
                try:
                    response = requests.get(f"{base_url}/api/tags", timeout=2)
                    if response.status_code == 200:
                        self.client = {"base_url": base_url}
                        logger.info(f"Initialized Ollama client with model: {self.model}")
                        return True
                except Exception as e:
                    logger.warning(f"Ollama not available: {str(e)}")
                    return False
                    
            elif self.provider == "azure":
                from openai import AzureOpenAI
                self.client = AzureOpenAI(
                    api_key=self.api_key,
                    api_version=self.kwargs.get("api_version", "2024-02-15-preview"),
                    azure_endpoint=self.base_url
                )
                logger.info(f"Initialized Azure OpenAI client with model: {self.model}")
                return True
                
            else:
                logger.error(f"Unsupported provider: {self.provider}")
                return False
                
        except ImportError as e:
            logger.error(f"Missing required package for {self.provider}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error initializing {self.provider}: {str(e)}")
            return False

    def classify(
        self,
        text: str,
        catalogs: List[Catalog]
    ) -> ClassificationResult:
        """Classify document text against available catalogs.
        
        Args:
            text: Document text to classify
            catalogs: List of available catalogs
            
        Returns:
            ClassificationResult with best matching catalog ID and confidence
        """
        if not self.available:
            return ClassificationResult(
                catalog_id="unknown",
                confidence=0.0,
                reasoning=f"{self.provider} not available"
            )
        
        try:
            prompt = self.build_classification_prompt(text, catalogs)
            response_text = self._generate(prompt, temperature=0.3, max_tokens=1024)
            
            # Parse JSON response
            result_json = self._extract_json(response_text)
            
            catalog_id = result_json.get("catalog_id", "unknown")
            confidence = float(result_json.get("confidence", 0.0))
            reasoning = result_json.get("reasoning", "")
            
            logger.info(f"Classified as '{catalog_id}' with confidence {confidence:.2f}")
            return ClassificationResult(
                catalog_id=catalog_id,
                confidence=confidence,
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"Error during classification: {str(e)}")
            return ClassificationResult(
                catalog_id="unknown",
                confidence=0.0,
                reasoning=f"Error: {str(e)}"
            )

    def extract_metadata(
        self,
        text: str,
        catalog: Catalog
    ) -> Dict[str, Any]:
        """Extract metadata fields defined in catalog.metadata_scan.
        
        Args:
            text: Document text to extract from
            catalog: Catalog defining metadata schema
            
        Returns:
            Dictionary with field names and extracted values
        """
        if not self.available:
            return {}
        
        try:
            prompt = self.build_metadata_prompt(text, catalog)
            response_text = self._generate(prompt, temperature=0.1, max_tokens=2048)
            
            # Parse JSON response
            metadata = self._extract_json(response_text)
            
            logger.info(f"Extracted {len(metadata)} metadata fields")
            return metadata
            
        except Exception as e:
            logger.error(f"Error during metadata extraction: {str(e)}")
            return {}

    def _generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1024
    ) -> str:
        """Generate response from LLM.
        
        Args:
            prompt: Prompt to send
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        if self.provider == "openai" or self.provider == "azure":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a document classification expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
            
        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt + "\n\nRespond ONLY with valid JSON, no other text."}
                ]
            )
            return response.content[0].text
            
        elif self.provider == "ollama":
            import requests
            response = requests.post(
                f"{self.client['base_url']}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
            
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from response text.
        
        Args:
            text: Response text that may contain JSON
            
        Returns:
            Parsed JSON dictionary
        """
        # Try direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in text
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx]
            return json.loads(json_str)
        
        raise ValueError("No valid JSON found in response")

