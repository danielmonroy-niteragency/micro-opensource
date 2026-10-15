import unittest

from text_processing import clean


class CleanTextTests(unittest.TestCase):
    def test_removes_fillers_and_capitalizes(self):
        self.assertEqual(clean("ehm hola mundo"), "Hola mundo")

    def test_spoken_paragraph_and_punctuation(self):
        self.assertEqual(
            clean("primera frase punto y aparte segunda frase coma correcto punto final"),
            "Primera frase.\n\nSegunda frase, correcto.",
        )

    def test_question_marks(self):
        self.assertEqual(
            clean("abrir interrogacion funciona cerrar interrogacion"),
            "¿Funciona?",
        )

    def test_filters_common_hallucination(self):
        self.assertEqual(clean("Gracias por ver el video."), "")


if __name__ == "__main__":
    unittest.main()

