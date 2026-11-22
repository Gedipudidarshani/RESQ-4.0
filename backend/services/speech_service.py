"""
RESQ 4.0 Speech & Multimodal Processing Service
Provides Tamil and English phonetics, emergency keyword mapping,
speech synthesis hooks, and multimodal evidence management.
"""
from typing import Dict, Any, List

TAMIL_SAMPLE_UTTERANCES = [
    {
        "id": "TA-01",
        "tamil": "வணக்கம், அண்ணா மேம்பாலம் அருகே ஒரு பெரிய விபத்து. இரண்டு பேர் பலத்த காயமடைந்துள்ளனர். நான் இங்க இல்ல, என் அலுவலகத்திலிருந்து பார்க்கிறேன்.",
        "english_translation": "Hello, there is a major accident near Anna Flyover. Two people are severely injured. I am not at the spot, I am watching from my office.",
        "language": "ta",
        "category": "Road Accident",
        "caller_away": True,
        "caller_loc": "Office",
        "incident_loc": "Anna Flyover",
        "injuries": "Two people severely injured"
    },
    {
        "id": "TA-02",
        "tamil": "தி.நகர் மார்க்கெட் அருகே ஒரு கடையில் பலத்த தீப்பிடித்து புகை வருகிறது! உடனடியாக தீயணைப்பு வண்டி தேவை!",
        "english_translation": "A heavy fire broke out in a shop near T. Nagar market with thick smoke! Fire engine needed immediately!",
        "language": "ta",
        "category": "Fire Hazard",
        "caller_away": False,
        "caller_loc": "Near T. Nagar Market",
        "incident_loc": "T. Nagar Market Shop",
        "injuries": "Unknown, heavy smoke"
    }
]

ENGLISH_SAMPLE_UTTERANCES = [
    {
        "id": "EN-01",
        "text": "There has been a head-on collision near the river bridge. Two people are bleeding and unconscious. I am driving past, not at the exact location.",
        "language": "en",
        "category": "Road Accident",
        "caller_away": True,
        "caller_loc": "In-transit vehicle",
        "incident_loc": "River bridge",
        "injuries": "Two people bleeding and unconscious"
    },
    {
        "id": "EN-02",
        "text": "Emergency! Someone collapsed with sudden chest pain inside the community center. Breathing is very shallow.",
        "language": "en",
        "category": "Medical Emergency",
        "caller_away": False,
        "caller_loc": "Community center",
        "incident_loc": "Community center",
        "injuries": "One person collapsed / chest pain"
    }
]

class SpeechProcessingService:
    def get_supported_languages(self) -> List[Dict[str, str]]:
        return [
            {"code": "en", "name": "English (India / Global)", "voice_recognition": "Enabled"},
            {"code": "ta", "name": "தமிழ் (Tamil)", "voice_recognition": "Enabled"}
        ]

    def get_sample_utterances(self) -> Dict[str, Any]:
        return {
            "tamil": TAMIL_SAMPLE_UTTERANCES,
            "english": ENGLISH_SAMPLE_UTTERANCES
        }

speech_service = SpeechProcessingService()
