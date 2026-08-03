import re

closing_pattern = r'\b(bye|goodbye|good bye|alvida|end call|end the call|hang up|disconnect|call cut|call end|phone rakh|band kar|bas itna hi|that is all|thats all)\b'

tests = {
    "Thank you, can you also tell me about the pricing?": False,
    "Theek hai, aur mujhe project ke baare mein batao.": False,
    "Okay, what are the available options?": False,
    "Thanks. I have another question.": False,
    "Achha theek hai, price kya hai?": False,
    "Got it, can you explain that again?": False,
    "Okay thanks.": False,
    "Theek hai.": False,
    "Thank you.": False,
    "Bye.": True,
    "Goodbye.": True,
    "Please end the call.": True,
    "You can hang up now.": True,
    "That's all, bye.": True,
    "I don't have any more questions, goodbye.": True,
    "Bas itna hi tha, bye.": True,
    "Call end kar do.": True,
    "Ab call band kar do.": True,
    "Okay, that's everything. Goodbye.": True,
}

for text, expected in tests.items():
    clean_text = re.sub(r'[^\w\s]', '', text.strip().lower())
    match = bool(len(clean_text.split()) <= 8 and re.search(closing_pattern, clean_text))
    if match != expected:
        print(f"FAILED: '{text}' -> Got {match}, Expected {expected}")
print("Done")
