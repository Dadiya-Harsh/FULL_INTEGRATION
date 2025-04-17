import re
from groq import Groq
import os
from nltk.sentiment import SentimentIntensityAnalyzer


client = Groq(api_key=os.environ["GROQ_API_KEY"])
sia = SentimentIntensityAnalyzer()

sentiment_thresholds = {
    "Very Positive": 0.75,  # Extremely positive sentiment
    "Positive": 0.35,       # Moderately positive sentiment
    "Slightly Positive": 0.05,  # Slightly positive sentiment
    "Neutral": -0.05,       # Neutral sentiment
    "Slightly Negative": -0.35, # Slightly negative sentiment
    "Negative": -0.75,      # Moderately negative sentiment
    "Very Negative": -1.0   # Extremely negative sentiment
}


def classify_sentiment_threshold(score):
    if score >= sentiment_thresholds["Very Positive"]:
        return "Very Happy 😃"
    elif score >= sentiment_thresholds["Positive"]:
        return "Happy 😊"
    elif score >= sentiment_thresholds["Slightly Positive"]:
        return "Slightly Happy 🙂"
    elif score >= sentiment_thresholds["Neutral"]:
        return "Neutral 😐"
    elif score >= sentiment_thresholds["Slightly Negative"]:
        return "Slightly Sad 😕"
    elif score >= sentiment_thresholds["Negative"]:
        return "Sad 🙁"
    else:
        return "Very Sad 😞"
    


def normalize_score(score):
    return (score + 1) * 50  # Converts -1 to 1 range into 0 to 100

def clean_text(text):
    # Retain punctuation and emojis
    text = re.sub(r"[^\w\s\!\?\.\,\:\;\-\(\)\[\]\{\}]", "", text)
    return text.lower()


def get_sentiment(text):
    raw_score = sia.polarity_scores(clean_text(text))["compound"]
    return normalize_score(raw_score)