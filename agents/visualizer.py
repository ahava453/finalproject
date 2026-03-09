import logging
import random
from collections import Counter
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class VisualizerAgent:
    """
    Agent responsible for aggregating processed data into chart-ready formats for the frontend.
    """
    def __init__(self):
        pass

    def generate_dashboard_data(self, processed_comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Takes a list of processed comments and generates aggregations for the frontend UI.
        """
        logger.info(f"VisualizerAgent: Aggregating data from {len(processed_comments)} comments")
        
        if not processed_comments:
            return self._empty_dashboard()
            
        # 1. Sentiment Distribution
        sentiment_counts = Counter([c["sentiment_label"] for c in processed_comments])
        
        # 2. Platform Distribution
        platform_counts = Counter([c["platform"] for c in processed_comments])
        
        # 3. Top Keywords
        all_keywords = []
        for c in processed_comments:
            all_keywords.extend(c["keywords"])
        top_keywords = Counter(all_keywords).most_common(10)
        
        # 4. Average Sentiment Over Time (Mocked timeseries distribution for now)
        # In a real app we parse datetime and group by hour/day
        time_series = [
            {"date": "Day 1", "positive": random.randint(10, 50), "negative": random.randint(5, 20)},
            {"date": "Day 2", "positive": random.randint(15, 60), "negative": random.randint(10, 30)},
            {"date": "Day 3", "positive": random.randint(20, 70), "negative": random.randint(5, 15)},
            {"date": "Day 4", "positive": random.randint(30, 80), "negative": random.randint(15, 35)},
            {"date": "Day 5", "positive": random.randint(40, 90), "negative": random.randint(10, 25)},
        ]
        
        return {
            "summary": {
                "total_comments": len(processed_comments),
                "avg_sentiment": sum(c["sentiment_score"] for c in processed_comments) / len(processed_comments)
            },
            "charts": {
                "sentiment_pie": [
                    {"name": "Positive", "value": sentiment_counts.get("positive", 0)},
                    {"name": "Neutral", "value": sentiment_counts.get("neutral", 0)},
                    {"name": "Negative", "value": sentiment_counts.get("negative", 0)}
                ],
                "platform_bar": [{"name": k, "value": v} for k, v in platform_counts.items()],
                "keyword_cloud": [{"text": k, "value": v} for k, v in top_keywords],
                "sentiment_timeline": time_series
            },
            "raw_samples": [processed_comments[i] for i in range(min(100, len(processed_comments)))] # Return top 100 for feed view
        }
        
    def _empty_dashboard(self) -> Dict[str, Any]:
        return {
            "summary": {"total_comments": 0, "avg_sentiment": 0.5},
            "charts": {
                "sentiment_pie": [],
                "platform_bar": [],
                "keyword_cloud": [],
                "sentiment_timeline": []
            },
            "raw_samples": []
        }

