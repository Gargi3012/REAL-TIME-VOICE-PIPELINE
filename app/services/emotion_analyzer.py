import re

# Hinglish, Hindi, and English keywords categorized by emotion
EMOTION_KEYWORDS = {
    "happy": [
        "great", "awesome", "hello", "good", "happy", "yes", "nice", "perfect", "thank you", "thanks", "excellent",
        "मज़ेदार", "बढ़िया", "अच्छा", "थैंक्यू", "धन्यवाद", "मजा", "खुश", "बढ़िया है", "love", "cool", "superb", "super",
        "glad", "pleased", "fantastic", "amazing"
    ],
    "angry": [
        "bad", "worst", "slow", "late", "useless", "irritated", "nonsense", "no", "stop", "waste", "angry", "hate",
        "घटिया", "खराब", "बकवास", "बंद करो", "late reply", "गुस्सा", "नहीं", "बेकार", "stupid", "annoying", "frustrated",
        "waste of time"
    ],
    "confused": [
        "why", "how", "what", "where", "confused", "cannot", "don't know", "doubt", "explain", "help", "question",
        "कहाँ", "कैसे", "क्यों", "समझ नहीं आया", "क्या", "मदद", "सवाल", "कन्फ्यूज", "बताओ", "know more", "details"
    ]
}

# Emoji map for frontend display (sent separately so the logger never touches them)
EMOTION_EMOJI = {
    "Happy": "😊",
    "Frustrated": "😠",
    "Confused": "🤔",
    "Neutral": "😐",
}

def analyze_emotion(text: str) -> str:
    """Analyze the emotion of the user utterance based on multilingual keywords.
    
    Returns one of: 'Happy', 'Frustrated', 'Confused', 'Neutral'
    (no emojis — the frontend adds them via EMOTION_EMOJI map or CSS)
    """
    if not text:
        return "Neutral"
        
    text_lower = text.lower()
    
    # Check for angry/frustrated patterns
    for word in EMOTION_KEYWORDS["angry"]:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower) or word in text_lower:
            return "Frustrated"
            
    # Check for confused patterns
    for word in EMOTION_KEYWORDS["confused"]:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower) or word in text_lower:
            return "Confused"
            
    # Check for happy/excited patterns
    for word in EMOTION_KEYWORDS["happy"]:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower) or word in text_lower:
            return "Happy"
            
    return "Neutral"
