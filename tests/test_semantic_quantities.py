"""Typed numeric observations (VEGA next W02)."""

from __future__ import annotations

import random
import unittest

from memory_fabric.causal_replay.semantic.observations import (Predicate, evaluate, extract, verify_span,
                                                              words_to_number)

HOT = Predicate("temperature", "gt", 50.0)


def one(text: str, **kw):
    obs = extract(text, default_unit="C", **kw)
    assert len(obs) == 1, (text, obs)
    return obs[0]


class Schema(unittest.TestCase):
    def test_records_carry_sensor_property_value_unit_relation_time_and_span(self):
        o = one("10:15 pack P-7 sensor TB2 reads 64 C", evidence_ref="m1@1", sensor="pack:p-7/sensor:tb2")
        self.assertEqual((o.status, o.relation, o.low, o.high, o.unit, o.time, o.evidence_ref, o.sensor),
                         ("OK", "eq", 64.0, 64.0, "C", "10:15", "m1@1", "pack:p-7/sensor:tb2"))
        self.assertEqual(o.to_dict()["span"]["text"], "64 C")
        unscoped = extract("it reads 64", default_unit="C")
        self.assertEqual(unscoped, [])  # a number with no unit is not a temperature observation
        self.assertEqual(extract("reads 64 zorks"), [])  # not a recognised unit: no quantity claimed


class Digits(unittest.TestCase):
    def test_integers_decimals_signs_and_separators_are_exact(self):
        cases = {"61 C": 61.0, "-4.5 C": -4.5, "50.0 C": 50.0, "+3 C": 3.0, "−7 C": -7.0}
        for text, value in cases.items():
            self.assertEqual(one(f"reads {text}").low, value, text)
        current = extract("draws 1,250 mA", property="current")
        self.assertEqual((current[0].low, current[0].unit), (1250.0, "mA"))


class Words(unittest.TestCase):
    def test_number_words_map_deterministically_or_not_at_all(self):
        known = {"sixty-one": 61, "sixty four": 64, "fifty": 50, "one hundred and two": 102,
                 "negative five": -5, "minus twelve": -12, "fifty point five": 50.5, "nineteen": 19}
        for phrase, value in known.items():
            self.assertEqual(words_to_number(phrase), value, phrase)
        for bad in ("twenty twenty", "fifty sixty", "hundred", "point", "sixty-onety", "eleventy"):
            self.assertIsNone(words_to_number(bad), bad)

    def test_the_two_pr41_regressions_read_as_hot(self):
        for text in ("At 10:00 the A-side thermistor TA1 on pack P-7 was showing sixty-one degrees",
                     "The second sensor on P-7, TB2, logged sixty-four degrees at 10:15"):
            self.assertEqual(evaluate(one(text), HOT), "TRUE", text)

    def test_unreadable_quantities_are_unknown_never_dropped(self):
        for text in ("gazillion degrees", "the display showed some degrees"):
            obs = extract(text, default_unit="C")
            self.assertTrue(obs and all(o.status == "UNKNOWN" for o in obs), text)


class Units(unittest.TestCase):
    def test_celsius_fahrenheit_and_kelvin_agree(self):
        for text in ("61 C", "61 °C", "61 degrees Celsius", "141.8 F", "141.8 °F", "334.15 K", "334.15 kelvin"):
            self.assertAlmostEqual(one(f"reads {text}").low, 61.0, places=6, msg=text)

    def test_unknown_or_incompatible_units_abstain(self):
        self.assertEqual(extract("reads 61 degrees", default_unit=None)[0].status, "UNKNOWN")
        self.assertEqual(extract("reads 61 V", default_unit="C")[0].status, "UNKNOWN")
        registry_unit = one("reads 61 degrees")
        self.assertTrue(registry_unit.unit_from_registry)


class Relations(unittest.TestCase):
    def test_comparisons_are_intervals_with_distinct_outcomes(self):
        expect = {"above 50 C": "TRUE", "at least 50 C": "UNKNOWN", "at most 50 C": "FALSE",
                  "exactly 50 C": "FALSE", "around 50 C": "UNKNOWN", "below 50 C": "FALSE",
                  "50.1 C": "TRUE", "49.9 C": "FALSE", "not above 50 C": "FALSE", "not below 51 C": "TRUE"}
        for text, verdict in expect.items():
            self.assertEqual(evaluate(one(f"reading {text}"), HOT), verdict, text)
        self.assertEqual(evaluate(one("reading at least 50 C"), Predicate("temperature", "ge", 50)), "TRUE")

    def test_hedges_double_negation_and_threshold_crossing_ranges_are_never_safe(self):
        self.assertEqual(one("reading maybe 61 C").status, "UNKNOWN")
        self.assertEqual(one("it is not not above 50 C").status, "UNKNOWN")
        self.assertEqual(evaluate(one("between 40 and 60 C"), HOT), "UNKNOWN")
        self.assertEqual(evaluate(one("between 20 and 30 C"), HOT), "FALSE")


class Provenance(unittest.TestCase):
    def test_every_value_reads_back_from_its_span(self):
        text = "At 10:00 TA1 showed sixty-one degrees; TB2 read 41 C at 10:15"
        for o in extract(text, default_unit="C"):
            self.assertTrue(verify_span(o, text))
            self.assertFalse(verify_span(o, text.replace("sixty-one", "sixty-two").replace("41", "42")))


class Metamorphic(unittest.TestCase):
    """Hundreds of generated equivalent sentences must agree on the threshold verdict."""

    WORDS = {38: "thirty-eight", 41: "forty-one", 49: "forty-nine", 51: "fifty-one", 61: "sixty-one",
             64: "sixty-four", 72: "seventy-two"}
    TEMPLATES = ("{s} reads {v}", "{s} was showing {v}", "At 10:00, {s} logged {v}.", "{s}: {v}",
                 "Reading from {s} -- {v}", "{s} reported {v} at 10:15", "the value on {s} is {v}")

    def test_equivalent_phrasings_give_the_same_verdict(self):
        rng = random.Random(7)
        checked = 0
        for _ in range(400):
            value = rng.choice(list(self.WORDS))
            form = rng.choice(["digits_c", "digits_deg", "words", "fahrenheit"])
            v = {"digits_c": f"{value} C", "digits_deg": f"{value} °C", "words": f"{self.WORDS[value]} degrees",
                 "fahrenheit": f"{value * 9 / 5 + 32:.1f} F"}[form]
            text = rng.choice(self.TEMPLATES).format(s=rng.choice(["TA1", "probe B", "sensor TB2"]), v=v)
            obs = [o for o in extract(text, default_unit="C") if o.readable]
            self.assertEqual(len(obs), 1, text)
            self.assertEqual(evaluate(obs[0], HOT), "TRUE" if value > 50 else "FALSE", text)
            checked += 1
        self.assertEqual(checked, 400)

    def test_punctuation_and_case_noise_does_not_change_the_value(self):
        for text in ("TA1 READS 61 C!!!", "ta1 reads 61 c", "TA1 reads 61C.", "TA1 reads (61 C)"):
            self.assertEqual(one(text).low, 61.0, text)


if __name__ == "__main__":
    unittest.main()
