import pytest

from app.vin_decode import decode_make, decode_model_year, year_code_matches

SAMPLE_VIN = "1G1FY6S0XN0000123"  # 1G1 = Chevrolet, position 10 'N' = 2022


def vin_with_pos10(char: str) -> str:
    return SAMPLE_VIN[:9] + char + SAMPLE_VIN[10:]


class TestDecodeModelYear:
    def test_sample_vin(self):
        assert decode_model_year(SAMPLE_VIN, now_year=2026) == 2022

    def test_most_recent_cycle_wins(self):
        assert decode_model_year(vin_with_pos10("A"), now_year=2026) == 2010  # not 1980

    def test_cycle_boundary(self):
        # limit = now_year + 1 = 2027
        assert decode_model_year(vin_with_pos10("V"), now_year=2026) == 2027  # base 1997
        assert decode_model_year(vin_with_pos10("W"), now_year=2026) == 1998  # 2028 > limit
        assert decode_model_year(vin_with_pos10("W"), now_year=2027) == 2028

    @pytest.mark.parametrize("char", ["U", "Z", "0", "I", "O", "Q"])
    def test_undecodable_codes(self, char):
        assert decode_model_year(vin_with_pos10(char), now_year=2026) is None

    def test_wrong_length_guard(self):
        assert decode_model_year("1G1FY6S0XN", now_year=2026) is None


class TestYearCodeMatches:
    def test_match(self):
        assert year_code_matches(2022, SAMPLE_VIN) is True

    def test_match_previous_cycle(self):
        assert year_code_matches(1992, SAMPLE_VIN) is True  # 'N' is also 1992

    def test_mismatch(self):
        assert year_code_matches(2023, SAMPLE_VIN) is False

    def test_undecodable_returns_none(self):
        assert year_code_matches(2022, vin_with_pos10("U")) is None

    def test_wrong_length_guard(self):
        assert year_code_matches(2022, "1G1") is None


class TestDecodeMake:
    @pytest.mark.parametrize(
        "prefix, expected",
        [
            ("1G1", "Chevrolet"),
            ("1GC", "Chevrolet"),
            ("1GT", "GMC"),
            ("1GK", "GMC"),
            ("1FA", "Ford"),
            ("1FT", "Ford"),
            ("JTD", "Toyota"),  # via the 2-char "JT" fallback
            ("KMH", "Hyundai"),
            ("KNA", "Kia"),
            ("1N4", "Nissan"),
            ("1HG", "Honda"),
            ("1J4", "Jeep"),
            ("1C6", "Ram"),
        ],
    )
    def test_known_wmis(self, prefix, expected):
        assert decode_make(prefix + "XXXXXXXXXXXXXX") == expected

    @pytest.mark.parametrize("prefix", ["JTH", "JTJ", "1C4"])
    def test_explicit_none_stops_fallthrough(self, prefix):
        assert decode_make(prefix + "XXXXXXXXXXXXXX") is None

    def test_unknown_wmi(self):
        assert decode_make("WVWZZZXXXXXXXXXXX") is None  # Volkswagen, not in table

    def test_case_insensitive(self):
        assert decode_make("1g1fy6s0xn0000123") == "Chevrolet"

    def test_sample_vin(self):
        assert decode_make(SAMPLE_VIN) == "Chevrolet"
