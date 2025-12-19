from src.modules.ingestion.core.classifiers.base import Classifier


class ClassifierManager:
    instance = None

    def __init__(self):
        from src.modules.ingestion.core.classifiers.llm_classifier import LLMClassifier

        self.classifier: Classifier = LLMClassifier()

    @staticmethod
    def get_instance():
        if (
            not hasattr(ClassifierManager, "instance")
            or ClassifierManager.instance is None
        ):
            ClassifierManager.instance = ClassifierManager()
        return ClassifierManager.instance

    @staticmethod
    def set_classifier(classifier: Classifier):
        """Set the global classifier for the router.

        Args:
            classifier: A classifier instance
        """
        ClassifierManager.get_instance().classifier = classifier
