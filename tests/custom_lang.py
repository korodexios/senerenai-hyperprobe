"""Multilingual quality prompts for major world languages.

The benchmark intentionally includes both broad-use languages and the original
Slovak/Czech cases. Each prompt carries machine-readable language metadata so
graders and dashboards can analyze results by language.
"""

LANGUAGE_PROFILES = {
    "en": {"name": "English", "script": "latin", "diacritics": "", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
    "zh": {"name": "Mandarin Chinese", "script": "cjk", "diacritics": "", "foreign_scripts": "cyrillic arabic devanagari bengali hangul"},
    "hi": {"name": "Hindi", "script": "devanagari", "diacritics": "", "foreign_scripts": "cjk cyrillic arabic bengali hangul"},
    "es": {"name": "Spanish", "script": "latin", "diacritics": "áéíóúüñ", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
    "ar": {"name": "Arabic", "script": "arabic", "diacritics": "", "foreign_scripts": "cjk cyrillic devanagari bengali hangul"},
    "fr": {"name": "French", "script": "latin", "diacritics": "àâçéèêëîïôùûüÿœ", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
    "bn": {"name": "Bengali", "script": "bengali", "diacritics": "", "foreign_scripts": "cjk cyrillic arabic devanagari hangul"},
    "pt": {"name": "Portuguese", "script": "latin", "diacritics": "áàâãçéêíóôõú", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
    "id": {"name": "Indonesian", "script": "latin", "diacritics": "", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
    "ur": {"name": "Urdu", "script": "arabic", "diacritics": "", "foreign_scripts": "cjk cyrillic devanagari bengali hangul"},
    "ru": {"name": "Russian", "script": "cyrillic", "diacritics": "", "foreign_scripts": "cjk arabic devanagari bengali hangul"},
    "de": {"name": "German", "script": "latin", "diacritics": "äöüß", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
    "ja": {"name": "Japanese", "script": "japanese", "diacritics": "", "foreign_scripts": "cyrillic arabic devanagari bengali hangul"},
    "ko": {"name": "Korean", "script": "hangul", "diacritics": "", "foreign_scripts": "cjk cyrillic arabic devanagari bengali"},
    "tr": {"name": "Turkish", "script": "latin", "diacritics": "çğıİöşü", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
    "pl": {"name": "Polish", "script": "latin", "diacritics": "ąćęłńóśźż", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
    "cs": {"name": "Czech", "script": "latin", "diacritics": "ěščřžýáíéúůďťň", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
    "sk": {"name": "Slovak", "script": "latin", "diacritics": "áäčďéíĺľňóôŕšťúýž", "foreign_scripts": "cjk cyrillic arabic devanagari bengali hangul"},
}

_LANGUAGE_TASKS = {
    "en": ("Explain in three concise sentences why local LLM inference can improve privacy.", "Answer in natural English."),
    "zh": ("请用三句话解释本地运行大型语言模型如何提升隐私保护。", "请使用自然、正式的现代标准汉语回答。"),
    "hi": ("स्थानीय भाषा मॉडल चलाने से गोपनीयता कैसे बेहतर हो सकती है? तीन वाक्यों में समझाइए।", "स्वाभाविक और स्पष्ट हिंदी में उत्तर दें।"),
    "es": ("Explica en tres frases por qué ejecutar un modelo de lenguaje local puede mejorar la privacidad.", "Responde en español natural y claro."),
    "ar": ("اشرح في ثلاث جمل كيف يمكن لتشغيل نموذج لغوي محلي أن يحسن حماية الخصوصية.", "أجب باللغة العربية الفصحى وبأسلوب واضح."),
    "fr": ("Expliquez en trois phrases pourquoi l'exécution locale d'un modèle de langage peut améliorer la confidentialité.", "Répondez en français naturel et précis."),
    "bn": ("স্থানীয় ভাষা মডেল চালালে গোপনীয়তা কীভাবে বাড়তে পারে? তিনটি বাক্যে ব্যাখ্যা করুন।", "স্বাভাবিক ও পরিষ্কার বাংলায় উত্তর দিন।"),
    "pt": ("Explique em três frases por que executar um modelo de linguagem local pode melhorar a privacidade.", "Responda em português natural e claro."),
    "id": ("Jelaskan dalam tiga kalimat mengapa menjalankan model bahasa secara lokal dapat meningkatkan privasi.", "Jawablah dalam bahasa Indonesia yang alami dan jelas."),
    "ur": ("تین جملوں میں وضاحت کریں کہ مقامی زبان کا ماڈل چلانے سے رازداری کیسے بہتر ہو سکتی ہے۔", "قدرتی اور واضح اردو میں جواب دیں۔"),
    "ru": ("Объясните в трёх предложениях, почему локальный запуск языковой модели может повысить конфиденциальность.", "Отвечайте на естественном и ясном русском языке."),
    "de": ("Erkläre in drei Sätzen, warum der lokale Betrieb eines Sprachmodells den Datenschutz verbessern kann.", "Antworte in natürlichem und klarem Deutsch."),
    "ja": ("ローカルで大規模言語モデルを実行すると、なぜプライバシーが向上するのか、三文で説明してください。", "自然で明確な日本語で答えてください。"),
    "ko": ("로컬에서 언어 모델을 실행하면 개인정보 보호가 어떻게 향상될 수 있는지 세 문장으로 설명하세요.", "자연스럽고 명확한 한국어로 답하세요."),
    "tr": ("Yerel bir dil modeli çalıştırmanın gizliliği nasıl artırabileceğini üç cümleyle açıkla.", "Doğal ve açık Türkçe kullan."),
    "pl": ("Wyjaśnij w trzech zdaniach, dlaczego lokalne uruchamianie modelu językowego może poprawić prywatność.", "Odpowiedz naturalnym i jasnym językiem polskim."),
    "cs": ("Vysvětli ve třech větách, proč může místní spuštění jazykového modelu zlepšit ochranu soukromí.", "Odpověz přirozenou a spisovnou češtinou."),
    "sk": ("Vysvetli v troch vetách, prečo môže lokálne spustenie jazykového modelu zlepšiť ochranu súkromia.", "Odpovedz prirodzenou a spisovnou slovenčinou."),
}

def _build_prompt(code: str, index: int) -> dict:
    meta = LANGUAGE_PROFILES[code]
    task, instruction = _LANGUAGE_TASKS[code]
    return {
        "id": f"lang_{code}_{index:02d}",
        "category": "language_quality",
        "difficulty": "medium",
        "language": code,
        "language_name": meta["name"],
        "expected_script": meta["script"],
        "expected_diacritics": meta["diacritics"],
        "foreign_scripts": meta["foreign_scripts"].split(),
        "system": instruction,
        "prompt": task,
    }

CUSTOM_LANG_PROMPTS = [_build_prompt(code, 1) for code in LANGUAGE_PROFILES]
CUSTOM_LANG_QUICK = [next(p for p in CUSTOM_LANG_PROMPTS if p["language"] == code) for code in ("en", "zh", "es", "hi", "ar", "sk", "cs")]

# Compatibility aliases used by older stage scripts.
SK_CZ_PROMPTS = CUSTOM_LANG_PROMPTS
SK_CZ_QUICK = CUSTOM_LANG_QUICK
CHAT_SK_CZ_PROMPTS = CUSTOM_LANG_PROMPTS
CHAT_SK_CZ_QUICK = CUSTOM_LANG_QUICK
