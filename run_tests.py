# run_tests.py
"""
Запуск тестов
"""

import unittest
import sys
import os


def run_tests():
    """Запуск всех тестов"""
    # Поиск всех тестов
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern="test_*.py")

    # Запуск тестов
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Возврат кода выхода
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
