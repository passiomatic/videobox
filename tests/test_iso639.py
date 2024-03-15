import pytest
from videobox import iso639

@pytest.mark.parametrize("value,expected", [
    ("Constellation.S01E01.L.angelo.ferito.ITA.ENG.1080p.ATVP.WEB.DL.DD5.1.H.264.MeM.GP.mkv", ["Italian", "English"]),
    ("Halo.S02e05..1080p.Ita.Eng.Spa.h265.10bit.SubS..byMe7alh..MIRCrew.", ["Italian", "English", "Spanish"]), 
    ("Home.Economics.S02E20.720p.HDTV.x264-SYNCOPY[eztv.re].mkv", []), 
    ("Star Wars: The Bad Batch S03E07 FRENCH HDTV", ["French"]), 
])
def test_extract_languages(app, value, expected):
    assert iso639.extract_languages(value) == expected
