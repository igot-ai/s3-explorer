"""Classifiers for document classification using LLM."""

from src.modules.ingestion.core.classifiers.base import Classifier
from src.modules.ingestion.core.classifiers.llm_classifier import LLMClassifier

__all__ = ["Classifier", "LLMClassifier"]
