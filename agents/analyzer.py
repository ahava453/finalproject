import torch
# If using transformers (pip install transformers)
from transformers import pipeline
from typing import Dict, Any
import emoji

class SentimentAnalyzerAgent:
    def __init__(self):
        # 1. Detect if a GPU is available to speed up PyTorch inference
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading model on device: {self.device}")
        
        # 2. Load a PyTorch-backed sentiment analysis model
        self.sentiment_model = pipeline(
            "sentiment-analysis", 
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=0 if self.device == "cuda" else -1
        )

    def preprocess_text(self, text: str) -> str:
        """Emoji-to-Text preprocessing to improve NLP accuracy on social media slang."""
        # Convert emojis to their text representation, e.g., 🔥 -> :fire:
        text = emoji.demojize(text, delimiters=(" ", " "))
        # Replace underscores with spaces for the model
        text = text.replace("_", " ")
        # Basic cleanup
        return " ".join(text.split())

    def analyze_text(self, raw_text: str) -> Dict[str, Any]:
        text = self.preprocess_text(raw_text)
        # Run the text through the PyTorch model
        # pipeline returns a list of dicts, so we take the first element.
        result: Dict[str, Any] = self.sentiment_model(text)[0] # type: ignore
        
        return {
            "label": str(result["label"]),       # e.g., 'POSITIVE' or 'NEGATIVE'
            "score": float(f"{float(result['score']):.4f}")
        }

# Example usage:
if __name__ == "__main__":
    agent = SentimentAnalyzerAgent()
    print(agent.analyze_text("PyTorch integrations are incredibly powerful!"))
