import sys

from src.modules.ingestion.core.classifiers.base import Classifier
from src.modules.ingestion.core.classifiers.llm_classifier import LLMClassifier
from src.shared._logging import get_logger

logger = get_logger(__name__)


class ClassifierManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        for mod_name, module in sys.modules.items():
            if "classifier_manager" in mod_name and hasattr(module, "_shared_instance"):
                return module._shared_instance

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            global _shared_instance
            _shared_instance = cls._instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.classifier: Classifier = LLMClassifier()

        self._initialized = True

    @staticmethod
    def get_instance():
        return ClassifierManager()

    @staticmethod
    def set_classifier(classifier: Classifier):
        instance = ClassifierManager()
        instance.classifier = classifier
