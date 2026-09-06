import unittest

from main import VoiceRequest, process_voice


def empty_form():
    return {
        "name": "",
        "dob": "",
        "phone": "",
        "email": "",
        "application_id": "",
        "pin": "",
        "address": "",
        "city": "",
        "state": "",
        "paragraph": "",
    }


class FieldVoiceProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def assert_field_value(self, field, spoken_text, expected):
        response = await process_voice(
            VoiceRequest(
                text=spoken_text,
                current_form=empty_form(),
                target_field=field,
            )
        )
        self.assertEqual(response["form"][field], expected)

    async def test_each_target_field_is_preserved_and_processed(self):
        cases = {
            "name": ("my name is jane doe", "Jane Doe"),
            "dob": ("4 July 1998", "04/07/1998"),
            "phone": ("my phone is 9876543210", "9876543210"),
            "email": ("jane dot doe at example dot com", "jane.doe@example.com"),
            "application_id": ("ABX 2047 891", "ABX2047891"),
            "pin": ("zero one two three", "0123"),
            "address": ("address is 42 Lake Road", "42 Lake Road"),
            "city": ("city is pune", "Pune"),
            "state": ("state is maharashtra", "Maharashtra"),
            "paragraph": ("description is need wheelchair access", "need wheelchair access"),
        }
        for field, (spoken_text, expected) in cases.items():
            with self.subTest(field=field):
                await self.assert_field_value(field, spoken_text, expected)

    async def test_whole_form_processing_is_still_available(self):
        response = await process_voice(
            VoiceRequest(
                text="my name is jane doe and my phone is 9876543210",
                current_form=empty_form(),
            )
        )
        self.assertEqual(response["form"]["phone"], "9876543210")
        self.assertEqual(response["form"]["name"], "Jane Doe And My Phone Is 9876543210")


if __name__ == "__main__":
    unittest.main()
