import unittest

# Internal logic to be tested
def get_user_slug(email):
    return email.replace("@", "_").replace(".", "_")

class BrandGuardianUnitTests(unittest.TestCase):
    def test_slug_logic(self):
        """Verify email strings are safely converted for file paths."""
        self.assertEqual(get_user_slug("user@example.com"), "user_example_com")
        
    def test_slug_complex(self):
        """Verify multiple dots are handled correctly."""
        self.assertEqual(get_user_slug("dev.test@mail.co.uk"), "dev_test_mail_co_uk")

if __name__ == "__main__":
    unittest.main()