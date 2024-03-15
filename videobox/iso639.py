# https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes
import re

# Set 1 codes
LANGUAGES_SET_1 = {
    'aa': 'Afar',
    'ab': 'Abkhazian',
    'af': 'Afrikaans',
    'am': 'Amharic',
    'ar': 'Arabic',
    'as': 'Assamese',
    'ay': 'Aymara',
    'az': 'Azerbaijani',
    'ba': 'Bashkir',
    'be': 'Belarusian',
    'bg': 'Bulgarian',
    'bn': 'Bengali',
    'bo': 'Tibetan',
    'br': 'Breton',
    'bs': 'Bosnian',
    'ca': 'Catalan',
    'cs': 'Czech',
    'cy': 'Welsh',
    'da': 'Danish',
    'de': 'German',
    'dz': 'Dzongkha',
    'el': 'Greek',
    'en': 'English',
    'es': 'Spanish',
    'et': 'Estonian',
    'eu': 'Basque',
    'fa': 'Persian',
    'fi': 'Finnish',
    'fj': 'Fijian',
    'fo': 'Faroese',
    'fr': 'French',
    'ga': 'Irish',
    'gl': 'Galician',
    'gn': 'Guarani',
    'gu': 'Gujarati',
    'he': 'Hebrew',
    'hi': 'Hindi',
    'hr': 'Croatian',
    'hu': 'Hungarian',
    'hy': 'Armenian',
    'id': 'Indonesian',
    'is': 'Icelandic',
    'it': 'Italian',
    'ja': 'Japanese',
    'ka': 'Georgian',
    'kk': 'Kazakh',
    'km': 'Khmer',
    'kn': 'Kannada',
    'ko': 'Korean',
    'ku': 'Kurdish',
    'ky': 'Kyrgyz',
    'lb': 'Luxembourgish',
    'lo': 'Lao',
    'lt': 'Lithuanian',
    'lv': 'Latvian',
    'mg': 'Malagasy',
    'mk': 'Macedonian',
    'ml': 'Malayalam',
    'mn': 'Mongolian',
    'mr': 'Marathi',
    'ms': 'Malay',
    'mt': 'Maltese',
    'nb': 'Norwegian Bokmål',
    'ne': 'Nepali',
    'nl': 'Dutch',
    'nn': 'Norwegian Nynorsk',
    'no': 'Norwegian',
    'oc': 'Occitan',
    'or': 'Oriya',
    'pa': 'Punjabi',
    'pl': 'Polish',
    'ps': 'Pashto',
    'pt': 'Portuguese',
    'ro': 'Romanian',
    'ru': 'Russian',
    'rw': 'Kinyarwanda',
    'si': 'Sinhala',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'sq': 'Albanian',
    'sr': 'Serbian',
    'sv': 'Swedish',
    'sw': 'Swahili',
    'ta': 'Tamil',
    'te': 'Telugu',
    'th': 'Thai',
    'tl': 'Tagalog',
    'tr': 'Turkish',
    'uk': 'Ukrainian',
    'ur': 'Urdu',
    'vi': 'Vietnamese',
    'yi': 'Yiddish',
    'zh': 'Chinese',
    'zu': 'Zulu',
}

# Set 2 codes
LANGUAGES_SET_2 = {    
    "ita": "Italian",
    "fra": "French",
    "fre": "French",
    "spa": "Spanish",
    "deu": "German",
    "ger": "German",
    "eng": "English",
}

# Detect both three-characters and full English names
LANGUAGES_SET_X = LANGUAGES_SET_2 | {v.lower(): v for v in LANGUAGES_SET_2.values()}

RE_SEPARATOR = re.compile(r'[\.,:;\-_]')

def extract_languages(value):
    name = RE_SEPARATOR.sub(' ', value.lower())
    return [LANGUAGES_SET_X[piece] for piece in name.split() if (piece in LANGUAGES_SET_X)]
