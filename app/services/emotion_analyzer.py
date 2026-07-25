import re

# Hinglish, Hindi, and English keywords categorized by emotion
# We avoid very generic single words like "how", "why", "what", "no", "yes", "hello" to prevent false triggers.
EMOTION_KEYWORDS = {
    "happy": [
        # English
        "great", "awesome", "happy", "perfect", "thank you", "thanks", "excellent",
        "love", "cool", "superb", "super", "glad", "pleased", "fantastic", "amazing", 
        "wonderful", "nice", "good job", "perfectly", "satisfied", "love it", "splendid", 
        "beautiful", "delighted", "helpful", "very helpful", "awesome job",
        # Hindi & Hinglish
        "मज़ेदार", "बढ़िया", "अच्छा", "मजा", "खुश", "बढ़िया है", "shandar", "shandaar",
        "mast", "mja", "mza", "achha", "dhanyawad", "badhiya", "bahut badhiya", "gazab", 
        "maza aa gaya", "mazaa", "bahut achha", "dhanuyavad", "shukriya", "sahi hai"
    ],
    "angry": [
        # English
        "bad", "worst", "slow", "late", "useless", "irritated", "nonsense", "waste", "angry", "hate",
        "stupid", "annoying", "frustrated", "waste of time", "terrible", "horrible", 
        "disappointed", "annoyed", "impatient", "so slow", "not working", "pointless", 
        "garbage", "trash", "ridiculous", "hate it", "fed up", "sucks",
        # Hindi & Hinglish
        "घटिया", "खराब", "बकवास", "late reply", "गुस्सा", "बेकार", "bekaar", "pagal",
        "faltu", "ghatiya", "kharab", "bakwas", "gussa", "bekar", "falthu", "time waste", 
        "samay barbad", "pareshan", "dimaag kharab", "dimag kharab", "gussa aaya", "ghussa"
    ],
    "confused": [
        # English
        "confused", "cannot understand", "don't know", "dont know", "doubt", "explain", "not understanding",
        "pardon", "lost", "unsure", "not clear", "what is this", "what do you mean", "puzzled", 
        "mixed up", "no idea", "unclear", "not following", "how so", "makes no sense", "what is that", 
        "who is this", "which one", "dont understand", "do not understand", "what are you saying",
        # Hindi & Hinglish
        "समझ नहीं आया", "कन्फ्यूज", "explain kar", "samajh nahi", "samajh ni", "kya matlab", 
        "kya bol rahe ho", "kya bole", "kya hai ye", "samajh nahi aa raha", "samajh nahi ara", 
        "kuch samajh nahi", "dubaara batao", "kaise hoga", "samajh nahi aaya", "confuse"
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
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            return "Frustrated"
            
    # Check for confused patterns
    for word in EMOTION_KEYWORDS["confused"]:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            return "Confused"
            
    # Check for happy/excited patterns
    for word in EMOTION_KEYWORDS["happy"]:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            return "Happy"
            
    return "Neutral"
