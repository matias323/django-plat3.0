from datetime import date

from django.test import SimpleTestCase

from .views.product import _first_day_for_depreciation, _months_between


class DepreciationDateTests(SimpleTestCase):
    def test_day_before_16_uses_current_month(self):
        self.assertEqual(_first_day_for_depreciation(date(2026, 9, 15)), date(2026, 9, 1))

    def test_day_16_uses_next_month(self):
        self.assertEqual(_first_day_for_depreciation(date(2026, 9, 16)), date(2026, 10, 1))

    def test_december_rolls_to_next_year(self):
        self.assertEqual(_first_day_for_depreciation(date(2026, 12, 20)), date(2027, 1, 1))

    def test_month_count_is_inclusive(self):
        self.assertEqual(_months_between(date(2026, 1, 1), date(2026, 1, 1)), 1)
        self.assertEqual(_months_between(date(2026, 1, 1), date(2026, 3, 1)), 3)
